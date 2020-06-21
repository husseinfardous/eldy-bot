import os
import json

from flask import Flask, request
from pymessenger import Bot
from wit import Wit

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

                # Extract Text Message

                if messaging_event.get("message"):

                    if "text" in messaging_event["message"]:
                        message_text = messaging_event["message"]["text"]
                        bot.send_text_message(sender_id, response(message_text))
                    
                    else:
                        bot.send_text_message(sender_id, "Invalid Message!")

    return "Ok", 200



# ~~~~~~~~~~~~~~~~~~~~~~~~~~~Wit.ai~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Bot
client = Wit(access_token=WIT_TOKEN)

def response(message_text):
    
    wit_response = client.message(message_text)

    if wit_response["intents"] == None or len(wit_response["intents"]) == 0:
        return "Message Not Supported!"

    intent = wit_response["intents"][0]["name"]

    if intent == "covid_definition":
        return handle_general_coronavirus_info("covid_definition")
    
    elif intent == "covid_spread":
        return handle_general_coronavirus_info("covid_spread")
    
    elif intent == "safe_actions":
        return handle_general_coronavirus_info("safe_actions")
    
    elif intent == "food_concerns":
        return handle_general_coronavirus_info("food_concerns")
    
    elif intent == "safe_actions_neighborhood":
        return handle_general_coronavirus_info("safe_actions_neighborhood")
    
    elif intent == "elder_vulnerability":
        return handle_general_coronavirus_info("elder_vulnerability")
    
    elif intent == "covid_coping":
        return handle_general_coronavirus_info("covid_coping")
    
    elif intent == "covid_symptoms":
        return handle_general_coronavirus_info("covid_symptoms")
    
    elif intent == "pet_vulnerability":
        return handle_general_coronavirus_info("pet_vulnerability")
    
    elif intent == "inperson_hangout":
        return handle_general_coronavirus_info("inperson_hangout")

    elif intent == "actions_if_sick":
        return handle_general_coronavirus_info("actions_if_sick")

    elif intent == "plan_if_sick":
        return handle_general_coronavirus_info("plan_if_sick")

    elif intent == "nursing_home_concern":
        return handle_general_coronavirus_info("nursing_home_concern")

    elif intent == "immunocompromised_concern":
        return handle_general_coronavirus_info("immunocompromised_concern")

    elif intent == "asthma_concern":
        return handle_general_coronavirus_info("asthma_concern")

    elif intent == "kidney_concern":
        return handle_general_coronavirus_info("kidney_concern")

    elif intent == "diabetes_concern":
        return handle_general_coronavirus_info("diabetes_concern")

    elif intent == "hemoglobin_concern":
        return handle_general_coronavirus_info("hemoglobin_concern")

    elif intent == "liver_concern":
        return handle_general_coronavirus_info("liver_concern")

    elif intent == "heart_concern":
        return handle_general_coronavirus_info("heart_concern")

    elif intent == "obesity_concern":
        return handle_general_coronavirus_info("obesity_concern")
    
    else:
        return "Message Not Supported Yet!"

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~Intent Handlers~~~~~~~~~~~~~~~~~~~~~~~~~~~

general_coronavirus_info = None
with open("general_coronavirus_info.json") as json_file:
    general_coronavirus_info = json.load(json_file)

def handle_general_coronavirus_info(intent):
    return general_coronavirus_info[intent][0]["response"]

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~Main Function~~~~~~~~~~~~~~~~~~~~~~~~~~~

if __name__ == "__main__":
    app.run(port=port)