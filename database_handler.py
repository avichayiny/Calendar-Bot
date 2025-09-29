import os
import psycopg2

# נקרא את כתובת בסיס הנתונים ממשתני הסביבה
DATABASE_URL = os.getenv('DATABASE_URL')

def add_user(whatsapp_id, refresh_token, user_name):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # הפקודה ב-PostgreSQL מעט שונה, היא בטוחה יותר ומונעת כפילויות
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
    cursor.close()
    conn.close()
    print(f"User {whatsapp_id} ({user_name}) was added/updated in the PostgreSQL database.")

def get_user_token(whatsapp_id):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute("SELECT google_refresh_token FROM users WHERE whatsapp_id = %s", (whatsapp_id,))
    
    result = cursor.fetchone() 
    
    cursor.close()
    conn.close()
    
    if result:
        return result[0] 
    else:
        return None
