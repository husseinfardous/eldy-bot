import os

from flask import Flask, request, jsonify
from pymessenger import Bot
from wit import Wit

app = Flask(__name__)

# ~~~~~~~~~~Parameters~~~~~~~~~~

# Webserver Parameter
port = os.environ.get("PORT") or 8445

# Wit.ai Parameters
WIT_TOKEN = os.environ.get("WIT_TOKEN")

# Messenger API Parameters
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN")
if not FB_PAGE_TOKEN:
    raise ValueError("Missing FB PAGE TOKEN!")
FB_APP_SECRET = os.environ.get("FB_APP_SECRET")
if not FB_APP_SECRET:
    raise ValueError("Missing FB APP SECRET!")

# ~~~~~~~~~~Messenger API~~~~~~~~~~



# ~~~~~~~~~~Wit.ai Bot~~~~~~~~~~

#client = Wit(WIT_TOKEN)

bot = Bot(FB_PAGE_TOKEN)

# Webhook Setup
@app.route("/webhook", methods=["GET"])
def verify():
    # When the endpoint is registered as a webhook, it must echo back the "hub.challenge" value it receives in the query arguments
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.environ.get("FB_VERIFY_TOKEN"):
            return "Verification Token Mismatch!", 403
        return request.args["hub.challenge"], 200
    return "Hello World!", 200

# Message Handler
@app.route("/webhook", methods=["POST"])
def webhook():
    
    data = request.get_json()

    if data['object'] == 'page':
        for entry in data['entry']:
            for messaging_event in entry['messaging']:

                # IDs
                sender_id = messaging_event['sender']['id']
                recipient_id = messaging_event['recipient']['id']

                if messaging_event.get('message'):
                    # Extracting text message
                    if 'text' in messaging_event['message']:
                        messaging_text = messaging_event['message']['text']
                    else:
                        messaging_text = 'no text'

                    # Echo
                    response = messaging_text
                    bot.send_text_message(sender_id, response)

    return "ok", 200