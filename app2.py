# app.py (גרסה 17.0 - הגרסה השלמה והנקייה)

import os
import json
import re
import requests
from flask import Flask, request, redirect, session, url_for
from dotenv import load_dotenv
from datetime import datetime, time, timedelta

# --- ייבואים מהקבצים שלנו ---
# ודא שהקבצים האלה קיימים באותה תיקייה
from database_handler import add_user, get_user_token
from google_calendar_handler import create_event_for_user

# --- ייבואים לתהליך האימות של גוגל ---
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# --- טעינת משתני הסביבה ---
load_dotenv()
APP_VERIFY_TOKEN = os.getenv('META_VERIFY_TOKEN')
APP_ACCESS_TOKEN = os.getenv('META_ACCESS_TOKEN')
PHONE_NUMBER_ID = os.getenv('META_PHONE_NUMBER_ID')

# הגדרות לתהליך האימות של גוגל
CLIENT_SECRET_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/userinfo.profile']

# --- אתחול השרת ---
app = Flask(__name__)
app.secret_key = os.urandom(24) # חיוני לאבטחת סשנים

# --- פונקציות עזר קבועות ---
def parse_whatsapp_message(data):
    try:
        message_object = data['entry'][0]['changes'][0]['value']['messages'][0]
        message_text = message_object['text']['body']
        sender_phone_number = message_object['from']
        return sender_phone_number, message_text
    except (KeyError, IndexError):
        return None, None

def send_whatsapp_message1(to_phone_number, message):
    headers = {
        "Authorization": f"Bearer {APP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    data = { "messaging_product": "whatsapp", "to": to_phone_number, "text": {"body": message} }
    print(f"--- Sending WhatsApp Message to {to_phone_number} ---")
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        print(f"Meta API Response: Status={response.status_code}, Body={response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending WhatsApp message: {e}")

def send_whatsapp_message(to_phone_number, message):
    """
    בזמן הפיתוח המקומי, הפונקציה הזו רק מדפיסה את ההודעה לטרמינל
    במקום באמת לשלוח אותה לוואטסאפ.
    """
    print("\n" + "="*50)
    print(f"--- SIMULATED WHATSAPP MESSAGE ---")
    print(f"TO: {to_phone_number}")
    print(f"MESSAGE:\n{message}")
    print("="*50 + "\n")

# --- מנוע פיענוח מבוסס חוקים (הגרסה היציבה) ---
def parse_datetime_and_title(text):
    now = datetime.now()
    original_text = text
    date_obj, extracted_time, date_string_found, time_string_found = None, None, "", ""

    time_pattern = r'\b(ב-?\s*)?([0-2]?[0-9])(:([0-5][0-9]))?\b'
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
    if time_string_found: event_title = event_title.replace(time_string_found, '', 1)
    if date_string_found: event_title = event_title.replace(date_string_found, '', 1)
    stop_words = ['בבוקר', 'בערב', 'בצהריים', 'בלילה']
    for word in stop_words: event_title = event_title.replace(word, '')
    event_title = re.sub(r'\s+', ' ', event_title).strip()
    if not event_title: event_title = "אירוע ללא כותרת"

    return final_datetime, event_title

# --- [חדש] עמודי האינטרנט לתהליך ההרשמה (עם דיבאג) ---

@app.route('/auth')
def register():
    """העמוד שאליו הקישור מהוואטסאפ מוביל."""
    print("\n--- [DEBUG] Reached /register route ---")
    wa_id = request.args.get('wa_id')
    print(f"[DEBUG] wa_id from URL: {wa_id}")

    if not wa_id:
        return "<h1>Error: Missing wa_id in URL. Please use the full link from the terminal.</h1>", 400

    session['whatsapp_id'] = wa_id
    print(f"[DEBUG] whatsapp_id saved to session: {session['whatsapp_id']}")

    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri=url_for('oauth2callback', _external=True)
        )
        authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
        
        session['state'] = state
        print(f"[DEBUG] Redirecting to Google URL: {authorization_url}")
        return redirect(authorization_url)
    except Exception as e:
        print(f"[DEBUG] ERROR during flow creation: {e}")
        return f"<h1>An error occurred: {e}</h1>", 500

@app.route('/oauth2callback')
def oauth2callback():
    """העמוד שאליו גוגל מחזיר את המשתמש אחרי שהוא מאשר."""
    print("\n--- [DEBUG] Reached /oauth2callback route ---")
    
    # ודא שה-state שהגיע מגוגל תואם לזה ששמרנו
    if 'state' not in session or session['state'] != request.args['state']:
        return "<h1>State mismatch error. Please try again.</h1>", 400
    state = session['state']
    
    flow = Flow.from_client_secrets_file(CLIENT_SECRET_FILE, scopes=SCOPES, state=state, redirect_uri=url_for('oauth2callback', _external=True))
    
    try:
        flow.fetch_token(authorization_response=request.url)
        
        credentials = flow.credentials
        refresh_token = credentials.refresh_token
        
        whatsapp_id = session.get('whatsapp_id')
        print(f"[DEBUG] whatsapp_id retrieved from session: {whatsapp_id}")

        if not whatsapp_id or not refresh_token:
            return "<h1>Error: Could not retrieve user details or refresh token. Please try again.</h1>", 400

        user_info_service = build('oauth2', 'v2', credentials=credentials)
        user_info = user_info_service.userinfo().get().execute()
        user_name = user_info.get('name', 'User')
        
        add_user(whatsapp_id, refresh_token, user_name)
        
        return "<h1>החיבור הושלם בהצלחה!</h1><p>אפשר לסגור את הדף ולחזור לוואטסאפ.</p>"
    except Exception as e:
        print(f"[DEBUG] ERROR during token fetch: {e}")
        return f"<h1>An error occurred during token fetch: {e}</h1>", 500

@app.route('/test')
def test_route():
    print("\n--- [SUCCESS] Reached the /test route! ---\n")
    return "<h1>It works! The server is reachable from the browser.</h1>"
# --- Webhook ראשי ---
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
            if not request.args.get("hub.verify_token") == APP_VERIFY_TOKEN: return "Verification token mismatch", 403
            return request.args.get("hub.challenge"), 200
        return "Hello World", 200

    elif request.method == 'POST':
        data = request.get_json()
        sender_phone, message_text = parse_whatsapp_message(data)
        
        if sender_phone and message_text:
            user_token = get_user_token(sender_phone)
            
            if user_token:
                print(f"Known user: {sender_phone}. Processing message.")
                result = parse_datetime_and_title(message_text)
                if result:
                    start_datetime, event_title = result
                    end_datetime = start_datetime + timedelta(hours=1)
                    start_iso = start_datetime.isoformat()
                    end_iso = end_datetime.isoformat()
                    
                    event_link = create_event_for_user(user_token, event_title, start_iso, end_iso)
                    
                    confirmation_message = f"בסדר, קבעתי!\nאירוע: {event_title}\nבתאריך: {start_datetime.strftime('%d/%m/%Y')} בשעה {start_datetime.strftime('%H:%M')}\n\nקישור: {event_link}"
                    send_whatsapp_message(sender_phone, confirmation_message)
                else:
                    error_message = "מצטער, לא הצלחתי להבין את התאריך והשעה בהודעה שלך."
                    send_whatsapp_message(sender_phone, error_message)
            else:
                print(f"New user: {sender_phone}. Sending registration link.")
                registration_link = f"http://127.0.0.1:5000/auth?wa_id={sender_phone}"
                message = f"שלום! נראה שזו הפעם הראשונה שלך כאן. כדי שאוכל ליצור עבורך אירועים, יש לחבר את יומן גוגל שלך דרך הקישור הבא:\n\n{registration_link}"
                send_whatsapp_message(sender_phone, message)
        
        return 'OK', 200
    return 'Unsupported method', 405

if __name__ == '__main__':
    app.run(debug=True, port=5000)