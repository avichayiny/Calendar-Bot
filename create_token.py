# create_token.py

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import os.path

# הגדרת ההרשאות שאנו מבקשים. במקרה שלנו, גישה מלאה ליומן.
SCOPES = ['https://www.googleapis.com/auth/calendar']

def main():
    creds = None
    # הקובץ token.json שומר את הרשאות הגישה של המשתמש.
    # הוא נוצר אוטומטית בסיום תהליך ההתחברות הראשון.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # אם אין הרשאות (או שהן פגות תוקף), בצע תהליך התחברות חדש.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # טען את ה-credentials.json שהורדנו מגוגל
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            # הרץ תהליך אימות שיפתח דפדפן ויבקש אישור
            creds = flow.run_local_server(port=0)

        # שמור את ההרשאות לקראת ההרצה הבאה
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    print("Successfully created or updated token.json!")

if __name__ == '__main__':
    main()