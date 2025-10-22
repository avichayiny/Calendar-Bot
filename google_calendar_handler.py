# google_calendar_handler.py

import os
import json
from datetime import datetime, time
from google.oauth2.credentials import Credentials # <-- Necessary import
from googleapiclient.discovery import build

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