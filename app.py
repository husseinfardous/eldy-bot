import os

from flask import Flask, request, jsonify
from pymessenger import Bot
from wit import Wit

app = Flask(__name__)



# ~~~~~~~~~~Parameters~~~~~~~~~~

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



# ~~~~~~~~~~Facebook Messenger API~~~~~~~~~~

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
                #recipient_id = messaging_event["recipient"]["id"]

                # Extract Text Message
                if messaging_event.get("message"):
                    if "text" in messaging_event["message"]:
                        message_text = messaging_event["message"]["text"]
                    else:
                        message_text = ""

                    """
                    # Echo Message
                    response = message_text
                    bot.send_text_message(sender_id, response)
                    """

                    bot.send_text_message(sender_id, response(message_text))

    return "Ok", 200



# ~~~~~~~~~~Wit.ai~~~~~~~~~~

# Bot
client = Wit(access_token=WIT_TOKEN)

def response(message_text):

    if message_text == "":
        return "Invalid Message!"

    wit_response = client.message(message_text)
    return "Query: " + wit_response["text"] + "; Intent"  + wit_response["intents"][0]["name"]

# ~~~~~~~~~~Main Function~~~~~~~~~~

if __name__ == "__main__":
    app.run(port=port)