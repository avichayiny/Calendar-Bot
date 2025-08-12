# google_calendar_handler.py (גרסת משתמשים מרובים)

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']
# חשוב: קובץ זה חייב להיות קיים בתיקייה
CLIENT_SECRET_FILE = 'credentials.json' 

def create_event_for_user(user_refresh_token, summary, start_time, end_time):
    """
    יוצר אירוע ביומן עבור משתמש ספציפי באמצעות ה-refresh_token שלו.
    """
    if not user_refresh_token:
        return "Error: No refresh token provided."

    try:
        # יוצרים אובייקט Credentials מה-refresh_token
        creds = Credentials.from_authorized_user_info(
            info={'refresh_token': user_refresh_token},
            scopes=SCOPES
        )
        # טוענים את סודות הלקוח שלנו כדי שהרענון יוכל לעבוד
        creds.with_client_secrets_file = CLIENT_SECRET_FILE

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