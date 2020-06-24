import os

from flask import Flask, request
from pymessenger import Bot
from wit import Wit

import json
import requests

from geopy.geocoders import Nominatim

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

# Wit.ai Parameter
WIT_TOKEN = os.environ.get("WIT_TOKEN")

# The Weather Company APIs Parameter
WEATHER_COMPANY_API_KEY = os.environ.get("WEATHER_COMPANY_API_KEY")



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

                # Extract Message Text and Send Reply

                if messaging_event.get("message"):

                    if "text" in messaging_event["message"]:
                        message_text = messaging_event["message"]["text"]
                        bot.send_text_message(sender_id, response(message_text))
                    
                    else:
                        bot.send_text_message(sender_id, "The message is invalid! Please try again.")

    return "Ok", 200



# ~~~~~~~~~~~~~~~~~~~~~~~~~~~Wit.ai~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Bot
wit_client = Wit(access_token=WIT_TOKEN)

# Default Message Replies for Undesirable Behavior
unsupported_message = "Sorry, this message isn't supported!"
unparsable_location = "Sorry, I couldn't quite get that. Please type in the location or address by itself."
unreadable_location = "Sorry, I couldn't quite understand that. Please type in the location or address in a different format."

# Order of Confidence Cutoff
confidence_cutoff = 0.8

# Load General COVID-19 Information from JSON File
general_coronavirus_info = None
with open("general_coronavirus_info.json") as json_file:
    general_coronavirus_info = json.load(json_file)

# Utilized when Location or Address isn't able to be Parsed
prev_intent_name = None

# Set of Intents within COVID-19 Statsitics Domain
coronavirus_stats_intents = {"confirmed", "recovered", "deaths", "testsPerformed", "all_stats"}

geolocator = Nominatim(user_agent="Eldy Bot")

# Format Reply Message
def response(message_text):
    
    wit_response = wit_client.message(message_text)

    if wit_response["intents"] == None or len(wit_response["intents"]) == 0:
        return unsupported_message

    # Extract Intent with Highest Order of Confidence
    intent_name = wit_response["intents"][0]["name"]
    intent_confidence = wit_response["intents"][0]["confidence"]

    if intent_confidence < confidence_cutoff:
        return unsupported_message

    # Format Reply based on Intent

    if intent_name == "hello":
        return handle_hello()

    elif intent_name in general_coronavirus_info:
        return handle_general_coronavirus_info(intent_name)
    
    elif intent_name in coronavirus_stats_intents:
        
        if wit_response["entities"] == None or wit_response["entities"]["wit$location:location"] == None or len(wit_response["entities"]["wit$location:location"]) == 0:
            prev_intent_name = intent_name
            return unparsable_location

        entity_body = wit_response["entities"]["wit$location:location"][0]["body"]
        entity_confidence = wit_response["entities"]["wit$location:location"][0]["confidence"]

        if entity_confidence < confidence_cutoff:
            prev_intent_name = intent_name
            return unparsable_location
        
        return handle_coronavirus_stats(intent_name, entity_body)

    elif intent_name == "location":

        if wit_response["entities"] == None or wit_response["entities"]["wit$location:location"] == None or len(wit_response["entities"]["wit$location:location"]) == 0:
            return unreadable_location

        entity_body = wit_response["entities"]["wit$location:location"][0]["body"]
        entity_confidence = wit_response["entities"]["wit$location:location"][0]["confidence"]

        if entity_confidence < confidence_cutoff:
            return unreadable_location

        return handle_location(entity_body)

    else:
        return handle_goodbye()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~Intent Handlers~~~~~~~~~~~~~~~~~~~~~~~~~~~

def handle_hello():
    return "Hi! How can I assist you today?"

def handle_general_coronavirus_info(intent_name):
    return general_coronavirus_info[intent_name][0]["response"]

def handle_coronavirus_stats(intent_name, entity_body):

    location = geolocator.geocode(entity_body)
    geocode = location.raw["lat"] + "," + location.raw["lon"]

    reply_message = ""

    for loc_type in ["country", "state", "county"]:

        json_data = json.loads(requests.get("https://api.weather.com/v3/wx/disease/tracker/" + loc_type + "/60day?geocode=" + geocode + "&format=json&apiKey=" + WEATHER_COMPANY_API_KEY).text)
        
        loc_type_capitalized = loc_type.capitalize()

        if intent_name != "all_stats":

            stat = val_to_str(json_data["covid19"][intent_name][0])

            if intent_name == "confirmed":
                reply_message += loc_type_capitalized + " Wide COVID-19 Confirmed Cases: " + stat + "\n\n"

            elif intent_name == "recovered":
                reply_message += loc_type_capitalized + " Wide COVID-19 Recoveries: " + stat + "\n\n"

            elif intent_name == "deaths":
                reply_message += loc_type_capitalized + " Wide COVID-19 Deaths: " + stat + "\n\n"

            else:
                reply_message += loc_type_capitalized + " Wide COVID-19 Tests Performed: " + stat + "\n\n"

        else:

            cases = val_to_str(json_data["covid19"]["confirmed"][0])
            recoveries = val_to_str(json_data["covid19"]["recovered"][0])
            deaths = val_to_str(json_data["covid19"]["deaths"][0])
            tests = val_to_str(json_data["covid19"]["testsPerformed"][0])

            reply_message += loc_type_capitalized + " Wide COVID-19 Statistics\n\nConfirmed Cases: " + cases + "\nRecoveries: " + recoveries + "\nDeaths: " + deaths + "\nTests Performed: " + tests + "\n\n\n"

    return reply_message.rstrip()

def handle_location(entity_body):
    if prev_intent_name is not None:
        temp = prev_intent_name
        prev_intent_name = None
        return handle_coronavirus_stats(temp, entity_body)

def handle_goodbye():
    return "Thank you for chatting with me today. Stay safe and feel free to chat with me anytime you need to!"

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~Utility Functions~~~~~~~~~~~~~~~~~~~~~~~~~~~

def val_to_str(val):
    if val is None:
        return "N/A"
    return str(val)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~Main Function~~~~~~~~~~~~~~~~~~~~~~~~~~~

if __name__ == "__main__":
    app.run(port=port)