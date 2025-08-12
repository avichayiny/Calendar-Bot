# database_handler.py

import sqlite3

DB_FILE = "bot_database.db"

def add_user(whatsapp_id, refresh_token, user_name):
    """מוסיף משתמש חדש או מעדכן משתמש קיים בבסיס הנתונים."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # הפקודה "REPLACE" תעדכן את הרשומה אם ה-whatsapp_id כבר קיים, או תיצור חדשה אם לא.
    cursor.execute(
        "REPLACE INTO users (whatsapp_id, google_refresh_token, user_name) VALUES (?, ?, ?)",
        (whatsapp_id, refresh_token, user_name)
    )
    
    conn.commit()
    conn.close()
    print(f"User {whatsapp_id} ({user_name}) was added/updated in the database.")

def get_user_token(whatsapp_id):
    """מחזיר את ה-refresh_token של משתמש ספציפי."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT google_refresh_token FROM users WHERE whatsapp_id = ?", (whatsapp_id,))
    
    # fetchone() יחזיר None אם המשתמש לא נמצא
    result = cursor.fetchone() 
    
    conn.close()
    
    if result:
        # התוצאה היא tuple, אנחנו רוצים את הפריט הראשון
        return result[0] 
    else:
        return None