import os

from flask import Flask, request
from pymessenger import Bot
from wit import Wit

import json
import requests
from requests.auth import HTTPBasicAuth
import copy

from geopy.geocoders import Nominatim

from nltk.stem.wordnet import WordNetLemmatizer

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

# Airtable API Parameters
AIRTABLE_EMAIL = os.environ.get("AIRTABLE_EMAIL")
AIRTABLE_PASSWORD = os.environ.get("AIRTABLE_PASSWORD")
AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY")

# MapQuest API Parameter
MAPQUEST_API_KEY = os.environ.get("MAPQUEST_API_KEY")



# ~~~~~~~~~~~~~~~~~~~~~~~~~~~Global Variables~~~~~~~~~~~~~~~~~~~~~~~~~~~

# ~~~~~~~~~~General~~~~~~~~~~
geolocator = Nominatim(user_agent="Eldy Bot")
lemmatizer = WordNetLemmatizer()

# ~~~~~~~~~~Facebook Messenger API~~~~~~~~~~

# Bot
bot = Bot(FB_PAGE_TOKEN)

# Default Message Replies for Undesirable Behavior
unsupported_message = "Sorry, this message isn't supported!"
unparsable_location = "Sorry, I couldn't quite get that. Please type in the location or address by itself."
unreadable_location = "Sorry, I couldn't quite understand that. Please type in the location or address in a different format."
unreadable_supply_request = "Sorry, I couldn't quite understand. I think you are requesting items. Can you please rephrase your question?"

# ~~~~~~~~~~Wit.ai~~~~~~~~~~

# Bot
wit_client = Wit(access_token=WIT_TOKEN)

# Order of Confidence Cutoff
confidence_cutoff = 0.8

# ~~~~~~~~~~Intent Handling~~~~~~~~~~

# ~~~~~COVID-19 General Information~~~~~

# Load General COVID-19 Information from JSON File
general_coronavirus_info = None
with open("general_coronavirus_info.json") as json_file:
    general_coronavirus_info = json.load(json_file)

# ~~~~~COVID-19 Statistics~~~~~

# Set of Intents within COVID-19 Statsitics Domain
coronavirus_stats_intents = {"confirmed", "recovered", "deaths", "testsPerformed", "all_stats"}

# Utilized when Location or Address isn't able to be Parsed
prev_intent_name = None

# ~~~~~Physical, Communal Resources Nearby~~~~~

# Load US States and Abbreviations from JSON File 
us_states_data = None
with open("us_states.json") as json_file:
    us_states_data = json.load(json_file)

# Dictionary of US states map to an array of suppliers residing in that state
supplier_state_dictionary = dict()

# Timestamp of the last entry added to the Resource Provider Table 
resource_providers_timestamp = '2020-05-22T03:36:27.000Z'

supplies_request = []


"""
~~~~~~~~~~~~~~~~~~~~~JANILL LEMA~~~~~~~~~~~~~
"""

# ~~~~~Loneliness Prevention~~~~~

companions_interests_to_id = {}
companions_id_to_info = {}
companions_info_fields = []

companions_latest_entry_timestamp = None

companions_table = json.loads(requests.get("https://api.airtable.com/v0/app62IQsAsxBquR8C/tblSfz8w4Vi26Pf90?sort%5B0%5D%5Bfield%5D=created_time&sort%5B0%5D%5Bdirection%5D=asc&api_key=" + AIRTABLE_API_KEY, auth=HTTPBasicAuth(AIRTABLE_EMAIL, AIRTABLE_PASSWORD)).text)["records"]

for record in companions_table:
        
    companions_interests_to_id[record["fields"]["Interests/Hobbies"]] = record["id"]

    for field in record["fields"]:

        if field != "Interests/Hobbies" and field != "created_time":
            
            companions_info_fields.append(field)
            
            if record["id"] in companions_id_to_info:
                companions_id_to_info[record["id"]][field] = record["fields"][field]
            else:
                companions_id_to_info[record["id"]] = {field: record["fields"][field]}

companions_latest_entry_timestamp = companions_table[len(companions_table) - 1]["createdTime"]

ids_to_overlapping_interests = {}



# ~~~~~~~~~~~~~~~~~~~~~~~~~~~Facebook Messenger API~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

# Format Reply Message
def response(message_text):
    
    global prev_intent_name

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
        
        if wit_response["entities"] == None or "wit$location:location" not in wit_response["entities"] or len(wit_response["entities"]["wit$location:location"]) == 0:
            prev_intent_name = intent_name
            return unparsable_location

        entity_body = wit_response["entities"]["wit$location:location"][0]["body"]
        entity_confidence = wit_response["entities"]["wit$location:location"][0]["confidence"]

        if entity_confidence < confidence_cutoff:
            prev_intent_name = intent_name
            return unparsable_location
        
        return handle_coronavirus_stats(intent_name, entity_body)

    elif intent_name == "location":

        if wit_response["entities"] == None or "wit$location:location" not in wit_response["entities"] or len(wit_response["entities"]["wit$location:location"]) == 0:
            return unreadable_location

        entity_body = wit_response["entities"]["wit$location:location"][0]["body"]
        entity_confidence = wit_response["entities"]["wit$location:location"][0]["confidence"]

        if entity_confidence < confidence_cutoff:
            return unreadable_location

        return handle_location(entity_body)

    
    elif intent_name == "resource_service_request":
        global supplies_request
        supplies_request.clear()

        if wit_response["entities"] == None or "wit_supplies:wit_supplies" not in wit_response["entities"] or len(wit_response["entities"]["wit_supplies:wit_supplies"]) == 0:
            return unreadable_supply_request

        for idx in range(0, len(wit_response["entities"]["wit_supplies:wit_supplies"])):
            entity = wit_response["entities"]["wit_supplies:wit_supplies"][idx]["body"]
            supplies_request.append(entity)

        entity_confidence = wit_response["entities"]["wit_supplies:wit_supplies"][0]["confidence"]

        if entity_confidence < confidence_cutoff:
            return unreadable_supply_request

        return handle_supply_request()

    elif intent_name == "loneliness":
        return handle_loneliness()

    elif intent_name == "interests":
        return handle_interests(message_text)

    else:
        return handle_goodbye()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~Intent Handlers~~~~~~~~~~~~~~~~~~~~~~~~~~~

def handle_hello():
    return "Hi! How can I assist you today?"

def handle_general_coronavirus_info(intent_name):
    return general_coronavirus_info[intent_name][0]["response"]

def handle_coronavirus_stats(intent_name, entity_body):

    global prev_intent_name

    location = geolocator.geocode(entity_body, addressdetails=True)

    if location:

        all_loc_types = ["country", "state", "county"]
        loc_types = []
        for loc_type in all_loc_types:
            if loc_type in location.raw["address"]:
                loc_types.append(loc_type)

        geocode = location.raw["lat"] + "," + location.raw["lon"]

        reply_message = ""

        for loc_type in loc_types:

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

    else:
        prev_intent_name = intent_name
        return unparsable_location

def handle_location(entity_body):
    global prev_intent_name
    global supplies_request

    if len(supplies_request)==0:
        if prev_intent_name is not None:
            temp = prev_intent_name
            prev_intent_name = None
            return handle_coronavirus_stats(temp, entity_body)
    else:
        return handle_supplies(entity_body)

"""
~~~~~~~~~~~~~~~~~~~~~JANILL LEMA~~~~~~~~~~~~~
"""
def handle_supply_request():
    return "I see that you are requesting supplies. Can you please give me your current location so that I can find people offerring these services/ supplies nearby? "

def handle_supplies(reciever_address):
    global supplies_request

    check_new_entry_supplier_table()

    address_locator= geolocator.geocode(reciever_address, addressdetails=True)
     if address_locator:
          find_possible_resource_providers(address_locator.raw['address']['state'], reciever_address, supplies_array)
     else:
          handle_resource_request()

def handle_resource_request(data=None):
     if data == None:
          return "I could not understand your address. Could you please write format your address as this sample address: 70 Morningside St., New York, NY 11207"
     elif (len(data) == 0):
          return "Sorry, I could not find any of the supplies requested near you."
     else:
          return supplier_information(data)

def handle_loneliness():
    return "I am very sorry to hear that. What are your interests/hobbies? Please write each one followed by a comma so I can connect you with people that have similar interests and that want to mingle with you about them :)"

def handle_interests(message_text):
    
    check_companions_table_update()
    find_overlapping_interests(message_text)

    reply_message = "Here are your matches!\n\n"

    for match in ids_to_overlapping_interests:
        reply_message += companions_id_to_info[match]["Name"] + "\n"
        reply_message += "Common Interests/Hobbies: "
        for overlapping_interest in ids_to_overlapping_interests[match]:
            reply_message += overlapping_interest + ", "
        reply_message.rstrip()[len(reply_message) - 1]
        reply_message += "\n\n"

    return reply_message.rstrip()[len(reply_message) - 1]

def handle_goodbye():
    return "Thank you for chatting with me today. Stay safe and feel free to chat with me anytime you need to!"

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~Helper Functions~~~~~~~~~~~~~~~~~~~~~~~~~~~

def val_to_str(val):
    if val is None:
        return "N/A"
    return str(val)

def check_new_entry_supplier_table():

     global resource_providers_timestamp

     created_time_string = "CREATED_TIME() > '" + resource_providers_timestamp
     supplier_table = requests.get("https://api.airtable.com/v0/app62IQsAsxBquR8C/tbllMS68Zqkwm7nbn?fields%5B%5D=Pickup+Address&filterByFormula=" + created_time_string + "'&sort%5B0%5D%5Bfield%5D=created_time&sort%5B0%5D%5Bdirection%5D=asc&api_key=" + AIRTABLE_API_KEY, auth=HTTPBasicAuth(AIRTABLE_EMAIL, AIRTABLE_PASSWORD)).json()["records"]
     
     if (len(supplier_table) > 0):

          resource_providers_timestamp = supplier_table[-1]['createdTime']

          for k in supplier_table:

               supplier_state = ""
               supplier_address = k['fields'].get('Pickup Address')
          
               address_locator = geolocator.geocode(supplier_address, addressdetails=True)

               if address_locator:
                    supplier_state = address_locator.raw['address']['state']
                    supplier_state_dictionary.setdefault(supplier_state,[]).append(k['id'])
               else:
                    supplier_address = ''.join([i for i in supplier_address if not i.isdigit()])
                    parsed_address_array = [ x.strip().lstrip().lower() for x in supplier_address.split(",")]

                    for idx in range(0, len(us_states_data["abbreviations"])):
                         if us_states_data["abbreviations"][idx].lower() in parsed_address_array or us_states_data["states"][idx].lower() in parsed_address_array:
                              supplier_state_dictionary.setdefault(us_states_data["states"][idx],[]).append(k['id'])
                              break

def populate_companions_table_data(table):

    global companions_interests_to_id
    global companions_id_to_info
    global companions_info_fields
    global companions_latest_entry_timestamp

    for record in table:
        
        companions_interests_to_id[record["fields"]["Interests/Hobbies"]] = record["id"]

        for field in record["fields"]:

            if field != "Interests/Hobbies" and field != "created_time":
                
                companions_info_fields.append(field)
                
                if record["id"] in companions_id_to_info:
                    companions_id_to_info[record["id"]][field] = record["fields"][field]
                else:
                    companions_id_to_info[record["id"]] = {field: record["fields"][field]}

    companions_latest_entry_timestamp = table[len(table) - 1]["createdTime"]

def check_companions_table_update():
    
    new_records = json.loads(requests.get("https://api.airtable.com/v0/app62IQsAsxBquR8C/tblSfz8w4Vi26Pf90?filterByFormula=CREATED_TIME()+%3E+%22" + companions_latest_entry_timestamp + "%22&api_key=" + AIRTABLE_API_KEY, auth=HTTPBasicAuth(AIRTABLE_EMAIL, AIRTABLE_PASSWORD)).text)["records"]

    if len(new_records) > 0:
        populate_companions_table_data(new_records)

def find_overlapping_interests(message_text):
    
    global ids_to_overlapping_interests

    demand_interests = message_text.split(",")

    for supply_interests in companions_interests_to_id:
        
        demand_interests_toks = [lemmatizer.lemmatize(x.lower().strip(), "v") for x in demand_interests]

        supply_interests_toks = [lemmatizer.lemmatize(x.strip(), "v") for x in supply_interests.lower().split(",")]

        overlapping_interests = {supply_interests_tok.capitalize() for demand_interest_tok in demand_interests_toks for supply_interests_tok in supply_interests_toks if supply_interests_tok in demand_interest_tok or demand_interest_tok in supply_interests_tok}

        if len(overlapping_interests) > 0:
            ids_to_overlapping_interests[companions_interests_to_id[supply_interests]] = copy.deepcopy(overlapping_interests)

def find_possible_resource_providers(reciever_state, reciever_address, supply_array):
     supply_array_lemmatized = [lemmatizer.lemmatize(x.lower().strip().lstrip()) for x in supply_array]
     
     possible_suppliers = ','.join(supplier_state_dictionary[reciever_state])   
     possible_supplier_list = requests.get("https://api.airtable.com/v0/app62IQsAsxBquR8C/tbllMS68Zqkwm7nbn?filterByFormula=SEARCH(RECORD_ID()%2C+%27"+ possible_suppliers + "%27)+!%3D+%22%22&api_key=" + AIRTABLE_API_KEY, auth=HTTPBasicAuth(AIRTABLE_EMAIL, AIRTABLE_PASSWORD)).json()["records"]
    
     matching_suppliers_list = []
     for supplier_dict in possible_supplier_list:
          available_supplier_supplies = []
          available_supplier_supplies = [lemmatizer.lemmatize(s.lower().strip().lstrip()) for s in supplier_dict.get('fields').get('Service/Items')] 
          
          other_items = supplier_dict.get('fields').get('Other Items')
          if other_items:
               other_items = other_items.split(",")
               available_supplier_supplies += [lemmatizer.lemmatize(s.lower().strip().lstrip()) for s in other_items]
               
          overlap_items = [x for x in supply_array_lemmatized for y in available_supplier_supplies if x in y or y in x]

          if (len(overlap_items) > 0 ):
               matching_suppliers_list.append(supplier_dict)
     
     find_providers_nearby(matching_suppliers_list, reciever_address)



def find_providers_nearby(possible_suppliers, reciever_add):
     providers_nearby = []

     reciever_address = reciever_add.replace(" ", '+').replace(",", "%2C").replace('#','%')
     for supplier in possible_suppliers:
          supplier_address = supplier.get('fields').get("Pickup Address").replace(" ", '+').replace(",", "%2C").replace('#','%')
          distance = requests.get("https://www.mapquestapi.com/directions/v2/alternateroutes?key=" + MAPQUEST_API_KEY + "&from=" + reciever_address + "&to=" + supplier_address + "&outFormat=json&ambiguities=ignore&routeType=pedestrian&maxRoutes=1&timeOverage=0&doReverseGeocode=false&enhancedNarrative=false&avoidTimedConditions=false&unit=M").json()['route']['distance']
          if (distance <= 15):
               providers_nearby.append([distance, supplier])
     
     handle_resource_request(sorted(providers_nearby))

def supplier_information(supplier_data):

     response = ""
     
     for arr in supplier_data:

          distance_away = str(arr[0])
          supplier_name = arr[1]['fields']['Name']
          response += supplier_name + " is " + distance_away + " miles away from you! \n" 

          pick_up_address = arr[1]['fields']['Pickup Address']
          response += "Pickup Address: " + pick_up_address +'\n'

          items = arr[1]['fields'].get('Service/Items')
          if items:
               response += "Items/Services Available: " + ",".join(items)
          
          other_items = arr[1]['fields'].get('Other Items')
          if other_items:
               if ( items!= None ):
                    response += "," + other_items  + "\n"
               else:
                    response += "Items/Services Available: " + other_items + "\n"
          else:
               response += "\n"
          
          phone_number = arr[1]['fields'].get('Phone Number')
          if phone_number:
               response += "Phone Number: " + phone_number + '\n'
          
          email = arr[1]['fields'].get('Email')
          if email:
               response += "Email: " + email + '\n'
          
          additional_notes = arr[1]['fields'].get('Additional Notes')
          if additional_notes:
               response += "Additional Notes: " + additional_notes + "\n"
          
          response += "\n"
     return response
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~Main Function~~~~~~~~~~~~~~~~~~~~~~~~~~~

if __name__ == "__main__":
    app.run(port=port)