# database_setup.py

import sqlite3

# שם קובץ בסיס הנתונים
DB_FILE = "bot_database.db"

# מתחברים לבסיס הנתונים (אם הקובץ לא קיים, הוא ייווצר)
conn = sqlite3.connect(DB_FILE)
print("Database file created or connected successfully.")

# יוצרים "סמן" שדרכו נבצע פקודות
cursor = conn.cursor()

# --- יצירת טבלת המשתמשים ---
# הפקודה הזו תבוצע רק אם הטבלה לא קיימת עדיין
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    whatsapp_id TEXT PRIMARY KEY,
    google_refresh_token TEXT NOT NULL,
    user_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')
print("'users' table created or already exists.")

# שמירת השינויים וסגירת החיבור
conn.commit()
conn.close()

print("Database setup is complete.")