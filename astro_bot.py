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
import re  # validates city names typed by users
from getpass import getpass  # hides keys while they are typed

from dotenv import load_dotenv  # loads API keys from the git-ignored .env file

# =========================
# SETTINGS
# =========================
WEBEX_API_URL = "https://webexapis.com/v1"
GEOCODING_API_URL = "https://api.openweathermap.org/geo/1.0"
WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"
ISS_API_URL = "http://api.open-notify.org/iss-now.json"  # Open Notify only offers HTTP
ISS_BACKUP_API_URL = "https://api.wheretheiss.at/v1/satellites/25544"  # 25544 = the ISS's NORAD ID

REQUEST_TIMEOUT = 10  # seconds to wait for any API before giving up
ISS_TIMEOUT = 5  # shorter wait for Open Notify, so the backup ISS API is tried sooner
POLL_INTERVAL = 5  # seconds between checks for new Webex messages

MAX_CITY_LENGTH = 85
# Letters in any language, separated by spaces, commas, full stops, apostrophes or hyphens
CITY_PATTERN = re.compile(r"[^\W\d_]+(?:[ ,.'’-]+[^\W\d_]+)*\.?")

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
    url = f"{WEBEX_API_URL}/messages"
    headers = {"Authorization": token, "Content-Type": "application/json"}
    data = {
        "roomId": room_id,
        "text": message
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=REQUEST_TIMEOUT)
    except requests.RequestException as error:
        # A failed reply must not crash the bot; the next command can still succeed
        print("Could not send message:", type(error).__name__)
        return None

    if response.status_code != 200:
        print("Error sending message:", response.status_code)
        return None

    # The new message's ID lets the bot recognise its own reply when it polls
    return response.json().get("id")

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

    # A usable geocoding result must include coordinates
    if not location or location.get("lat") is None or location.get("lon") is None:
        return f"Sorry, I couldn't find a city called '{city}'. Try adding a country code, e.g. /weather Paris,FR"

    weather = get_current_weather(location["lat"], location["lon"], api_key)

    if not weather:
        return "Sorry, the weather data could not be retrieved right now. Please try again later."

    # Read every field with .get() so a missing value shows as N/A instead of crashing
    conditions = (weather.get("weather") or [{}])[0]
    readings = weather.get("main", {})
    return (
        f"Weather for {format_place(location)}\n"
        f"Temperature: {format_value(readings.get('temp'), '°C')}\n"
        f"Conditions: {conditions.get('description', 'Unknown')}\n"
        f"Humidity: {format_value(readings.get('humidity'), '%', decimals=0)}\n"
        f"Wind speed: {format_value(weather.get('wind', {}).get('speed'), ' m/s')}\n"
        f"Stargazing: {assess_stargazing(weather)}"
    )


def assess_stargazing(weather):
    # Rate the current conditions for stargazing from the weather code, cloud cover and visibility
    clouds = weather.get("clouds", {}).get("all")
    condition_id = (weather.get("weather") or [{}])[0].get("id")
    visibility = weather.get("visibility")

    # OpenWeather codes: 2xx-6xx = storms, drizzle, rain or snow; 7xx = mist, fog, haze or dust
    if condition_id is not None and condition_id < 700:
        verdict = "Poor - rain, snow or storms"
    elif condition_id is not None and condition_id < 800:
        verdict = "Poor - mist, fog or haze"
    elif clouds is None:
        verdict = "Unknown - no cloud data"
    elif clouds > 50:
        verdict = f"Poor - {clouds}% cloud cover"
    elif clouds > 20:
        verdict = f"Fair - {clouds}% cloud cover, look for clear gaps"
    elif visibility is not None and visibility < 5000:
        verdict = f"Fair - clear but hazy ({visibility / 1000:.1f} km visibility)"
    else:
        verdict = f"Good - {clouds}% cloud cover"

    # These are current conditions, so warn if the sun has not set yet
    if is_daytime(weather):
        verdict += " (it is daytime now - check again after sunset)"
    return verdict


def is_daytime(weather):
    # dt, sunrise and sunset are all UTC epoch seconds, so they compare directly
    now = weather.get("dt")
    sunrise = weather.get("sys", {}).get("sunrise")
    sunset = weather.get("sys", {}).get("sunset")
    if None in (now, sunrise, sunset):
        return False
    return sunrise <= now < sunset

# =========================
# ISS FUNCTIONS
# =========================
def reverse_geocode(lat, lon, api_key):
    url = f"{GEOCODING_API_URL}/reverse"
    params = {"lat": lat, "lon": lon, "limit": 1, "appid": api_key}

    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)

    if response.status_code != 200:
        print("Reverse geocoding API error:", response.status_code)
        return None

    # An empty list means there is no named place nearby (e.g. over the ocean)
    data = response.json()
    return data[0] if data else None


def get_iss_location(api_key):
    url = ISS_API_URL

    try:
        response = requests.get(url, timeout=ISS_TIMEOUT)
    except requests.RequestException as error:
        print("Open Notify ISS API unreachable:", type(error).__name__)
        response = None

    if response is not None and response.status_code == 200:
        data = response.json()
    else:
        # Open Notify is volunteer-run and sometimes times out, so try a second provider
        data = get_iss_backup_position()
        if data is None:
            return "Sorry, the ISS location could not be retrieved right now. Please try again shortly."

    try:
        # Open Notify returns the coordinates as strings, e.g. "51.5072"
        lat = float(data["iss_position"]["latitude"])
        lon = float(data["iss_position"]["longitude"])
    except (KeyError, TypeError, ValueError):
        return "Sorry, the ISS service returned incomplete data. Please try again shortly."

    location = reverse_geocode(lat, lon, api_key)

    place = "Over Ocean / No Nearby City"

    if location:
        place = format_place(location)

    # Weather at the point on Earth directly below the ISS
    weather = get_current_weather(lat, lon, api_key)
    conditions = "Unavailable"
    if weather:
        description = (weather.get("weather") or [{}])[0].get("description", "Unknown")
        conditions = f"{description}, {format_value(weather.get('main', {}).get('temp'), '°C')}"

    return (
        f"ISS location at {epoch_to_utc(data.get('timestamp'))}\n"
        f"Latitude: {lat}\n"
        f"Longitude: {lon}\n"
        f"Location: {place}\n"
        f"Weather below: {conditions}"
    )


def get_iss_backup_position():
    # Backup source: the "Where the ISS at?" API (HTTPS, no key, numeric coordinates)
    try:
        response = requests.get(ISS_BACKUP_API_URL, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as error:
        print("Backup ISS API unreachable:", type(error).__name__)
        return None

    if response.status_code != 200:
        print("Backup ISS API error:", response.status_code)
        return None

    # Reshape the reply into Open Notify's format so get_iss_location() handles both the same way
    data = response.json()
    return {
        "timestamp": data.get("timestamp"),
        "iss_position": {"latitude": data.get("latitude"), "longitude": data.get("longitude")},
    }


def epoch_to_utc(timestamp):
    # time.gmtime() turns Unix epoch seconds into a UTC struct_time; strftime() formats it
    if timestamp is None:
        return "Unknown time"
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(timestamp))

# =========================
# DATA HANDLING HELPERS
# =========================
def format_value(value, unit="", decimals=1):
    # Show a reading with its unit, or N/A when the API did not provide it
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.{decimals}f}{unit}"
    except (TypeError, ValueError):
        return "N/A"


def format_place(location):
    # Join whichever of name, state and country the geocoding API returned
    parts = [location.get("name"), location.get("state"), location.get("country")]
    return ", ".join(part for part in parts if part) or "Unknown location"


def validate_city(city, command):
    # Return an error message for an unusable city name, or None if it looks valid
    if not city:
        return f"Usage: {command} <city>, e.g. {command} London,GB"
    if len(city) > MAX_CITY_LENGTH or not CITY_PATTERN.fullmatch(city):
        return "Please send a plain city name using letters, spaces, commas, hyphens or apostrophes, e.g. London,GB"
    return None

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

    try:
        rooms = get_rooms(token)
    except requests.RequestException as error:
        # Only the error type is printed: request errors can include the URL and key
        print("Could not reach Webex:", type(error).__name__)
        rooms = []

    if not rooms:
        print("No Webex rooms found. Check your access token and network connection.")
        return

    print_rooms(rooms)
    room_id = select_room(rooms)

    # Remember the newest existing message so old messages are not treated as commands
    try:
        last_message_id, _ = get_latest_message(token, room_id)
    except requests.RequestException as error:
        print("Could not reach Webex:", type(error).__name__)
        return
    print("AstroBot is listening for commands. Press Ctrl+C to stop.")

    while True:

        # Sleeping at the top of the loop means 'continue' can never skip the delay
        time.sleep(POLL_INTERVAL)

        try:
            message_id, message_text = get_latest_message(token, room_id)
        except requests.RequestException as error:
            # A network blip should not stop the bot; try again on the next poll
            print("Could not reach Webex:", type(error).__name__)
            continue

        if message_id and message_id != last_message_id:

            last_message_id = message_id
            message_text = message_text.strip()

            print(f"Received: {message_text}")

            # Only messages starting with "/" are commands; ignore normal chat
            if not message_text.startswith("/"):
                continue

            # Split e.g. "/weather London,GB" into the command word and its argument
            parts = message_text.split(maxsplit=1)
            command = parts[0].lower()
            argument = parts[1].strip() if len(parts) > 1 else ""

            try:
                if command == "/help":
                    reply = "AstroBot commands:\n/weather <city>\n/iss\n/help\n/quit"

                elif command == "/weather":
                    # validate_city() returns an error message, or None so the lookup runs
                    reply = validate_city(argument, command) or get_weather(argument, weather_key)

                elif command == "/iss":
                    reply = get_iss_location(weather_key)

                elif command == "/quit":
                    send_message(token, room_id, "AstroBot shutting down.")
                    break

                else:
                    reply = "Unknown command. Use /help"

            except requests.RequestException as error:
                print("API request failed:", type(error).__name__)
                reply = "Sorry, I couldn't reach one of the data services. Please try again in a minute."
            except (KeyError, TypeError, ValueError) as error:
                print("Unexpected API data:", type(error).__name__, error)
                reply = "Sorry, a data service sent an unexpected response. Please try again later."

            # Replies are posted with the user's own token, so they come back as the newest
            # message on the next poll; remembering the reply's ID stops the bot answering itself
            reply_id = send_message(token, room_id, reply)
            if reply_id:
                last_message_id = reply_id


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nAstroBot stopped.")
