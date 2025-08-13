import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']

def create_event_for_user(user_refresh_token, summary, start_time, end_time):
    try:
        creds = Credentials.from_authorized_user_info(
            info={
                'refresh_token': user_refresh_token,
                'client_id': os.getenv('GOOGLE_CLIENT_ID'),
                'client_secret': os.getenv('GOOGLE_CLIENT_SECRET')
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
        return created_event.get('htmlLink')
    except Exception as e:
        print(f"An error occurred in Google Calendar Handler: {e}")
        return f"An error occurred: {e}"