import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
# חשוב: ודא שמשתנה הסביבה DATABASE_URL מוגדר גם בקובץ ה-.env המקומי שלך
DATABASE_URL = os.getenv('DATABASE_URL')

conn = psycopg2.connect(DATABASE_URL)
print("Connected to PostgreSQL database.")
cursor = conn.cursor()

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
cursor.close()
conn.close()
print("Database setup is complete.")