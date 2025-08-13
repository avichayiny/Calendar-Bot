# app.py (גרסה 19.0 - Twilio Edition)

import os
from flask import Flask, request, redirect, session, url_for
from dotenv import load_dotenv
import re
from datetime import datetime, time, timedelta

# --- ייבואים מהקבצים שלנו ---
from database_handler import add_user, get_user_token
from google_calendar_handler import create_event_for_user

# --- ייבואים לתהליך האימות של גוגל ---
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# --- [חדש] ייבוא ספריית Twilio ---
from twilio.rest import Client

# --- טעינת משתני הסביבה ---
load_dotenv()
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

# הגדרות לתהליך האימות של גוגל
CLIENT_SECRET_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/userinfo.profile']

# --- אתחול השרת ---
app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- [חדש] פונקציות עזר מותאמות ל-Twilio ---
def parse_twilio_message(incoming_data):
    try:
        message_text = incoming_data.get('Body')
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

# --- מנוע פיענוח (הגרסה היציבה שלנו - ללא שינוי) ---
def parse_datetime_and_title(text):
    # ... כל הקוד של הפונקציה הזו נשאר זהה לחלוטין ...
    now = datetime.now(); original_text = text
    date_obj, extracted_time, date_string_found, time_string_found = None, None, "", ""
    time_pattern = r'\b(ב-?\s*)?(\d{1,2})(:(\d{2}))?\b'
    time_matches = [m for m in re.finditer(time_pattern, text) if 0 <= int(m.group(2)) <= 23]
    if time_matches:
        time_match = time_matches[-1]; hour = int(time_match.group(2)); minute = int(time_match.group(4)) if time_match.group(4) else 0
        extracted_time = time(hour, minute); time_string_found = time_match.group(0)
    else: extracted_time = time(9, 0)
    months_he = "ינואר|פברואר|מרץ|אפריל|מאי|יוני|יולי|אוגוסט|ספטמבר|אוקטובר|נובמבר|דצמבר"
    full_date_pattern = rf'\b(ב|ל)?(\d{{1,2}})\s+(?:ב|ל)?({months_he})\b'
    full_date_match = re.search(full_date_pattern, text)
    if full_date_match:
        day = int(full_date_match.group(2)); month_str = full_date_match.group(3)
        month_map = {'ינואר': 1, 'פברואר': 2, 'מרץ': 3, 'אפריל': 4, 'מאי': 5, 'יוני': 6, 'יולי': 7, 'אוגוסט': 8, 'ספטמבר': 9, 'אוקטובר': 10, 'נובמבר': 11, 'דצמבר': 12}
        month = month_map[month_str]; year = now.year
        if datetime(year, month, day, 23, 59) < now: year += 1
        date_obj = datetime(year, month, day).date(); date_string_found = full_date_match.group(0)
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
                target_weekday = weekday_map[day_str]; days_ahead = (target_weekday - now.weekday() + 7) % 7
                if days_ahead == 0: days_ahead = 7
                date_obj = (now + timedelta(days=days_ahead)).date(); date_string_found = weekday_match.group(0)
    if not date_obj: date_obj = now.date()
    final_datetime = datetime.combine(date_obj, extracted_time)
    event_title = original_text
    if time_string_found: event_title = event_title.replace(time_string_found, '', 1)
    if date_string_found: event_title = event_title.replace(date_string_found, '', 1)
    stop_words = ['בבוקר', 'בערב', 'בצהריים', 'בלילה']
    for word in stop_words: event_title = event_title.replace(word, '')
    event_title = re.sub(r'\s+', ' ', event_title).strip()
    if not event_title: event_title = "אירוע ללא כותרת"
    return final_datetime, event_title

# --- עמודי האינטרנט לתהליך ההרשמה (ללא שינוי) ---
@app.route('/register')
def register():
    session['whatsapp_id'] = request.args.get('wa_id')
    
    # [תיקון] יוצרים את ה-Flow ממשתני הסביבה
    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": os.getenv('GOOGLE_CLIENT_ID'),
                "client_secret": os.getenv('GOOGLE_CLIENT_SECRET'),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": [url_for('oauth2callback', _external=True)],
            }
        },
        scopes=SCOPES,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    state = session['state']
    
    # [תיקון] יוצרים את ה-Flow ממשתני הסביבה
    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": os.getenv('GOOGLE_CLIENT_ID'),
                "client_secret": os.getenv('GOOGLE_CLIENT_SECRET'),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    refresh_token = credentials.refresh_token
    whatsapp_id = session['whatsapp_id']
    user_info_service = build('oauth2', 'v2', credentials=credentials)
    user_info = user_info_service.userinfo().get().execute()
    user_name = user_info.get('name', 'User')
    add_user(whatsapp_id, refresh_token, user_name)
    return "<h1>החיבור הושלם בהצלחה!</h1><p>אפשר לסגור את הדף ולחזור לוואטסאפ.</p>"
# --- [חדש] Webhook ראשי מותאם ל-Twilio ---
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

# --- [חדש] נתיב סודי לאיפוס בסיס הנתונים לצורכי בדיקה ---
@app.route('/reset-database-for-testing')
def reset_database():
    db_file = "bot_database.db"
    if os.path.exists(db_file):
        os.remove(db_file)
        print("--- Database file removed. ---")
    
    # מריצים מחדש את הלוגיקה של database_setup.py
    import sqlite3
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        whatsapp_id TEXT PRIMARY KEY,
        google_refresh_token TEXT NOT NULL,
        user_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()
    print("--- New database file created. ---")
    
    return "<h1>Database has been reset successfully!</h1>"

if __name__ == '__main__':
    app.run(debug=True, port=5000)