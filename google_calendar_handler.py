# google_calendar_handler.py

import os
import json
from datetime import datetime, time, timedelta
from google.oauth2.credentials import Credentials # <-- Necessary import
from googleapiclient.discovery import build
from zoneinfo import ZoneInfo

# --- Settings read from environment variables ---
SCOPES = ['https://www.googleapis.com/auth/calendar']
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
# ---------------------------------------------------

def create_event_for_user(user_refresh_token, summary, start_time, end_time):
    """
    Creates a calendar event for a specific user using their refresh_token.
    """
    try:
        # Create the credentials object with all the required info from environment variables
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
    Fetches all events for a specific day from the user's calendar.
    """
    try:
        # Authentication code is the same - use environment variables
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
    Deletes a specific event from the user's calendar by its ID.
    """
    try:
        # Authentication code is the same as previous functions
        creds = Credentials.from_authorized_user_info(
            info={
                'refresh_token': user_refresh_token,
                'client_id': GOOGLE_CLIENT_ID,
                'client_secret': GOOGLE_CLIENT_SECRET
            },
            scopes=SCOPES
        )

        service = build('calendar', 'v3', credentials=creds)

        # Call the Google API to delete the event
        service.events().delete(
            calendarId='primary', 
            eventId=event_id
        ).execute()

        print(f"Successfully deleted event with ID: {event_id}")
        return True # Return True on success

    except Exception as e:
        print(f"An error occurred in delete_event: {e}")
        return False # Return False on failure
    

def delete_event_at_time(user_refresh_token, target_datetime):
    """
    Finds and deletes a single event that starts at the exact target_datetime.
    """
    try:
        # --- התיקון האמיתי: שימוש בשיטת האימות הנכונה ---
        creds = Credentials.from_authorized_user_info(
            info={
                'refresh_token': user_refresh_token,
                'client_id': GOOGLE_CLIENT_ID,
                'client_secret': GOOGLE_CLIENT_SECRET
            },
            scopes=SCOPES
        )
        service = build('calendar', 'v3', credentials=creds)
        # --- סוף התיקון ---

        # --- ⭐️ התיקון הקריטי: הוספת אזור זמן ⭐️ ---
        # ה-LLM שולח לנו זמן "נאיבי" (בלי אזור). אנחנו נהפוך אותו ל"מודע".
        local_tz = ZoneInfo("Asia/Jerusalem")
        aware_target_datetime = target_datetime.replace(tzinfo=local_tz)
        
        # עכשיו ה-ISO format יכלול את האופסט הנכון (למשל +02:00)
        time_min = aware_target_datetime.isoformat()
        # אנחנו עדיין מחפשים בטווח של דקה אחת
        time_max = (aware_target_datetime + timedelta(minutes=1)).isoformat()
        # --- סוף תיקון אזור הזמן ---

        print(f"--- Searching for event to delete between {time_min} and {time_max} ---", flush=True)

        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            maxResults=2,  # אנחנו צריכים לדעת רק אם יש 0, 1, או יותר מ-1
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])

        if not events:
            print("--- No events found to delete ---", flush=True)
            return "מצטער, לא מצאתי שום אירוע למחוק בשעה המדויקת שציינת."
        
        if len(events) > 1:
            print(f"--- Found {len(events)} events, too ambiguous ---", flush=True)
            return "אופס, מצאתי יותר מאירוע אחד בשעה הזו. אני עוד לא יודע איך לבקש ממך לבחור."
        
        # הצלחה! מצאנו בדיוק אירוע אחד
        event_to_delete = events[0]
        event_id = event_to_delete['id']
        event_summary = event_to_delete.get('summary', 'ללא כותרת')

        print(f"--- Deleting event: {event_summary} (ID: {event_id}) ---", flush=True)

        service.events().delete(
            calendarId='primary',
            eventId=event_id
        ).execute()

        return f"מחקתי! האירוע '{event_summary}' בוטל."

    except Exception as e:
        print(f"Error in delete_event_at_time: {e}", flush=True)
        return "אירעה שגיאה בזמן ניסיון המחיקה. אולי פג התוקף של ההרשאה שלך?"