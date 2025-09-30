import os
import psycopg2

# --- [שדרוג] קריאת פרטי החיבור המאובטח ממשתני הסביבה ---
DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')
DB_NAME = os.getenv('DB_NAME')
INSTANCE_CONNECTION_NAME = os.getenv('INSTANCE_CONNECTION_NAME') # שם החיבור המיוחד מ-Cloud SQL

def get_connection():
    """יוצר ופותח חיבור מאובטח לבסיס הנתונים."""
    try:
        # בתוך סביבת Cloud Run, נתיב ה-socket נוצר אוטומטית
        unix_socket_path = f"/cloudsql/{INSTANCE_CONNECTION_NAME}"
        conn = psycopg2.connect(
            host=unix_socket_path,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        return conn
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return None

def add_user(whatsapp_id, refresh_token, user_name):
    conn = get_connection()
    if not conn: return

    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO users (whatsapp_id, google_refresh_token, user_name) 
            VALUES (%s, %s, %s)
            ON CONFLICT (whatsapp_id) 
            DO UPDATE SET google_refresh_token = EXCLUDED.google_refresh_token, user_name = EXCLUDED.user_name;
            """,
            (whatsapp_id, refresh_token, user_name)
        )
    conn.commit()
    conn.close()
    print(f"User {whatsapp_id} ({user_name}) was added/updated in the PostgreSQL database.")

def get_user_token(whatsapp_id):
    conn = get_connection()
    if not conn: return None

    with conn.cursor() as cursor:
        cursor.execute("SELECT google_refresh_token FROM users WHERE whatsapp_id = %s", (whatsapp_id,))
        result = cursor.fetchone()
    
    conn.close()
    
    if result:
        return result[0] 
    else:
        return None
