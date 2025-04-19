import psycopg2
import bcrypt
from contextlib import contextmanager
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@contextmanager
def get_db_connection():
    conn = None
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "demo"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "5565"),
            port=os.getenv("DB_PORT", "5432")
        )
        yield conn
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()

@contextmanager
def get_db_cursor():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Database error: {e}")
            raise
        finally:
            cursor.close()

def create_tables():
    with get_db_cursor() as cursor:
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Reviews table - corrected structure
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                review_text TEXT NOT NULL,
                sentiment TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

def add_user(username, email, password):
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (%s, %s, %s) RETURNING id",
            (username, email, hashed.decode())
        )
        return cursor.fetchone()[0]

def validate_login(email, password):
    with get_db_cursor() as cursor:
        cursor.execute("SELECT id, password FROM users WHERE email = %s", (email,))
        row = cursor.fetchone()
        if row and bcrypt.checkpw(password.encode(), row[1].encode()):
            return row[0]  # Return user ID
        return None

def user_exists(email):
    with get_db_cursor() as cursor:
        cursor.execute("SELECT 1 FROM users WHERE email = %s", (email,))
        return cursor.fetchone() is not None

def add_review(user_id, review_text, sentiment):
    with get_db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO reviews (user_id, review_text, sentiment) VALUES (%s, %s, %s)",
            (user_id, review_text, sentiment)
        )

def get_user_reviews(user_id):
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT review_text, sentiment, created_at FROM reviews WHERE user_id = %s ORDER BY created_at DESC",
            (user_id,)
        )
        return cursor.fetchall()