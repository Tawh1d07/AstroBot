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
GEOCODING_API_URL = "https://api.openweathermap.org/geo/1.0"
WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"

REQUEST_TIMEOUT = 10  # seconds to wait for any API before giving up
POLL_INTERVAL = 5  # seconds between checks for new Webex messages

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
        name = input("\nEnter the room number or part of its name to monitor: ").strip()
        if not name:
            continue

        # A number picks the room at that position in the printed list
        if name.isdigit() and 1 <= int(name) <= len(rooms):
            room = rooms[int(name) - 1]
            print(f"Monitoring room: {room.get('title', 'Untitled room')}")
            return room["id"]

        for room in rooms:
            if name.lower() in room.get("title", "").lower():
                print(f"Monitoring room: {room['title']}")
                return room["id"]
        print(f"No room matching '{name}' was found. Please try again.")


def get_latest_message(token, room_id):
    url = f"{WEBEX_API_URL}/messages"
    # Webex lists messages newest first, so max=1 returns only the latest one
    params = {"roomId": room_id, "max": 1}
    headers = {"Authorization": token}

    response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)

    if response.status_code == 429:
        # Rate limited: wait as long as the Retry-After header asks before polling again
        retry_after = response.headers.get("Retry-After", "")
        wait = int(retry_after) if retry_after.isdigit() else POLL_INTERVAL
        print(f"Webex rate limit reached - pausing for {wait} seconds")
        time.sleep(wait)
        return None, None

    if response.status_code == 401:
        # Personal access tokens expire after 12 hours, so polling cannot continue
        raise SystemExit("Webex rejected the access token (401). Get a new token and restart AstroBot.")

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
    url = f"{GEOCODING_API_URL}/direct"
    params = {"q": city, "limit": 1, "appid": api_key}
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)

    if response.status_code != 200:
        print("Geocoding API error:", response.status_code)
        return None

    data = response.json()
    return data[0] if data else None


def get_current_weather(lat, lon, api_key):
    # Shared by /weather and /iss: current conditions at a coordinate in metric units
    url = WEATHER_API_URL
    params = {"lat": lat, "lon": lon, "units": "metric", "appid": api_key}

    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)

    if response.status_code != 200:
        print("Weather API error:", response.status_code)
        return None

    return response.json()


def get_weather(city, api_key):
    location = get_city_coordinates(city, api_key)

    if not location:
        return f"Sorry, I couldn't find a city called '{city}'. Try adding a country code, e.g. /weather Paris,FR"

    weather = get_current_weather(location["lat"], location["lon"], api_key)

    if not weather:
        return "Sorry, the weather data could not be retrieved right now. Please try again later."

    return (
        f"Weather for {location['name']}, {location['country']}\n"
        f"Temperature: {weather['main']['temp']}°C\n"
        f"Conditions: {weather['weather'][0]['description']}\n"
        f"Humidity: {weather['main']['humidity']}%\n"
        f"Wind speed: {weather['wind']['speed']} m/s"
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
        print("No Webex rooms found. Check your access token and network connection.")
        return

    print_rooms(rooms)
    room_id = select_room(rooms)

    # Remember the newest existing message so old messages are not treated as commands
    last_message_id, _ = get_latest_message(token, room_id)
    print("AstroBot is listening for commands. Press Ctrl+C to stop.")

    while True:

        # Sleeping at the top of the loop means 'continue' can never skip the delay
        time.sleep(POLL_INTERVAL)

        message_id, message_text = get_latest_message(token, room_id)

        if message_id and message_id != last_message_id:

            last_message_id = message_id

            print(f"Received: {message_text}")

            # Only messages starting with "/" are commands; ignore normal chat
            if not message_text.startswith("/"):
                continue

            if message_text.lower() == "/help":
                send_message(
                    token,
                    room_id,
                    "/weather <city>\n/iss\n/help\n/quit"
                )

            elif message_text.lower().startswith("/weather"):

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


if __name__ == '__main__':
    main()
