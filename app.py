# app.py (גרסה 10.2 - תיקונים נקודתיים)

import os
import json
import requests
import re
from flask import Flask, request
from dotenv import load_dotenv
from google_calendar_handler import create_google_calendar_event
from dateparser.search import search_dates
from datetime import datetime, time, timedelta
# הוסף את השורות האלה יחד עם שאר ה-imports
from flask import redirect, session, url_for

# ייבוא הקבצים החדשים והמעודכנים שלנו
from database_handler import add_user, get_user_token
# שנה את השם של הפונקציה הישנה כדי שיתאים לקובץ המעודכן
from google_calendar_handler import create_event_for_user 

# ייבואים חדשים לתהליך האימות של גוגל
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# --- טעינת משתני הסביבה ---
load_dotenv()
# הגדרות חדשות
CLIENT_SECRET_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/userinfo.profile']
APP_VERIFY_TOKEN = os.getenv('META_VERIFY_TOKEN')
APP_ACCESS_TOKEN = os.getenv('META_ACCESS_TOKEN')
PHONE_NUMBER_ID = os.getenv('META_PHONE_NUMBER_ID')

# --- פונקציות עזר קבועות ---
def parse_whatsapp_message(data):
    try:
        message_object = data['entry'][0]['changes'][0]['value']['messages'][0]
        message_text = message_object['text']['body']
        sender_phone_number = message_object['from']
        return sender_phone_number, message_text
    except (KeyError, IndexError):
        return None, None

def send_whatsapp_message(to_phone_number, message):
    headers = {
        "Authorization": f"Bearer {APP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    data = {
        "messaging_product": "whatsapp",
        "to": to_phone_number,
        "text": {"body": message}
    }
    print(f"--- Sending WhatsApp Message to {to_phone_number} ---")
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status() # יזרוק שגיאה אם הבקשה נכשלה (סטטוס 4xx או 5xx)
        print(f"Meta API Response: Status={response.status_code}, Body={response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending WhatsApp message: {e}")

# --- [הליבה הסופית] מנוע פיענוח מבוסס חוקים (גרסה 16.2 - תיקון כפילויות) ---
def parse_datetime_and_title(text):
    now = datetime.now()
    original_text = text
    
    date_obj = None
    extracted_time = None
    date_string_found = ""
    time_string_found = ""

    # --- חלק 1: "צייד השעות" (יציב) ---
    time_pattern = r'\b(ב-?\s*)?(\d{1,2})(:(\d{2}))?\b'
    time_matches = [m for m in re.finditer(time_pattern, text) if 0 <= int(m.group(2)) <= 23]
    if time_matches:
        time_match = time_matches[-1]
        hour = int(time_match.group(2))
        minute = int(time_match.group(4)) if time_match.group(4) else 0
        extracted_time = time(hour, minute)
        time_string_found = time_match.group(0)
        print(f"Time Hunter Found: '{time_string_found}' -> {extracted_time}")
    else:
        extracted_time = time(9, 0)

    # --- חלק 2: "צייד התאריכים" עם סדר עדיפויות ---
    
    # עדיפות 1: תאריך מלא ("17 באוגוסט")
    months_he = "ינואר|פברואר|מרץ|אפריל|מאי|יוני|יולי|אוגוסט|ספטמבר|אוקטובר|נובמבר|דצמבר"
    full_date_pattern = rf'\b(ב|ל)?(\d{{1,2}})\s+(?:ב|ל)?({months_he})\b'
    full_date_match = re.search(full_date_pattern, text)
    if full_date_match:
        day = int(full_date_match.group(2))
        month_str = full_date_match.group(3)
        month_map = {'ינואר': 1, 'פברואר': 2, 'מרץ': 3, 'אפריל': 4, 'מאי': 5, 'יוני': 6, 'יולי': 7, 'אוגוסט': 8, 'ספטמבר': 9, 'אוקטובר': 10, 'נובמבר': 11, 'דצמבר': 12}
        month = month_map[month_str]
        year = now.year
        if datetime(year, month, day, 23, 59) < now: year += 1
        date_obj = datetime(year, month, day).date()
        date_string_found = full_date_match.group(0)
        print(f"Rule Matched: Full Date -> {date_obj}")
    
    # עדיפות 2: יחסי ("מחר", "10 לחודש")
    else:
        day_of_month_match = re.search(r'\b(\d{1,2})\s+לחודש\b', text)
        if day_of_month_match:
            day = int(day_of_month_match.group(1)); month = now.month; year = now.year
            if day < now.day:
                month += 1
                if month > 12: month = 1; year += 1
            date_obj = datetime(year, month, day).date()
            date_string_found = day_of_month_match.group(0)
            print(f"Rule Matched: Day of Month -> {date_obj}")
        
        else:
            relative_match = re.search(r'\b(מחרתיים|מחר)\b', text)
            if relative_match:
                relative_word = relative_match.group(0)
                if relative_word == "מחר": date_obj = (now + timedelta(days=1)).date()
                elif relative_word == "מחרתיים": date_obj = (now + timedelta(days=2)).date()
                date_string_found = relative_word
                print(f"Rule Matched: Relative Word -> {date_obj}")
            
            # עדיפות 3: יום בשבוע
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
                    print(f"Rule Matched: Weekday -> {date_obj}")

    # --- חלק 3: הרכבת הפאזל ---
    if not date_obj: date_obj = now.date()
    final_datetime = datetime.combine(date_obj, extracted_time)

    # --- חלק 4: ניקוי הכותרת (הגרסה הסופית) ---
    event_title = original_text
    # [תיקון] ננקה את כל הרמזים שמצאנו בסדר הנכון
    if date_string_found:
        event_title = event_title.replace(date_string_found, '', 1)
    if time_string_found:
        event_title = event_title.replace(time_string_found, '', 1)

    # [תיקון] נוסיף רשימה של מילים לניקוי סופי
    stop_words = ['בבוקר', 'בערב', 'בצהריים', 'בלילה']
    for word in stop_words:
        event_title = event_title.replace(word, '')

    event_title = re.sub(r'\s+', ' ', event_title).strip()
    if not event_title:
        event_title = "אירוע ללא כותרת"

    return final_datetime, event_title

# --- אתחול השרת וה-Webhook ---
app = Flask(__name__)
app.secret_key = os.urandom(24) # הוסף את השורה הזו
# --- [חדש] עמודי האינטרנט לתהליך ההרשמה ---

@app.route('/register')
def register():
    """העמוד שאליו הקישור מהוואטסאפ מוביל."""
    session['whatsapp_id'] = request.args.get('wa_id')
    
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    """העמוד שאליו גוגל מחזיר את המשתמש אחרי שהוא מאשר."""
    state = session['state']
    
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    
    flow.fetch_token(authorization_response=request.url)
    
    credentials = flow.credentials
    refresh_token = credentials.refresh_token
    
    whatsapp_id = session['whatsapp_id']
    
    # (אופציונלי) קבלת שם המשתמש מגוגל
    user_info_service = build('oauth2', 'v2', credentials=credentials)
    user_info = user_info_service.userinfo().get().execute()
    user_name = user_info.get('name', 'User')
    
    add_user(whatsapp_id, refresh_token, user_name)
    
    return "<h1>החיבור הושלם בהצלחה!</h1><p>אפשר לחזור לוואטסאפ ולהתחיל להשתמש בבוט.</p>"


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
            # --- [השינוי המרכזי] בדיקה אם המשתמש רשום ---
            user_token = get_user_token(sender_phone)
            
            if user_token:
                # המשתמש קיים - נפעיל את הלוגיקה הרגילה
                print(f"Known user: {sender_phone}. Processing message.")
                result = parse_datetime_and_title(message_text)
                if result:
                    start_datetime, event_title = result
                    end_datetime = start_datetime + timedelta(hours=1)
                    start_iso = start_datetime.isoformat()
                    end_iso = end_datetime.isoformat()
                    
                    # שימוש בפונקציה המעודכנת עם הטוקן של המשתמש
                    event_link = create_event_for_user(user_token, event_title, start_iso, end_iso)
                    
                    confirmation_message = f"בסדר, קבעתי!\nאירוע: {event_title}\nבתאריך: {start_datetime.strftime('%d/%m/%Y')} בשעה {start_datetime.strftime('%H:%M')}\n\nקישור: {event_link}"
                    send_whatsapp_message(sender_phone, confirmation_message)
                else:
                    error_message = "מצטער, לא הצלחתי להבין את התאריך והשעה בהודעה שלך."
                    send_whatsapp_message(sender_phone, error_message)
            else:
                # משתמש חדש - שלח לו קישור להרשמה
                print(f"New user: {sender_phone}. Sending registration link.")
                # ודא שאתה מריץ את ngrok כדי שהכתובת תהיה נכונה
                registration_link = url_for('register', wa_id=sender_phone, _external=True)
                message = f"שלום! נראה שזו הפעם הראשונה שלך כאן. כדי שאוכל ליצור עבורך אירועים, יש לחבר את יומן גוגל שלך דרך הקישור הבא:\n\n{registration_link}"
                send_whatsapp_message(sender_phone, message)
        
        return 'OK', 200
    return 'Unsupported method', 405

if __name__ == '__main__':
    app.run(debug=True, port=5000)