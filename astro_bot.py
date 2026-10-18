# AstroBot - a Webex chat bot for the Astronomy Club.
# Built from the provided starter code: the bot monitors one Webex room, answers
# slash commands with live data from web APIs and posts the replies back to the room.
# API keys are read from a git-ignored .env file (see .env.example).

# =========================
# REQUIRED LIBRARIES
# =========================

import requests  # sends the HTTP GET/POST requests to every API
import json  # encodes the Webex message body as JSON
import time  # polling delay and epoch -> human-readable time conversion
from datetime import datetime, timedelta, timezone  # local times for weather reports

import os  # reads API keys from environment variables
from getpass import getpass  # hides keys while they are typed

from dotenv import load_dotenv  # loads API keys from the git-ignored .env file

# =========================
# SETTINGS
# =========================
WEBEX_API_URL = "https://webexapis.com/v1"

REQUEST_TIMEOUT = 10  # seconds to wait for any API before giving up

# =========================
# CONFIGURATION FUNCTIONS
# =========================
def get_webex_token():
    # The "hard-coded" token is kept in .env instead of the source code
    token = get_api_key("Webex access token", os.getenv("WEBEX_ACCESS_TOKEN"))
    # Accept a token pasted with or without the "Bearer " prefix
    if token.lower().startswith("bearer "):
        token = token[len("bearer "):].strip()
    return f"Bearer {token}"

def get_api_key(prompt, hardcoded_key):
    # Offer the key saved in .env first; otherwise ask the user to type one in
    if hardcoded_key:
        choice = input(f"Use the {prompt} saved in .env? (y/n): ").strip().lower()
        if choice != "n":
            return hardcoded_key.strip()
    else:
        print(f"No {prompt} found in .env.")

    key = ""
    while not key:
        # getpass hides the key as it is typed so it never appears on screen
        key = getpass(f"Enter your {prompt}: ").strip()
    return key

# =========================
# WEBEX FUNCTIONS
# =========================
def get_rooms(token):
    url = f"{WEBEX_API_URL}/rooms"
    headers = {"Authorization": token}
    # Most recently active rooms first, so the club's room is near the top of the list
    params = {"sortBy": "lastactivity", "max": 100}
    response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)

    if response.status_code != 200:
        print("Error fetching rooms:", response.status_code)
        return []

    return response.json().get("items", [])


def print_rooms(rooms):
    print("\nAvailable Webex rooms:")
    # Number each room so it can be picked by number as well as by name
    for number, room in enumerate(rooms, start=1):
        print(f"  {number:>2}. {room.get('title', 'Untitled room')}  [{room.get('type', 'unknown')}]")


def select_room(rooms):
    while True:
        name = input(#complete the input prompt to ask the user for the room name)
        for room in rooms:
            if name.lower() in room["title"].lower():
                print(#complete the print statement to confirm the selected room)
                return room["id"]
        print(#complete the print statement to indicate that the room was not found)


def get_latest_message(token, room_id):
    url = #complete the URL to fetch messages from Webex API
    params = {"roomId":#complete, "max": #complete}
    headers = #complete the headers dictionary to include the Authorization header with the token

    response = requests.#complete(#complete, headers=headers, params=params)

    if response.status_code != 200:
        return None, None

    data = response.json().get("items", [])

    if not data:
        return None, None

    latest = data[0]
    return latest.get("id"), latest.get("text", "")


def send_message(token, room_id, message):
    url = #complete the URL to send messages to Webex API
    headers = #complete the headers dictionary to include the Authorization header with the token and Content-Type as application/json
    data = {
        "roomId": room_id,
        "text": message
    }
    requests.#complete(url, headers=headers, data=json.dumps(data))

# =========================
# WEATHER FUNCTIONS
# =========================
def get_city_coordinates(city, api_key):
    url = #complete the URL to fetch city coordinates from OpenWeatherMap API
    params = #complete the params dictionary to include the city name, limit, and the API key
    response = requests.#complete(url, params=params)

    if response.status_code != 200:
        return None

    data = response.json()
    return data[0] if data else None


def get_weather(city, api_key):
    location = get_city_coordinates(city, api_key)

    if not location:
        return #complete the return statement to indicate that the city was not found

    url = #complete the URL to fetch weather data from OpenWeatherMap API
    params = #complete the params dictionary to include the latitude, longitude, units as metric, and the API key

    response = requests.#complete(url, params=params)

    if response.status_code != 200:
        return #complete the return statement to indicate that the wheather weather data retrieved or not

    weather = response.json()

    return (
        #complete the return statement to format and return the weather information such as including city name, country, temperature, weather description, humidity, and wind speed
    )

# =========================
# ISS FUNCTIONS
# =========================
def reverse_geocode(lat, lon, api_key):
    url = #complete the URL to fetch reverse geocoding data from OpenWeatherMap API
    params = #complete the params dictionary to include the latitude, longitude, limit, and the API key

    response = requests.#complete(url, params=params)

    if response.status_code != 200:
        return None

    data = response.json()
    return data[0] if data else None


def get_iss_location(api_key):
    url = #complete the URL to fetch ISS current location from the Open Notify API

    response = requests.#complete(#complete)

    if response.status_code != 200:
        return #complete the return statement to indicate whether ISS location retrieved or not

    data = response.json()

    lat = data[#complete][#complete]
    lon = data[#complete][#complete]

    location = reverse_geocode(lat, lon, api_key)

    place = "Over Ocean / No Nearby City"

    if location:
        place = #

    return (
        #complete the return statement to format and return the ISS location information including latitude, longitude, and place name
    )

# =========================
# MAIN BOT LOGIC
# =========================
def main():

    # Load WEBEX_ACCESS_TOKEN and OPENWEATHER_API_KEY from .env into the environment
    load_dotenv()

    token = get_webex_token()

    weather_key = get_api_key(
        "OpenWeather API key",
        os.getenv("OPENWEATHER_API_KEY")
    )

    rooms = get_rooms(token)

    if not rooms:
        print(#complete the print statement )
        return

    print_rooms(rooms)
    room_id = select_room(rooms)

    last_message_id, _ = get_latest_message(token, room_id)

    while True:

        message_id, message_text = get_latest_message(token, room_id)

        if message_id and message_id != last_message_id:

            last_message_id = message_id

            print(#complete the print statement to display the received message text)

            if not message_text.startswith(#complete):
                continue

            if message_text.lower() == "/help":
                send_message(
                    token,
                    room_id,
                    "/weather <city>\n/iss\n/help\n/quit"
                )

            elif message_text.lower().startswith(#complete):

                parts = message_text.split(maxsplit=1)

                if len(parts) < 2:
                    send_message(token, room_id, "Usage: /weather <city>")
                else:
                    city = parts[1]
                    send_message(token, room_id, get_weather(city, weather_key))

            elif message_text.lower() == "#complete":
                send_message(token, room_id, get_iss_location(weather_key))

            elif message_text.lower() == "#complete":
                send_message(token, room_id, "AstroBot shutting down.")
                break

            else:
                send_message(token, room_id, "Unknown command. Use /help")

        time.sleep(5)


if __name__ == '__main__':
    main()
