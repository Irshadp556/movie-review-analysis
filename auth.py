import streamlit as st
from db import add_user, validate_login, user_exists, create_tables, get_db_cursor
import re
import time
import httpx
from urllib.parse import urlencode
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8501/")  # Must end with /

# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"

def is_strong_password(password):
    return (
        len(password) >= 8 and
        re.search(r"[A-Z]", password) and
        re.search(r"[a-z]", password) and
        re.search(r"[0-9]", password) and
        re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", password)
    )

def validate_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def validate_username(username):
    return re.match(r"^[a-zA-Z0-9_]{3,20}$", username)

async def exchange_code_for_token(code):
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(GOOGLE_TOKEN_URL, data=data)
        return response.json()

async def get_google_user_info(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(GOOGLE_USERINFO_URL, headers=headers)
        return response.json()

async def handle_google_auth(code):
    try:
        # Exchange code for tokens
        token_response = await exchange_code_for_token(code)
        
        if 'error' in token_response:
            st.error(f"Authentication failed: {token_response.get('error_description', 'Unknown error')}")
            return None
        
        # Get user info
        user_info = await get_google_user_info(token_response['access_token'])
        return user_info
    except Exception as e:
        st.error(f"Google Sign-In failed: {str(e)}")
        return None

def show_login():
    st.title("🔐 Login to Movie Review App")

    if 'login_attempts' not in st.session_state:
        st.session_state.login_attempts = 0

    if "menu" not in st.session_state:
        st.session_state.menu = "Login"

    st.session_state.menu = st.sidebar.selectbox("Menu", ["Login", "Signup"], 
                                               index=["Login", "Signup"].index(st.session_state.menu))

    # Generate Google OAuth URL
    params = {
        "response_type": "code",
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account"
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    # Google Sign-In Button
    st.markdown(f"""
    <div style="text-align: center; margin: 20px 0;">
        <a href="{auth_url}">
            <img src="https://developers.google.com/identity/images/btn_google_signin_dark_normal_web.png" alt="Sign in with Google">
        </a>
    </div>
    """, unsafe_allow_html=True)

    # Handle Google OAuth callback
    query_params = st.query_params
    if 'code' in query_params:
        code = query_params['code']
        
        # Run async function synchronously for Streamlit
        user_info = asyncio.run(handle_google_auth(code))
        
        if user_info:
            email = user_info['email']
            
            # Check if user exists in your database
            if not user_exists(email):
                # Create new user with Google info
                username = email.split('@')[0]
                password = "google_auth_" + os.urandom(16).hex()  # Random password
                user_id = add_user(username, email, password)
            else:
                # Get existing user ID
                try:
                    with get_db_cursor() as cursor:
                        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                        result = cursor.fetchone()
                        if result:
                            user_id = result[0]
                        else:
                            st.error("User not found in database")
                            return
                except Exception as e:
                    st.error(f"Database error: {str(e)}")
                    return
            
            # Set session state
            st.session_state.logged_in = True
            st.session_state.user = email
            st.session_state.user_id = user_id
            st.session_state.login_attempts = 0
            
            # Clear the code from URL and rerun
            st.query_params.clear()
            st.rerun()

    if st.session_state.menu == "Login":
        st.subheader("Login to Your Account")

        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")

            if st.form_submit_button("Login"):
                if not email or not password:
                    st.error("Please fill in all fields")
                elif not validate_email(email):
                    st.error("Please enter a valid email address")
                else:
                    user_id = validate_login(email, password)
                    if user_id:
                        st.success("Login successful!")
                        st.session_state.logged_in = True
                        st.session_state.user = email
                        st.session_state.user_id = user_id
                        st.session_state.login_attempts = 0
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.session_state.login_attempts += 1
                        if st.session_state.login_attempts > 2:
                            st.warning("Forgot your password? Try resetting it.")
                        st.error("Invalid email or password")

    elif st.session_state.menu == "Signup":
        st.subheader("Create New Account")

        with st.form("signup_form"):
            username = st.text_input("Username (3-20 chars, letters, numbers, _)", key="signup_username")
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            confirm_password = st.text_input("Confirm Password", type="password", key="signup_confirm_password")

            if st.form_submit_button("Signup"):
                if not all([username, email, password, confirm_password]):
                    st.error("Please fill in all fields")
                elif not validate_username(username):
                    st.error("Username must be 3-20 chars (letters, numbers, _)")
                elif not validate_email(email):
                    st.error("Please enter a valid email address")
                elif password != confirm_password:
                    st.error("Passwords do not match")
                elif not is_strong_password(password):
                    st.warning("""
                    Password must contain:
                    - 8+ characters
                    - Uppercase letter
                    - Lowercase letter
                    - Number
                    - Special character
                    """)
                elif user_exists(email):
                    st.warning("An account with this email already exists")
                else:
                    try:
                        user_id = add_user(username, email, password)
                        st.success("Account created successfully! Please login with your credentials.")
                        time.sleep(1.5)
                        st.session_state.menu = "Login"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error creating account: {str(e)}")

def logout_button():
    if st.sidebar.button("Logout", key="logout_button"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.user_id = None
        st.session_state.history = []
        st.success("You have been logged out successfully!")
        time.sleep(0.5)
        st.rerun()

def password_reset_request():
    if st.sidebar.button("Forgot Password?"):
        st.info("Password reset functionality coming soon!")