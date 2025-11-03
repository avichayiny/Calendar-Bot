# app.py (Version 22.0 - Final unified version for Meta)
import sys
import os
import json
import re
import requests
from flask import Flask, request, redirect, session, url_for
from dotenv import load_dotenv
from datetime import datetime, time, timedelta
import google.generativeai as genai
import vertexai
from vertexai.generative_models import GenerativeModel, Part

# --- Imports from our files ---
from database_handler import add_user, get_user_token
from google_calendar_handler import create_event_for_user, get_events_for_day, delete_event

# --- Imports for the Google authentication process ---
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from werkzeug.middleware.proxy_fix import ProxyFix

#print("--- app.py SCRIPT STARTED, IMPORTS OK ---")
# (כל האימפורטים שלך צריכים להיות לפני הבלוק הזה)
print("--- [DEBUG] 0. IMPORTS FINISHED. STARTING GLOBAL SCOPE ---", flush=True)
# -- Load environment variables (for Meta) --
load_dotenv()
APP_VERIFY_TOKEN = os.getenv('META_VERIFY_TOKEN')
APP_ACCESS_TOKEN = os.getenv('META_ACCESS_TOKEN')
PHONE_NUMBER_ID = os.getenv('META_PHONE_NUMBER_ID')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT')
LOCATION = 'us-central1'
print(f"--- [DEBUG] 0.5. Got ENV VARS (Project ID is: {PROJECT_ID}) ---", flush=True)

SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/userinfo.profile']


try:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-pro') # 'gemini-pro'
    print("--- GEMINI MODEL INITIALIZED ---")
except Exception as e:
    print(f"Error initializing Gemini: {e}")
    gemini_model = None

"""
try:
    print("--- [DEBUG] 1. Inside TRY block. About to init Vertex AI ---", flush=True)
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    print("--- [DEBUG] 2. vertexai.init() FINISHED ---", flush=True)

    gemini_model = GenerativeModel("gemini-1.5-pro")
    print(f"--- [SUCCESS] 3. VERTEX AI MODEL INITIALIZED (Region: {LOCATION}) ---", flush=True)

except Exception as e:
    print(f"--- [CRITICAL ERROR] 4. Error initializing Vertex AI: {e} ---", flush=True)
    print(f"--- [DEBUG] Project ID was: {PROJECT_ID} ---", flush=True)
    print(f"--- [DEBUG] Location was: {LOCATION} ---", flush=True)
    sys.stdout.flush() # וידוא הריגה
    sys.stderr.flush() # וידוא הריגה
    gemini_model = None
"""
print("--- [DEBUG] 5. FINISHED Vertex AI block. App is now loading. ---", flush=True)


# --- Initialize the server ---
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = os.getenv('FLASK_SECRET_KEY')

# --- [Our addition] Health check endpoint ---
@app.route('/')
def health_check():
    """A simple endpoint that Cloud Run can probe to verify the service is live."""
    return "OK", 200

# --- [Upgrade] Meta-compatible helper functions (with debug) ---
def parse_whatsapp_message(data):
    """Parses the incoming message structure from the Meta API."""
    # Print all the data coming from Meta so we can see it
    #print("--- RAW DATA FROM META ---")
    #print(json.dumps(data, indent=2))
    #print("--------------------------")
    
    try:
        entry = data['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']
        
        # Check if the payload contains a status update or a real message
        if 'messages' not in value:
            print("Webhook received a status update or other event, not a user message. Skipping.")
            return None, None
            
        message_object = value['messages'][0]
        
        # Check that this is a text message and not something else
        if 'text' not in message_object:
            print("Webhook received a non-text message (e.g., image, sticker). Skipping.")
            return None, None

        message_text = message_object['text']['body']
        # A small change to get the number from the most reliable source
        sender_phone_number = value['contacts'][0]['wa_id']
        
        print(f"Successfully parsed message from {sender_phone_number}")
        return sender_phone_number, message_text
        
    except (KeyError, IndexError, TypeError) as e:
        # If there's an error, print it instead of failing silently
        print(f"!!! FAILED TO PARSE MESSAGE. Error: {e} !!!")
        return None, None

def send_whatsapp_message(to_phone_number, message):
    """Sends a WhatsApp message via the Meta API."""
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


# --- [New] The Bot's Brain - LLM Based ---
def get_intent_from_llm(message_text):
    """
    Sends a user message to the Gemini API and gets back a structured JSON object
    with the intent and entities.
    """
    if not gemini_model:
        print("Gemini model is not initialized. Falling back.")
        return None

    # The prompt is our instruction to the model. It's critical.
    # The prompt's content itself remains in Hebrew, as it instructs the model
    # on how to process Hebrew text.
    system_prompt = f"""
    אתה עוזר חכם לניהול יומן. התאריך והשעה הנוכחיים הם: {datetime.now().isoformat()}
    המשתמש שלח את ההודעה הבאה בעברית: "{message_text}"

    תפקידך לנתח את ההודעה ולהחזיר *אך ורק* אובייקט JSON במבנה הבא:
    {{
      "intent": "CREATE", "QUERY", or "DELETE",
      "event_title": "כותרת האירוע שזוהתה (אם רלוונטי)",
      "event_datetime": "התאריך והשעה של האירוע בפורמט ISO 8601 (אם זוהה)"
    }}

    דוגמאות:
    - קלט: "פגישה עם רוני מחר ב-11" -> פלט: {{"intent": "CREATE", "event_title": "פגישה עם רוני", "event_datetime": "YYYY-MM-DDT11:00:00"}}
    - קלט: "מה יש לי מחר?" -> פלט: {{"intent": "QUERY", "event_title": null, "event_datetime": "YYYY-MM-DDT00:00:00"}}
    - קלט: "בטל את הפגישה של 11" -> פלט: {{"intent": "DELETE", "event_title": "פגישה", "event_datetime": "YYYY-MM-DDT11:00:00"}}
    
    חשוב:
    1. אם לא זוהה תאריך, השתמש בתאריך של היום.
    2. אם לא זוהתה שעה, השתמש ב-09:00 בבוקר כברירת מחדל עבור יצירה ומחיקה, ובחצות (00:00) עבור שאילתות.
    3. אם הכוונה היא "QUERY", שים ב-event_datetime את תחילת היום המבוקש.
    4. החזר *רק* את ה-JSON, בלי שום טקסט מסביב.
    """
    
    try:
        print("--- Sending prompt to Gemini API ---")
        response = gemini_model.generate_content(system_prompt)
        
        # Clean the response to ensure we only get the JSON
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
        
        print(f"--- Received response from Gemini: {cleaned_response} ---")
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"Error calling Gemini API or parsing JSON: {e}")
        return None

def get_intent_from_llm1(message_text):
    """
    Sends a user message to the Vertex AI API (in us-central1)
    and gets back a structured JSON object.
    """
    if not gemini_model:
        # הוספנו פלאש
        print("Vertex AI model is not initialized. Falling back.", flush=True)
        return None

    # הפרומפט נשאר כמעט זהה, רק בלי הפניות לתאריך
    system_prompt = f"""
    אתה עוזר חכם לניהול יומן. התאריך והשעה הנוכחיים הם: {datetime.now().isoformat()}
    המשתמש שלח את ההודעה הבאה בעברית: "{message_text}"

    תפקידך לנתח את ההודעה ולהחזיר *אך ורק* אובייקט JSON במבנה הבא:
    {{
      "intent": "CREATE", "QUERY", or "DELETE",
      "event_title": "כותרת האירוע שזוהתה (אם רלוונטי)",
      "event_datetime": "התאריך והשעה של האירוע בפורמט ISO 8601 (אם זוהה)"
    }}

    דוגמאות:
    - קלט: "פגישה עם רוני מחר ב-11" -> פלט: {{"intent": "CREATE", "event_title": "פגישה עם רוני", "event_datetime": "YYYY-MM-DDT11:00:00"}}
    - קלט: "מה יש לי מחר?" -> פלט: {{"intent": "QUERY", "event_title": null, "event_datetime": "YYYY-MM-DDT00:00:00"}}
    - קלט: "בטל את הפגישה של 11" -> פלט: {{"intent": "DELETE", "event_title": "פגישה", "event_datetime": "YYYY-MM-DDT11:00:00"}}
    
    חשוב:
    1. אם לא זוהה תאריך, השתמש בתאריך של היום.
    2. אם לא זוהתה שעה, השתמש ב-09:00 בבוקר כברירת מחדל עבור יצירה ומחיקה, ובחצות (00:00) עבור שאילתות.
    3. אם הכוונה היא "QUERY", שים ב-event_datetime את תחילת היום המבוקש.
    4. החזר *רק* את ה-JSON, בלי שום טקסט מסביב.
    """
    
    try:
        # הוספנו פלאש
        print("--- Sending prompt to Vertex AI API ---", flush=True)
        response = gemini_model.generate_content(system_prompt)
        
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
        
        # הוספנו פלאש
        print(f"--- Received response from Vertex AI: {cleaned_response} ---", flush=True)
        return json.loads(cleaned_response)
    except Exception as e:
        # הוספנו פלאש (זה הכי חשוב!)
        print(f"Error calling Vertex AI API or parsing JSON: {e}", flush=True)
        return None

# --- Parsing engine (our stable version - no changes) ---
""""
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

    # --- [Local fix] ---
    # Add a loop to clean the delete command words from the title
    delete_keywords = ['מחק', 'בטל', 'הסר']
    for word in delete_keywords:
        event_title = event_title.replace(word, '')
    # -------------------------
    
    event_title = re.sub(r'\s+', ' ', event_title).strip()
    if not event_title: event_title = "אירוע ללא כותרת"
    return final_datetime, event_title
"""""
# --- Web pages for the registration process (no changes) ---
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
    # --- [Our addition] ---
    generated_redirect_uri = url_for('oauth2callback', _external=True)
    print(f"--- GENERATED REDIRECT URI: '{generated_redirect_uri}' ----")
    # -------------------------

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
        if not credentials or not credentials.refresh_token: return "<h1>שגיאה: לא התקבל מפתח רענון מגוגל.</h1>", 400
        refresh_token = credentials.refresh_token
        whatsapp_id = session['whatsapp_id']
        user_info_service = build('oauth2', 'v2', credentials=credentials)
        user_info = user_info_service.userinfo().get().execute()
        user_name = user_info.get('name', 'User')
        add_user(whatsapp_id, refresh_token, user_name)
        try:
            welcome_message = f"היי {user_name}, החיבור הושלם! 🎉\n\nעכשיו היומן שלך מחובר. אתה יכול להתחיל לשלוח לי הודעות כמו:\n- 'פגישה חשובה מחר ב-10'\n- 'מה הלוז מחר?'\n- 'בטל את הפגישה של 10'"
            send_whatsapp_message(whatsapp_id, welcome_message)
        except Exception as e:
            print(f"Failed to send welcome message to {whatsapp_id}: {e}")
        return "<h1>החיבור הושלם בהצלחה!</h1><p>אפשר לסגור את הדף ולחזור לוואטסאפ.</p>"
    except Exception as e:
        print(f"Error in oauth2callback: {e}")
        return "<h1>אירעה שגיאה בתהליך האימות.</h1>", 500

"""
# --- Main Webhook with triple intent detection (fixed) ---
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
                print(f"Known user: {sender_phone}. Processing message: '{message_text}'")
                
                query_keywords = ['מה יש לי', 'מה הלוז', 'האם אני פנוי', 'מה יש']
                delete_keywords = ['מחק', 'בטל', 'הסר']
                
                is_query = any(keyword in message_text for keyword in query_keywords)
                is_delete = any(keyword in message_text for keyword in delete_keywords)

                if is_query:
                    # --- Existing logic: Handle query ---
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
                    # --- Fixed logic: Handle delete request ---
                    print("User intent: Delete event")
                    result = parse_datetime_and_title(message_text)
                    
                    if result:
                        target_datetime, event_keywords = result
                        events = get_events_for_day(user_token, target_datetime.date())
                        
                        event_to_delete = None
                        if events:
                            for event in events:
                                start = event['start'].get('dateTime', event['start'].get('date'))
                                start_time_obj_aware = datetime.fromisoformat(start.replace('Z', '+00:00'))
                                # <-- [The Fix] Making the time "naive" before comparison
                                start_time_obj_naive = start_time_obj_aware.replace(tzinfo=None)
                                
                                time_difference = abs((start_time_obj_naive - target_datetime).total_seconds())
                                title_match = event_keywords.lower() in event['summary'].lower()

                                if time_difference < 3600 and title_match:
                                    event_to_delete = event
                                    break
                        
                        if event_to_delete:
                            success = delete_event(user_token, event_to_delete['id'])
                            if success:
                                response_message = f"האירוע '{event_to_delete['summary']}' נמחק בהצלחה."
                            else:
                                response_message = "אירעה שגיאה במחיקת האירוע."
                        else:
                            response_message = "מצטער, לא מצאתי אירוע שתואם לתיאור שלך,."
                    else:
                        response_message = "לא הבנתי איזה אירוע למחוק. נסה לציין תאריך ומילת מפתח מהכותרת."
                    
                    send_whatsapp_message(sender_phone, response_message)

                else:
                    # --- Existing logic: Create new event ---
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
                # New user logic (remains the same)
                print(f"New user: {sender_phone}. Sending registration link.")
                registration_link = url_for('register', wa_id=sender_phone, _external=True)
                message = f"שלום! כדי שאוכל ליצור עבורך אירועים, יש לחבר את יומן גוגל שלך דרך הקישור הבא:\n\n{registration_link}"
                send_whatsapp_message(sender_phone, message)
            
            return 'OK', 200
        return 'Unsupported method', 405
"""

# --- [Major Upgrade] Main Webhook, now LLM-powered ---
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Webhook verification logic (no changes)
        if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
            if not request.args.get("hub.verify_token") == APP_VERIFY_TOKEN: 
                return "Verification token mismatch", 403
            return request.args.get("hub.challenge"), 200
        return "Hello World", 200

    elif request.method == 'POST':
        data = request.get_json()
        sender_phone, message_text = parse_whatsapp_message(data)
        
        # If it's not a valid text message, just acknowledge it and exit.
        if not (sender_phone and message_text):
            return 'OK', 200 

        user_token = get_user_token(sender_phone)
        
        # --- New User Logic (No Change) ---
        if not user_token:
            print(f"New user: {sender_phone}. Sending registration link." , flush=True)
            registration_link = url_for('register', wa_id=sender_phone, _external=True)
            message = f"שלום! כדי שאוכל ליצור עבורך אירועים, יש לחבר את יומן גוגל שלך דרך הקישור הבא:\n\n{registration_link}"
            send_whatsapp_message(sender_phone, message)
            return 'OK', 200

        # --- [NEW BRAIN] Known user logic starts here ---
        print(f"Known user: {sender_phone}. Processing with LLM: '{message_text}'", flush=True)
        
        action = get_intent_from_llm(message_text)
        
        if not action:
            # If the LLM failed to understand or parse
            send_whatsapp_message(sender_phone, "מצטער, לא הצלחתי להבין את הבקשה שלך. תוכל לנסח אותה קצת אחרת?")
            return 'OK', 200

        try:
            intent = action.get("intent")
            event_title = action.get("event_title")
            event_datetime_str = action.get("event_datetime")
            
            # Check if we got the minimum required info from the LLM
            if not (intent and event_datetime_str):
                raise ValueError("LLM response missing intent or datetime.")
                
            target_datetime = datetime.fromisoformat(event_datetime_str)

            # --- Execute action based on the LLM's recognized intent ---
            
            if intent == "CREATE":
                print("LLM Intent: CREATE", flush=True)
                if not event_title: 
                    event_title = "אירוע ללא כותרת" # Default title if LLM forgets
                
                end_datetime = target_datetime + timedelta(hours=1)
                event_link = create_event_for_user(user_token, event_title, target_datetime.isoformat(), end_datetime.isoformat())
                
                # Check if event creation was successful
                if "An error occurred" in str(event_link):
                    confirmation_message = f"ניסיתי לקבוע אירוע, אבל נתקלתי בשגיאה: {event_link}"
                else:
                    confirmation_message = f"בסדר, קבעתי!\nאירוע: {event_title}\nבתאריך: {target_datetime.strftime('%d/%m/%Y')} בשעה {target_datetime.strftime('%H:%M')}\n\nקישור: {event_link}"
                send_whatsapp_message(sender_phone, confirmation_message)

            elif intent == "QUERY":
                print("LLM Intent: QUERY", flush=True)
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

            elif intent == "DELETE":
                print("LLM Intent: DELETE", flush=True)
                # This logic is simpler for now. We can make it more complex later.
                # For now, it just demonstrates the intent was understood.
                # A full implementation would query events around `target_datetime`
                # and try to match `event_title` to delete the correct one.
                send_whatsapp_message(sender_phone, "זיהיתי שאתה רוצה למחוק אירוע. תכונה זו עדיין בפיתוח בגרסת ה-LLM.")

            else:
                send_whatsapp_message(sender_phone, "הבנתי את כוונתך, אבל אני עוד לא תומך בפעולה הזו.")

        except Exception as e:
            print(f"Error processing LLM action: {e}", flush=True)
            send_whatsapp_message(sender_phone, "מצטער, משהו השתבש בעיבוד הבקשה שלך.")
            
        return 'OK', 200

# --- Route for resetting the database (no change) ---
@app.route('/reset-database-for-testing')
# ... (הקוד של הפונקציה נשאר זהה) ...

# --- Route for resetting the database ---
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