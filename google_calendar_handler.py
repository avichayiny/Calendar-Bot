# google_calendar_handler.py (גרסה 20.0 - הגרסה הסופית והמאובטחת עבור Render)

import os
import json
from datetime import datetime, time
from google.oauth2.credentials import Credentials # <-- ייבוא הכרחי
from googleapiclient.discovery import build

# --- הגדרות שנקראות ממשתני הסביבה ב-Render ---
SCOPES = ['https://www.googleapis.com/auth/calendar']
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
# ---------------------------------------------------

def create_event_for_user(user_refresh_token, summary, start_time, end_time):
    """
    יוצר אירוע ביומן עבור משתמש ספציפי באמצעות ה-refresh_token שלו.
    """
    try:
        # יוצרים את אובייקט ההרשאות עם כל המידע הנדרש ממשתני הסביבה
        creds = Credentials.from_authorized_user_info(
            info={
                'refresh_token': user_refresh_token,
                'client_id': GOOGLE_CLIENT_ID,
                'client_secret': GOOGLE_CLIENT_SECRET
            },
            scopes=SCOPES
        )
        
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
        print(f"An error occurred in create_event_for_user: {e}")
        return f"An error occurred: {e}"


def get_events_for_day(user_refresh_token, target_date):
    """
    שולף את כל האירועים ליום מסוים מהיומן של המשתמש.
    """
    try:
        # קוד האימות זהה - שימוש במשתני הסביבה
        creds = Credentials.from_authorized_user_info(
            info={
                'refresh_token': user_refresh_token,
                'client_id': GOOGLE_CLIENT_ID,
                'client_secret': GOOGLE_CLIENT_SECRET
            },
            scopes=SCOPES
        )
        
        service = build('calendar', 'v3', credentials=creds)

        start_of_day = datetime.combine(target_date, time.min).isoformat() + 'Z'
        end_of_day = datetime.combine(target_date, time.max).isoformat() + 'Z'

        print(f"Fetching events for {target_date}...")
        events_result = service.events().list(
            calendarId='primary', 
            timeMin=start_of_day,
            timeMax=end_of_day, 
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        print(f"Found {len(events)} events.")
        return events

    except Exception as e:
        print(f"An error occurred in get_events_for_day: {e}")
        return None

def delete_event(user_refresh_token, event_id):
    """
    מוחק אירוע ספציפי מהיומן של המשתמש לפי ה-ID שלו.
    """
    try:
        # קוד האימות זהה לפונקציות הקודמות
        creds = Credentials.from_authorized_user_info(
            info={
                'refresh_token': user_refresh_token,
                'client_id': GOOGLE_CLIENT_ID,
                'client_secret': GOOGLE_CLIENT_SECRET
            },
            scopes=SCOPES
        )

        service = build('calendar', 'v3', credentials=creds)

        # קריאה ל-API של גוגל כדי למחוק את האירוע
        service.events().delete(
            calendarId='primary', 
            eventId=event_id
        ).execute()

        print(f"Successfully deleted event with ID: {event_id}")
        return True # החזר True בהצלחה

    except Exception as e:
        print(f"An error occurred in delete_event: {e}")
        return False # החזר False בכישלון