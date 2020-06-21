import os

from flask import Flask, request
from pymessenger import Bot
from wit import Wit

import json
import requests

app = Flask(__name__)



# ~~~~~~~~~~~~~~~~~~~~~~~~~~~Parameters~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Web Server Parameter
port = os.environ.get("PORT") or 8445

# Facebook Messenger API Parameters
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN")
if not FB_PAGE_TOKEN:
    raise ValueError("Missing FB PAGE TOKEN!")
FB_APP_SECRET = os.environ.get("FB_APP_SECRET")
if not FB_APP_SECRET:
    raise ValueError("Missing FB APP SECRET!")

# Wit.ai Parameters
WIT_TOKEN = os.environ.get("WIT_TOKEN")



# ~~~~~~~~~~~~~~~~~~~~~~~~~~~Facebook Messenger API~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Bot
bot = Bot(FB_PAGE_TOKEN)

# Webhook Setup
@app.route("/", methods=["GET"])
def webhook_setup():
    # When the endpoint is registered as a webhook, it must echo back the "hub.challenge" value it receives in the query arguments.
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.environ.get("FB_VERIFY_TOKEN"):
            return "Verification Token Mismatch!", 403
        return request.args["hub.challenge"], 200
    return "Hello World!", 200

# Message Handler
@app.route("/", methods=["POST"])
def message_handler():
    
    data = request.get_json()

    if data["object"] == "page":
        
        for entry in data["entry"]:
            
            for messaging_event in entry["messaging"]:

                # Extract Sender and Recipient IDs
                sender_id = messaging_event["sender"]["id"]

                # Extract Text Message and Send Reply

                if messaging_event.get("message"):

                    if "text" in messaging_event["message"]:
                        message_text = messaging_event["message"]["text"]
                        bot.send_text_message(sender_id, response(message_text))
                    
                    else:
                        bot.send_text_message(sender_id, "Invalid Message!")

    return "Ok", 200



# ~~~~~~~~~~~~~~~~~~~~~~~~~~~Wit.ai~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Bot
wit_client = Wit(access_token=WIT_TOKEN)

# Load General COVID-19 Information from JSON File
general_coronavirus_info = None
with open("general_coronavirus_info.json") as json_file:
    general_coronavirus_info = json.load(json_file)

# Format Reply Message
def response(message_text):
    
    wit_response = wit_client.message(message_text)

    if wit_response["intents"] == None or len(wit_response["intents"]) == 0:
        return "Message Not Supported!"

    # Extract Intent with Highest Order of Confidence
    intent = wit_response["intents"][0]["name"]

    if intent in general_coronavirus_info:
        return handle_general_coronavirus_info(intent)
    
    elif intent == "goodbye":
        return handle_goodbye()

    else:
        return "Message Not Supported Yet!"

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~Intent Handlers~~~~~~~~~~~~~~~~~~~~~~~~~~~

def handle_general_coronavirus_info(intent):
    return general_coronavirus_info[intent][0]["response"]

def handle_goodbye():
    return "Thank you for chatting with me today. Stay safe and feel free to chat with me anytime you need to!"

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~Main Function~~~~~~~~~~~~~~~~~~~~~~~~~~~

if __name__ == "__main__":
    app.run(port=port)