# app.py (גרסה 20.0 - הגרסה המאוחדת והסופית)

import os
import json
import re
import requests
from flask import Flask, request, redirect, session, url_for
from dotenv import load_dotenv
from datetime import datetime, time, timedelta

# --- ייבואים מהקבצים שלנו ---
from database_handler import add_user, get_user_token
from google_calendar_handler import create_event_for_user

# --- ייבואים לתהליך האימות של גוגל ---
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# --- ייבוא ספריית Twilio ---
from twilio.rest import Client

# --- טעינת משתני הסביבה ---
load_dotenv()
# Twilio Credentials
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
# Google Credentials for Render
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/userinfo.profile']

# --- אתחול השרת ---
app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- פונקציות עזר ---
def parse_twilio_message(incoming_data):
    try:
        message_text = incoming_data.get('Body')
        # הפורמט של מספר השולח מ-Twilio הוא 'whatsapp:+972...'
        sender_phone_number = incoming_data.get('From')
        return sender_phone_number, message_text
    except Exception:
        return None, None

def send_whatsapp_message(to_phone_number, message):
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(
            from_=TWILIO_PHONE_NUMBER,
            body=message,
            to=to_phone_number
        )
        print(f"--- Successfully sent Twilio message to {to_phone_number} ---")
    except Exception as e:
        print(f"Error sending Twilio message: {e}")

# --- מנוע פיענוח (הגרסה היציבה) ---
def parse_datetime_and_title(text):
    now = datetime.now()
    original_text = text
    date_obj, extracted_time, date_string_found, time_string_found = None, None, "", ""

    time_pattern = r'\b(ב-?\s*)?(\d{1,2})(:(\d{2}))?\b'
    time_matches = [m for m in re.finditer(time_pattern, text) if 0 <= int(m.group(2)) <= 23]
    if time_matches:
        time_match = time_matches[-1]
        hour = int(time_match.group(2))
        minute = int(time_match.group(4)) if time_match.group(4) else 0
        extracted_time = time(hour, minute)
        time_string_found = time_match.group(0)
    else:
        extracted_time = time(9, 0)

    months_he = "ינואר|פברואר|מרץ|אפריל|מאי|יוני|יולי|אוגוסט|ספטמבר|אוקטובר|נובמבר|דצמבר"
    full_date_pattern = rf'\b(ב|ל)?(\d{{1,2}})\s+(?:ב|ל)?({months_he})\b'
    full_date_match = re.search(full_date_pattern, text)
    if full_date_match:
        day = int(full_date_match.group(2)); month_str = full_date_match.group(3)
        month_map = {'ינואר': 1, 'פברואר': 2, 'מרץ': 3, 'אפריל': 4, 'מאי': 5, 'יוני': 6, 'יולי': 7, 'אוגוסט': 8, 'ספטמבר': 9, 'אוקטובר': 10, 'נובמבר': 11, 'דצמבר': 12}
        month = month_map[month_str]; year = now.year
        if datetime(year, month, day, 23, 59) < now: year += 1
        date_obj = datetime(year, month, day).date()
        date_string_found = full_date_match.group(0)
    else:
        relative_match = re.search(r'\b(מחרתיים|מחר)\b', text)
        if relative_match:
            relative_word = relative_match.group(0)
            if relative_word == "מחר": date_obj = (now + timedelta(days=1)).date()
            else: date_obj = (now + timedelta(days=2)).date()
            date_string_found = relative_word
        else:
            weekdays_he = "ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת"
            weekday_pattern = rf'\b(ביום\s+|ב)?({weekdays_he})\b'
            weekday_match = re.search(weekday_pattern, text)
            if weekday_match:
                day_str = weekday_match.group(2)
                weekday_map = {'ראשון': 6, 'שני': 0, 'שלישי': 1, 'רביעי': 2, 'חמישי': 3, 'שישי': 4, 'שבת': 5}
                target_weekday = weekday_map[day_str]
                days_ahead = (target_weekday - now.weekday() + 7) % 7
                if days_ahead == 0: days_ahead = 7
                date_obj = (now + timedelta(days=days_ahead)).date()
                date_string_found = weekday_match.group(0)

    if not date_obj: date_obj = now.date()
    final_datetime = datetime.combine(date_obj, extracted_time)

    event_title = original_text
    parts_to_remove = []
    if time_string_found: parts_to_remove.append(time_string_found)
    if date_string_found: parts_to_remove.append(date_string_found)
    parts_to_remove.sort(key=len, reverse=True)
    for part in parts_to_remove:
        event_title = event_title.replace(part, '', 1)

    stop_words = ['בבוקר', 'בערב', 'בצהריים', 'בלילה', 'ביום']
    for word in stop_words: event_title = event_title.replace(word, '')
    
    event_title = re.sub(r'\s+', ' ', event_title).strip()
    if not event_title: event_title = "אירוע ללא כותרת"

    return final_datetime, event_title

# --- עמודי האינטרנט לתהליך ההרשמה ---
@app.route('/register')
def register():
    wa_id = request.args.get('wa_id')
    if not wa_id: return "<h1>שגיאה: מספר וואטסאפ חסר.</h1>", 400
    auth_link = url_for('start_auth', wa_id=wa_id, _external=True)
    return f"""
    <!DOCTYPE html><html lang="he" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>אישור חיבור</title>
    <style>body{{font-family:Arial,sans-serif;text-align:center;padding:50px;}} a{{display:inline-block;padding:15px 25px;font-size:18px;color:white;background-color:#4285F4;text-decoration:none;border-radius:5px;}}</style>
    </head><body><h1>כמעט סיימנו!</h1><p>כדי לחבר את יומן גוגל שלך, לחץ על הכפתור למטה:</p><a href="{auth_link}">התחבר עם גוגל</a></body></html>
    """

@app.route('/start-auth')
def start_auth():
    session['whatsapp_id'] = request.args.get('wa_id')
    flow = Flow.from_client_config(
        client_config={ "web": { "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET, "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token" }},
        scopes=SCOPES, redirect_uri=url_for('oauth2callback', _external=True)
    )
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true', prompt='consent')
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    state = session['state']
    flow = Flow.from_client_config(
        client_config={ "web": { "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET, "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token" }},
        scopes=SCOPES, state=state, redirect_uri=url_for('oauth2callback', _external=True)
    )
    try:
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        if not credentials or not credentials.refresh_token:
            return "<h1>שגיאה: לא התקבל מפתח רענון מגוגל. נסה שוב.</h1>", 400
        
        refresh_token = credentials.refresh_token
        whatsapp_id = session['whatsapp_id']
        user_info_service = build('oauth2', 'v2', credentials=credentials)
        user_info = user_info_service.userinfo().get().execute()
        user_name = user_info.get('name', 'User')
        add_user(whatsapp_id, refresh_token, user_name)
        return "<h1>החיבור הושלם בהצלחה!</h1><p>אפשר לסגור את הדף ולחזור לוואטסאפ.</p>"
    except Exception as e:
        print(f"Error in oauth2callback: {e}")
        return "<h1>אירעה שגיאה בתהליך האימות.</h1>", 500

# --- Webhook ראשי ---
@app.route('/webhook', methods=['POST'])
def webhook():
    incoming_data = request.values
    sender_phone, message_text = parse_twilio_message(incoming_data)
    
    if sender_phone and message_text:
        user_token = get_user_token(sender_phone)
        
        if user_token:
            print(f"Known user: {sender_phone}. Processing message.")
            result = parse_datetime_and_title(message_text)
            if result:
                start_datetime, event_title = result
                end_datetime = start_datetime + timedelta(hours=1)
                event_link = create_event_for_user(user_token, event_title, start_datetime.isoformat(), end_datetime.isoformat())
                confirmation_message = f"בסדר, קבעתי!\nאירוע: {event_title}\nבתאריך: {start_datetime.strftime('%d/%m/%Y')} בשעה {start_datetime.strftime('%H:%M')}\n\nקישור: {event_link}"
                send_whatsapp_message(sender_phone, confirmation_message)
            else:
                error_message = "מצטער, לא הצלחתי להבין את התאריך והשעה."
                send_whatsapp_message(sender_phone, error_message)
        else:
            print(f"New user: {sender_phone}. Sending registration link.")
            registration_link = url_for('register', wa_id=sender_phone, _external=True)
            message = f"שלום! כדי שאוכל ליצור עבורך אירועים, יש לחבר את יומן גוגל שלך דרך הקישור הבא:\n\n{registration_link}"
            send_whatsapp_message(sender_phone, message)
    
    return 'OK', 200

# --- נתיב לאיפוס בסיס הנתונים ---
@app.route('/reset-database-for-testing')
def reset_database():
    db_file = "bot_database.db"
    if os.path.exists(db_file):
        os.remove(db_file)
    import sqlite3
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        whatsapp_id TEXT PRIMARY KEY, google_refresh_token TEXT NOT NULL,
        user_name TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit(); conn.close()
    return "<h1>Database has been reset successfully!</h1>"

if __name__ == '__main__':
    app.run(debug=True, port=5000)
