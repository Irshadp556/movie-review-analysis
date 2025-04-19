import streamlit as st
from auth import show_login, logout_button
from db import create_tables, add_review, get_user_reviews
from groq import Groq
import os
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from collections import Counter

# Initialize
load_dotenv()
create_tables()  # This ensures tables are created with correct structure

# Initialize session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.user_id = None
    st.session_state.history = []

# Authentication
if not st.session_state.logged_in:
    show_login()
    st.stop()

# Main App
try:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        st.error("GROQ_API_KEY not found in environment variables")
        st.stop()
    
    client = Groq(api_key=api_key)
except Exception as e:
    st.error(f"Error initializing Groq client: {e}")
    st.stop()

st.title("🎬 Movie Review Sentiment Analyzer")
st.write(f"Welcome, {st.session_state.user}!")

# Sentiment analysis
emoji_map = {
    "positive": "😊",
    "negative": "😞",
    "neutral": "😐"
}

feedback_map = {
    "positive": "Great! Your review sounds very positive. 🎉",
    "negative": "Hmm... looks like you didn't enjoy it much. 😢",
    "neutral": "It's a mixed review. 😐"
}

user_review = st.text_area("Enter your movie review:", height=150)

if st.button("Analyze Sentiment"):
    if not user_review.strip():
        st.warning("Please enter a review before submitting.")
    else:
        with st.spinner("Analyzing sentiment..."):
            try:
                prompt = f"""
                Analyze the sentiment of the following movie review and classify it as one of: Positive, Negative, or Neutral.
                Respond with only one word: Positive, Negative, or Neutral.

                Review: \"{user_review}\"
                """

                response = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama3-70b-8192"
                )

                sentiment = response.choices[0].message.content.strip().lower()
                
                # Store the review in database
                add_review(st.session_state.user_id, user_review, sentiment)
                
                # Update session state
                st.session_state.history.append((user_review, sentiment))
                
                emoji = emoji_map.get(sentiment, "🤔")
                feedback = feedback_map.get(sentiment, "Couldn't determine the sentiment clearly. 🤔")

                st.markdown(f"""
                ### Sentiment Result  
                **{sentiment.capitalize()}** {emoji}

                ---
                {feedback}
                """)

            except Exception as e:
                st.error(f"Error analyzing sentiment: {e}")

# Display review history
st.markdown("---")
st.subheader("📝 Review History")

# Get reviews from database
try:
    reviews = get_user_reviews(st.session_state.user_id)

    if reviews:
        # Display individual review cards
        for review_text, sentiment, created_at in reviews[:5]:  # Show last 5 reviews
            emoji = emoji_map.get(sentiment, "")
            date_str = created_at.strftime("%Y-%m-%d %H:%M")
            
            st.markdown(f"""
            <div style="
                border: 1px solid #ddd;
                border-radius: 10px;
                padding: 15px;
                margin: 10px 0;
                background-color: #f9f9f9;
            ">
                <div style="display: flex; justify-content: space-between;">
                    <h4 style="margin: 0;">{sentiment.capitalize()} {emoji}</h4>
                    <small>{date_str}</small>
                </div>
                <p style="margin: 10px 0 0 0;">{review_text}</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Sentiment distribution chart
        st.markdown("---")
        st.subheader("📊 Sentiment Distribution")
        
        sentiments = [review[1] for review in reviews]
        counts = Counter(sentiments)
        labels = list(counts.keys())
        values = list(counts.values())

        fig, ax = plt.subplots()
        ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90,
               colors=['#4CAF50', '#F44336', '#FFC107'])
        ax.axis("equal")
        st.pyplot(fig)
    else:
        st.info("No reviews yet. Analyze some reviews to see them here.")
except Exception as e:
    st.error(f"Error loading reviews: {e}")

# Logout
logout_button()