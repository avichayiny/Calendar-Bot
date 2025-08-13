# test_webhook.py
import requests
import json

# הכתובת המקומית של השרת שלנו
LOCAL_WEBHOOK_URL = "http://127.0.0.1:5000/webhook"

# דוגמה להודעה שאנחנו רוצים לדמות
# שנה את המספר וההודעה כדי לבדוק מקרים שונים
# למשל, מספר שכבר נרשם או מספר חדש
test_message_payload = {
    "entry": [{
        "changes": [{
            "value": {
                "messages": [{
                    "from": "972500000001",  # אותו מספר טלפון
                    "text": { "body": "פגישת סיכום לפרויקט הבוט מחר ב-11" } # הודעה חדשה
                }]
            }
        }]
    }]
}

def send_test_message():
    print(f"--- Sending test message to local server ---")
    try:
        response = requests.post(
            LOCAL_WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(test_message_payload)
        )
        print(f"Local server responded with status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to local server: {e}")
        print("Is your app.py server running?")

if __name__ == '__main__':
    send_test_message()