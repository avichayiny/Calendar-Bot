# app.py (גרסה 22.0 - הגרסה המאוחדת והסופית עבור מטא)

import os
import json
import re
import requests
from flask import Flask, request, redirect, session, url_for
from dotenv import load_dotenv
from datetime import datetime, time, timedelta

# --- ייבואים מהקבצים שלנו ---
from database_handler import add_user, get_user_token
from google_calendar_handler import create_event_for_user, get_events_for_day, delete_event

# --- ייבואים לתהליך האימות של גוגל ---
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# --- טעינת משתני הסביבה (מותאם למטא) ---
load_dotenv()
APP_VERIFY_TOKEN = os.getenv('META_VERIFY_TOKEN')
APP_ACCESS_TOKEN = os.getenv('META_ACCESS_TOKEN')
PHONE_NUMBER_ID = os.getenv('META_PHONE_NUMBER_ID')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/userinfo.profile']

# --- אתחול השרת ---
app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- [שדרוג] פונקציות עזר מותאמות למטא ---
def parse_whatsapp_message(data):
    """מנתח את מבנה ההודעה הנכנסת מה-API של מטא."""
    try:
        entry = data['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']
        message_object = value['messages'][0]
        
        message_text = message_object['text']['body']
        sender_phone_number = message_object['from'] # מספר השולח במטא
        
        return sender_phone_number, message_text
    except (KeyError, IndexError):
        return None, None

def send_whatsapp_message(to_phone_number, message):
    """שולח הודעת וואטסאפ דרך ה-API של מטא."""
    headers = {
        "Authorization": f"Bearer {APP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    data = { "messaging_product": "whatsapp", "to": to_phone_number, "text": {"body": message} }
    print(f"--- Sending WhatsApp Message via Meta to {to_phone_number} ---")
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        print(f"Meta API Response: Status={response.status_code}, Body={response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending WhatsApp message: {e}")

# --- מנוע פיענוח (הגרסה היציבה שלנו - ללא שינוי) ---
def parse_datetime_and_title(text):
    now = datetime.now()
    original_text = text
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
    parts_to_remove = []
    if time_string_found: parts_to_remove.append(time_string_found)
    if date_string_found: parts_to_remove.append(date_string_found)
    parts_to_remove.sort(key=len, reverse=True)
    for part in parts_to_remove: event_title = event_title.replace(part, '', 1)

    stop_words = ['בבוקר', 'בערב', 'בצהריים', 'בלילה', 'ביום']
    for word in stop_words: event_title = event_title.replace(word, '')
    
    event_title = re.sub(r'\s+', ' ', event_title).strip()
    if not event_title: event_title = "אירוע ללא כותרת"
    return final_datetime, event_title

# --- עמודי האינטרנט לתהליך ההרשמה (ללא שינוי) ---
@app.route('/register')
def register():
    # ... תוכן הפונקציה נשאר זהה ...
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
    # ... תוכן הפונקציה נשאר זהה ...
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
    # ... תוכן הפונקציה נשאר זהה ...
    state = session['state']
    flow = Flow.from_client_config(
        client_config={ "web": { "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET, "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token" }},
        scopes=SCOPES, state=state, redirect_uri=url_for('oauth2callback', _external=True)
    )
    try:
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        if not credentials or not credentials.refresh_token: return "<h1>שגיאה: לא התקבל מפתח רענון מגוגל.</h1>", 400
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

# --- Webhook ראשי עם זיהוי כוונות משולש (יצירה, שאילתה, מחיקה) ---
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # אימות ה-Webhook מול מטא
    if request.method == 'GET':
        if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
            if not request.args.get("hub.verify_token") == APP_VERIFY_TOKEN: return "Verification token mismatch", 403
            return request.args.get("hub.challenge"), 200
        return "Hello World", 200

    # קבלת הודעות חדשות
    elif request.method == 'POST':
        data = request.get_json()
        sender_phone, message_text = parse_whatsapp_message(data)

        if sender_phone and message_text:
            user_token = get_user_token(sender_phone)

            if user_token:
                print(f"Known user: {sender_phone}. Processing message: '{message_text}'")

                # --- [השדרוג] זיהוי כוונת המשתמש ---
                query_keywords = ['מה יש לי', 'מה הלוז', 'האם אני פנוי', 'מה יש']
                delete_keywords = ['מחק', 'בטל', 'הסר']
                
                is_query = any(keyword in message_text for keyword in query_keywords)
                is_delete = any(keyword in message_text for keyword in delete_keywords)

                if is_query:
                    # --- לוגיקה קיימת: טיפול בשאילתה ---
                    print("User intent: Query calendar")
                    result = parse_datetime_and_title(message_text)
                    target_datetime = result[0] if result else datetime.now()
                    events = get_events_for_day(user_token, target_datetime.date())

                    if events is None:
                        response_message = "אירעה שגיאה בבדיקת היומן שלך."
                    elif not events:
                        response_message = f"אתה פנוי לגמרי ב-{target_datetime.strftime('%d/%m/%Y')}! אין לך אירועים ביומן."
                    else:
                        response_message = f"הנה הלו\"ז שלך ל-{target_datetime.strftime('%d/%m/%Y')}:\n"
                        for event in events:
                            start = event['start'].get('dateTime', event['start'].get('date'))
                            start_time_obj = datetime.fromisoformat(start.replace('Z', '+00:00'))
                            start_time_str = start_time_obj.strftime('%H:%M')
                            response_message += f"\n- {start_time_str}: {event['summary']}"
                    
                    send_whatsapp_message(sender_phone, response_message)

                elif is_delete:
                    # --- [חדש] לוגיקה לטיפול בבקשת מחיקה ---
                    print("User intent: Delete event")
                    result = parse_datetime_and_title(message_text)
                    
                    if result:
                        target_datetime, event_keywords = result
                        events = get_events_for_day(user_token, target_datetime.date())
                        
                        event_to_delete = None
                        if events:
                            # נחפש אירוע שתואם לפרטים
                            for event in events:
                                start = event['start'].get('dateTime', event['start'].get('date'))
                                start_time_obj = datetime.fromisoformat(start.replace('Z', '+00:00'))
                                
                                time_difference = abs((start_time_obj - target_datetime).total_seconds())
                                title_match = event_keywords.lower() in event['summary'].lower()

                                # אם יש התאמה גם בשעה וגם בכותרת (או רק אחד מהם אם השני לא צוין)
                                if time_difference < 3600 or (not event_keywords and time_difference < 60):
                                    if not event_keywords or title_match:
                                        event_to_delete = event
                                        break
                        
                        if event_to_delete:
                            success = delete_event(user_token, event_to_delete['id'])
                            if success:
                                response_message = f"האירוע '{event_to_delete['summary']}' נמחק בהצלחה."
                            else:
                                response_message = "אירעה שגיאה במחיקת האירוע."
                        else:
                            response_message = "מצטער, לא מצאתי אירוע שתואם לתיאור שלך."
                    else:
                        response_message = "לא הבנתי איזה אירוע למחוק. נסה לציין תאריך ומילת מפתח מהכותרת."
                    
                    send_whatsapp_message(sender_phone, response_message)

                else:
                    # --- לוגיקה קיימת: יצירת אירוע חדש ---
                    print("User intent: Create event")
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
                # לוגיקת משתמש חדש (נשארת זהה)
                print(f"New user: {sender_phone}. Sending registration link.")
                registration_link = url_for('register', wa_id=sender_phone, _external=True)
                message = f"שלום! כדי שאוכל ליצור עבורך אירועים, יש לחבר את יומן גוגל שלך דרך הקישור הבא:\n\n{registration_link}"
                send_whatsapp_message(sender_phone, message)

        return 'OK', 200
    return 'Unsupported method', 405

# --- נתיב לאיפוס בסיס הנתונים ---
@app.route('/reset-database-for-testing')
def reset_database():
    db_file = "bot_database.db"
    if os.path.exists(db_file): os.remove(db_file)
    import sqlite3
    conn = sqlite3.connect(db_file); cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        whatsapp_id TEXT PRIMARY KEY, google_refresh_token TEXT NOT NULL,
        user_name TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit(); conn.close()
    return "<h1>Database has been reset successfully!</h1>"

if __name__ == '__main__':
    app.run(debug=True, port=5000)


