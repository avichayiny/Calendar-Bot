# google_calendar_handler.py (גרסת משתמשים מרובים - מתוקן)

import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']
CLIENT_SECRET_FILE = 'credentials.json' 

def create_event_for_user(user_refresh_token, summary, start_time, end_time):
    """
    יוצר אירוע ביומן עבור משתמש ספציפי באמצעות ה-refresh_token שלו.
    """
    if not user_refresh_token:
        return "Error: No refresh token provided."

    try:
        # --- [התיקון] ---
        # 1. טען את סודות הלקוח (תעודת הזהות של הבוט) מהקובץ
        with open(CLIENT_SECRET_FILE) as f:
            client_secrets = json.load(f)['installed']
        
        # 2. צור את אובייקט ההרשאות עם כל המידע הנדרש
        creds = Credentials.from_authorized_user_info(
            info={
                'refresh_token': user_refresh_token,
                'client_id': client_secrets['client_id'],
                'client_secret': client_secrets['client_secret']
            },
            scopes=SCOPES
        )
        
        # הרענון יתרחש אוטומטית אם צריך
        service = build('calendar', 'v3', credentials=creds)

        event = {
            'summary': summary,
            'start': {'dateTime': start_time, 'timeZone': 'Asia/Jerusalem'},
            'end': {'dateTime': end_time, 'timeZone': 'Asia/Jerusalem'},
        }

        created_event = service.events().insert(calendarId='primary', body=event).execute()
        print(f"Successfully created event for user.")
        return created_event.get('htmlLink')

    except Exception as e:
        print(f"An error occurred in Google Calendar Handler: {e}")
        return f"An error occurred: {e}"