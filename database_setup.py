import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')
DB_NAME = os.getenv('DB_NAME')
DB_HOST = os.getenv('DB_HOST') # <-- New variable with the IP address

def setup():
    conn = None
    try:
        # Connect via public IP address - intended only for the build step
        conn = psycopg2.connect(
            host=DB_HOST,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        print("Connected to PostgreSQL via Public IP for setup.")
        
        with conn.cursor() as cursor:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                whatsapp_id TEXT PRIMARY KEY,
                google_refresh_token TEXT NOT NULL,
                user_name TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            print("'users' table created or already exists.")
        
        conn.commit()

    except Exception as e:
        print(f"An error occurred during database setup: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    setup()