# database_handler.py (SQLAlchemy Version)
import os
from sqlalchemy import create_engine, Column, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.dialects.postgresql import insert

# שולפים את המחרוזת היחידה מהגדרות הסביבה
DATABASE_URL = os.getenv('DB_URL')

# יצירת מנוע החיבור עם Pooling שמותאם לענן
engine = create_engine(
    DATABASE_URL, 
    pool_size=5, 
    max_overflow=10,
    pool_pre_ping=True # מוודא שהחיבור לא נותק לפני שהוא משתמש בו
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# הגדרת מודל הטבלה שלנו
class User(Base):
    __tablename__ = "users"
    
    whatsapp_id = Column(String(50), primary_key=True, index=True)
    google_refresh_token = Column(Text)
    user_name = Column(String(100))

def init_db():
    """יוצר את הטבלאות ב-DB אם הן לא קיימות (מעולה ל-Neon ריק)"""
    Base.metadata.create_all(bind=engine)
    print("Database tables verified/created successfully via SQLAlchemy.")

def add_user(whatsapp_id, refresh_token, user_name):
    db = SessionLocal()
    try:
        # בונים את פעולת ההכנסה
        stmt = insert(User).values(
            whatsapp_id=whatsapp_id,
            google_refresh_token=refresh_token,
            user_name=user_name
        )
        
        # מגדירים מה קורה אם המשתמש כבר קיים (Upsert)
        stmt = stmt.on_conflict_do_update(
            index_elements=['whatsapp_id'],
            set_={
                'google_refresh_token': refresh_token,
                'user_name': user_name
            }
        )
        
        db.execute(stmt)
        db.commit()
        print(f"User {whatsapp_id} ({user_name}) was added/updated.")
    except Exception as e:
        print(f"Error saving user: {e}")
        db.rollback()
    finally:
        db.close()

def get_user_token(whatsapp_id):
    db = SessionLocal()
    try:
        # שליפה פשוטה ונקייה של המשתמש
        user = db.query(User).filter(User.whatsapp_id == whatsapp_id).first()
        if user:
            return user.google_refresh_token
        return None
    except Exception as e:
        print(f"Error fetching token: {e}")
        return None
    finally:
        db.close()