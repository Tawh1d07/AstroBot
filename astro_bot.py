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

import math  # moon illumination from the moon phase
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
SKY_API_URL = "https://api.open-meteo.com/v1/forecast"  # /sky extension (no key needed)

REQUEST_TIMEOUT = 10  # seconds to wait for any API before giving up
ISS_TIMEOUT = 5  # shorter wait for Open Notify, so the backup ISS API is tried sooner
POLL_INTERVAL = 5  # seconds between checks for new Webex messages

CLEAR_SKY_MAX_CLOUD = 30  # % cloud cover still counted as a clear spell for /sky
RAIN_LIKELY_CHANCE = 50  # % chance of rain from which a /sky hour counts as wet
MIN_NIGHT_HOURS = 3  # if less darkness than this is left (e.g. at dawn), /sky forecasts the next night

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
        # Plain-text fallback for clients that cannot show rich text
        "text": message.replace("**", "").replace("`", ""),
        # Webex markdown needs two spaces before a newline to keep a single line break
        "markdown": message.replace("\n", "  \n")
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
        return f"❌ I couldn't find a city called '{city}'. Try adding a country code, e.g. `/weather Paris,FR`"

    weather = get_current_weather(location["lat"], location["lon"], api_key)

    if not weather:
        return "⚠️ Sorry, the weather data could not be retrieved right now. Please try again later."

    return format_weather_report(location, weather)


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
            return "⚠️ Sorry, the ISS location could not be retrieved right now. Please try again shortly."

    try:
        # Open Notify returns the coordinates as strings, e.g. "51.5072"
        lat = float(data["iss_position"]["latitude"])
        lon = float(data["iss_position"]["longitude"])
    except (KeyError, TypeError, ValueError):
        return "⚠️ Sorry, the ISS service returned incomplete data. Please try again shortly."

    location = reverse_geocode(lat, lon, api_key)

    place = "Over Ocean / No Nearby City"

    if location:
        place = format_place(location)

    # Weather at the point on Earth directly below the ISS
    weather = get_current_weather(lat, lon, api_key)

    return format_iss_report(lat, lon, data.get("timestamp"), place, weather)


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
# ASTRONOMY EXTENSION FUNCTIONS (/sky)
# =========================
MOON_PHASES = [
    ("New Moon", "🌑"), ("Waxing Crescent", "🌒"), ("First Quarter", "🌓"), ("Waxing Gibbous", "🌔"),
    ("Full Moon", "🌕"), ("Waning Gibbous", "🌖"), ("Last Quarter", "🌗"), ("Waning Crescent", "🌘"),
]
VERDICT_LABELS = ("✅ Good", "⚠️ Fair", "❌ Poor")
CLOUD_LABELS = ("mostly clear", "partly cloudy", "mostly cloudy")


def get_sky_forecast(city, api_key):
    # Reuse the OpenWeather geocoder to turn the city name into coordinates
    location = get_city_coordinates(city, api_key)

    if not location or location.get("lat") is None or location.get("lon") is None:
        return f"❌ I couldn't find a city called '{city}'. Try adding a country code, e.g. `/sky Paris,FR`"

    url = SKY_API_URL
    params = {
        "latitude": location["lat"],
        "longitude": location["lon"],
        "hourly": "cloud_cover,visibility,precipitation_probability,is_day",
        "daily": "sunrise,sunset,moonrise,moonset,moon_phase",
        "timezone": "auto",  # times come back in the city's own local time
        "past_days": 1,  # yesterday's sunset and moonrise are needed for requests after midnight
        "forecast_days": 2,
    }

    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)

    if response.status_code != 200:
        print("Open-Meteo API error:", response.status_code)
        return "⚠️ Sorry, the stargazing forecast could not be retrieved right now. Please try again later."

    forecast = response.json()
    night = get_night_hours(forecast)

    if not night:
        return (f"☀️ The sun does not set in {format_place(location)} during the forecast period "
                "(midnight sun), so there is no stargazing window.")

    return format_sky_report(location, forecast, night)


def get_night_hours(forecast, now=None):
    # The coming night's dark hours: from now (or sunset) until the sun rises again
    hourly = forecast.get("hourly", {})
    if now is None:
        # Open-Meteo times are the city's local clock times, so compare with its local time now
        offset = timedelta(seconds=forecast.get("utc_offset_seconds") or 0)
        now = (datetime.now(timezone.utc) + offset).replace(tzinfo=None)
    this_hour = now.replace(minute=0, second=0, microsecond=0)
    moon_events = get_moon_events(forecast.get("daily", {}))

    # Group the remaining dark hours into nights (runs of hours with is_day == 0)
    nights, current = [], []
    for index, stamp in enumerate(hourly.get("time", [])):
        hour = datetime.fromisoformat(stamp)
        if hour < this_hour:
            continue
        if hourly_value(hourly, "is_day", index) == 1:
            if current:
                nights.append(current)
                current = []
            continue
        current.append({
            "time": hour,
            "cloud": hourly_value(hourly, "cloud_cover", index),
            "visibility": hourly_value(hourly, "visibility", index),
            "rain": hourly_value(hourly, "precipitation_probability", index),
            "moon_up": is_moon_up(moon_events, hour),
        })
    if current:
        nights.append(current)

    # At dawn only a few dark hours are left, so forecast the next night instead
    if len(nights) > 1 and len(nights[0]) < MIN_NIGHT_HOURS:
        return nights[1]
    return nights[0] if nights else []


def hourly_value(hourly, key, index):
    # One value from an hourly list, or None if the list is missing or too short
    values = hourly.get(key) or []
    return values[index] if index < len(values) else None


def get_moon_events(daily):
    # Sorted (time, is_rise) pairs; Open-Meteo gives null on days without a moonrise or moonset
    events = []
    for key, is_rise in (("moonrise", True), ("moonset", False)):
        for stamp in daily.get(key) or []:
            if stamp:
                events.append((datetime.fromisoformat(stamp), is_rise))
    return sorted(events)


def is_moon_up(events, when):
    # The Moon is up if its last rise/set before 'when' was a rise
    earlier = [is_rise for event_time, is_rise in events if event_time <= when]
    if earlier:
        return earlier[-1]
    later = [is_rise for event_time, is_rise in events if event_time > when]
    return (not later[0]) if later else None


def get_moon_phase(forecast, night):
    # Open-Meteo's daily moon_phase for the date tonight's dark hours begin
    daily = forecast.get("daily", {})
    dates, phases = daily.get("time", []), daily.get("moon_phase", [])
    start_date = night[0]["time"].date().isoformat()
    if start_date in dates:
        index = dates.index(start_date)
        if index < len(phases):
            return phases[index]
    return None


def describe_moon(phase):
    # moon_phase runs 0 -> 1 through the cycle: 0 = new, 0.25 = first quarter, 0.5 = full, 0.75 = last quarter
    if phase is None:
        return "Unknown phase", "🌙", None
    name, emoji = MOON_PHASES[int(phase * 8 + 0.5) % 8]
    illumination = (1 - math.cos(2 * math.pi * phase)) / 2  # fraction of the Moon's disc that is lit
    return name, emoji, illumination


def find_best_window(night):
    # Longest run of consecutive dark hours with little cloud and a low chance of rain
    best, current = [], []
    for hour in night:
        clear = (hour["cloud"] is not None and hour["cloud"] <= CLEAR_SKY_MAX_CLOUD
                 and (hour["rain"] or 0) < RAIN_LIKELY_CHANCE)
        current = current + [hour] if clear else []
        if len(current) > len(best):
            best = current
    return best


def assess_sky(night, illumination):
    # Overall rating is the worse of the cloud and rain ratings; moonlight and fog advice follow
    clouds = [hour["cloud"] for hour in night if hour["cloud"] is not None]
    if not clouds:
        return "❔ Unknown - no cloud forecast"
    average = sum(clouds) / len(clouds)
    cloud_level = 0 if average <= CLEAR_SKY_MAX_CLOUD else 1 if average <= 60 else 2

    # Any wet hour caps the rating at Fair; rain for at least half the dark hours makes it Poor
    rain_chances = [hour["rain"] for hour in night if hour["rain"] is not None]
    wet_hours = [chance for chance in rain_chances if chance >= RAIN_LIKELY_CHANCE]
    rain_level = 0 if not wet_hours else 2 if len(wet_hours) * 2 >= len(night) else 1

    level = max(cloud_level, rain_level)
    verdict = f"{VERDICT_LABELS[level]} - {CLOUD_LABELS[cloud_level]}"
    if rain_level:
        joiner = " but " if cloud_level == 0 else ", "
        timing = "for most of the night" if rain_level == 2 else "at times"
        verdict += f"{joiner}rain likely {timing} (up to {max(rain_chances):.0f}% chance)"
    elif cloud_level == 1 and find_best_window(night):
        verdict += " with clear spells"
    if not rain_chances:
        verdict += "; no rain forecast available"

    if level < 2:
        moon_free = [hour for hour in night if hour["moon_up"] is False]
        if (illumination is not None and illumination <= 0.25) or len(moon_free) >= 0.75 * len(night):
            verdict += "; dark skies, great for galaxies, nebulae and the Milky Way"
        elif illumination is not None and illumination >= 0.6:
            verdict += "; the bright Moon favours the Moon and planets over faint galaxies"

    visibilities = [hour["visibility"] for hour in night if hour["visibility"] is not None]
    if visibilities and min(visibilities) < 2000:
        verdict += "; mist or fog is possible"
    return verdict

# =========================
# FORMATTING FUNCTIONS
# =========================
# These build the chat replies. Lines are joined with "\n"; send_message() converts
# them to Webex markdown. Every value falls back to N/A or Unknown when it is missing.

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


def format_local_time(timestamp, offset_seconds, pattern="%a %d %b %Y, %H:%M"):
    # OpenWeather gives UTC epoch seconds plus the location's offset from UTC in seconds
    if timestamp is None:
        return "Unknown"
    local_zone = timezone(timedelta(seconds=offset_seconds or 0))
    return datetime.fromtimestamp(timestamp, tz=local_zone).strftime(pattern)


def format_coordinates(lat, lon):
    # e.g. 51.5072° N, 0.1276° W
    lat_side = "N" if lat >= 0 else "S"
    lon_side = "E" if lon >= 0 else "W"
    return f"{abs(lat):.4f}° {lat_side}, {abs(lon):.4f}° {lon_side}"


def summarise_weather(weather):
    # One-line summary of the weather below the ISS
    if not weather:
        return "Unavailable"
    description = (weather.get("weather") or [{}])[0].get("description", "unknown").capitalize()
    temperature = format_value(weather.get("main", {}).get("temp"), "°C")
    clouds = format_value(weather.get("clouds", {}).get("all"), "%", decimals=0)
    return f"{description}, {temperature}, {clouds} cloud cover"


def format_weather_report(location, weather):
    # Reply for /weather <city>
    conditions = (weather.get("weather") or [{}])[0]
    readings = weather.get("main", {})
    sun = weather.get("sys", {})
    offset = weather.get("timezone")
    visibility = weather.get("visibility")
    visibility_km = visibility / 1000 if visibility is not None else None

    lines = [
        f"🌤️ **Weather for {format_place(location)}**",
        f"🕒 Local time: {format_local_time(weather.get('dt'), offset)}",
        f"🌡️ Temperature: {format_value(readings.get('temp'), '°C')} "
        f"(feels like {format_value(readings.get('feels_like'), '°C')})",
        f"☁️ Conditions: {conditions.get('description', 'unknown').capitalize()}, "
        f"{format_value(weather.get('clouds', {}).get('all'), '%', decimals=0)} cloud cover",
        f"💧 Humidity: {format_value(readings.get('humidity'), '%', decimals=0)}",
        f"💨 Wind: {format_value(weather.get('wind', {}).get('speed'), ' m/s')}",
        f"👁️ Visibility: {format_value(visibility_km, ' km')}",
        f"🌅 Sunrise {format_local_time(sun.get('sunrise'), offset, '%H:%M')} · "
        f"🌇 Sunset {format_local_time(sun.get('sunset'), offset, '%H:%M')} (local time)",
        f"🔭 **Stargazing: {assess_stargazing(weather)}**",
    ]
    return "\n".join(lines)


def format_iss_report(lat, lon, timestamp, place, weather):
    # Reply for /iss, with a map link so users can see where the station is
    map_link = f"https://www.openstreetmap.org/?mlat={lat:.4f}&mlon={lon:.4f}#map=4/{lat:.4f}/{lon:.4f}"
    lines = [
        "🛰️ **International Space Station - live position**",
        f"🕒 Time: {epoch_to_utc(timestamp)}",
        f"📍 Coordinates: {format_coordinates(lat, lon)}",
        f"🌍 Location: {place}",
        f"🌦️ Weather below: {summarise_weather(weather)}",
        f"🗺️ Map: {map_link}",
    ]
    return "\n".join(lines)


def format_clock(moment):
    # Local clock time such as 21:00, or N/A
    return moment.strftime("%H:%M") if moment else "N/A"


def format_hour_range(hours, latest_end=None):
    # e.g. 22:00-02:00 for hourly slots starting at 22:00, 23:00, 00:00 and 01:00,
    # ending no later than latest_end (sunrise) because the last slot may only be partly dark
    end = hours[-1]["time"] + timedelta(hours=1)
    if latest_end is not None:
        end = min(end, latest_end)
    return f"{format_clock(hours[0]['time'])}-{format_clock(end)}"


def describe_moon_visibility(moon_events, start, end):
    # Moonrise/moonset during the dark period, e.g. "sets 05:26" - the sky is darkest while it is down
    changes = [f"{'rises' if is_rise else 'sets'} {format_clock(moment)}"
               for moment, is_rise in moon_events if start < moment < end]
    if changes:
        return ", ".join(changes)
    up = is_moon_up(moon_events, start)
    if up is None:
        return "rise and set times unavailable"
    return "above the horizon all night" if up else "below the horizon all night"


def format_sky_report(location, forecast, night):
    # Reply for /sky <city>: the night's cloud, best viewing window, Moon and an overall verdict
    daily = forecast.get("daily", {})
    sunsets = [datetime.fromisoformat(s) for s in daily.get("sunset") or [] if s]
    sunrises = [datetime.fromisoformat(s) for s in daily.get("sunrise") or [] if s]
    # The sunset that starts this night's darkness and the sunrise that ends it
    sunset = max((t for t in sunsets if t <= night[0]["time"] + timedelta(hours=1)), default=None)
    sunrise = min((t for t in sunrises if t >= night[-1]["time"]), default=None)
    night_of = (sunset or night[0]["time"]).strftime("%a %d %b")
    dark_from = max(sunset, night[0]["time"]) if sunset else night[0]["time"]
    dark_until = sunrise or night[-1]["time"] + timedelta(hours=1)

    cloudy_hours = [hour for hour in night if hour["cloud"] is not None]
    if cloudy_hours:
        average = sum(hour["cloud"] for hour in cloudy_hours) / len(cloudy_hours)
        clearest = min(cloudy_hours, key=lambda hour: hour["cloud"])
        cloud_line = (f"☁️ Cloud after dark: {average:.0f}% on average "
                      f"(lowest {clearest['cloud']}% at {format_clock(clearest['time'])})")
    else:
        cloud_line = "☁️ Cloud after dark: N/A"

    window = find_best_window(night)
    if window:
        window_line = (f"✨ Best viewing window: {format_hour_range(window, dark_until)} "
                       f"(cloud {CLEAR_SKY_MAX_CLOUD}% or less)")
    else:
        window_line = f"✨ Best viewing window: none - cloud stays above {CLEAR_SKY_MAX_CLOUD}% all night"

    rain_chances = [hour["rain"] for hour in night if hour["rain"] is not None]
    phase_name, moon_emoji, illumination = describe_moon(get_moon_phase(forecast, night))
    lit = f", {illumination:.0%} lit" if illumination is not None else ""

    moon_events = get_moon_events(daily)

    lines = [
        f"🔭 **Stargazing forecast for {format_place(location)}, night of {night_of}**",
        f"🌇 Sunset {format_clock(sunset)} · 🌅 Sunrise {format_clock(sunrise)} (local time)",
        cloud_line,
        window_line,
        f"🌧️ Highest chance of rain: {format_value(max(rain_chances, default=None), '%', decimals=0)}",
        f"{moon_emoji} Moon: {phase_name}{lit}, {describe_moon_visibility(moon_events, dark_from, dark_until)}",
        f"🔭 **Verdict: {assess_sky(night, illumination)}**",
    ]
    return "\n".join(lines)


def format_help():
    # Reply for /help (starts with an emoji, not "/", so it can never look like a command)
    return "\n".join([
        "🔭 **AstroBot commands**",
        "• `/weather <city>` - current weather and a stargazing verdict, e.g. `/weather London,GB`",
        "• `/iss` - where the International Space Station is right now",
        "• `/sky <city>` - tonight's stargazing forecast: cloud, best viewing window and the Moon",
        "• `/help` - show this list",
        "• `/quit` - stop AstroBot",
    ])

# =========================
# INPUT VALIDATION
# =========================
def validate_city(city, command):
    # Return an error message for an unusable city name, or None if it looks valid
    if not city:
        return f"ℹ️ Usage: `{command} <city>`, e.g. `{command} London,GB`"
    if len(city) > MAX_CITY_LENGTH or not CITY_PATTERN.fullmatch(city):
        return ("⚠️ Please send a plain city name using letters, spaces, commas, hyphens or apostrophes, "
                "e.g. `London,GB`")
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
                    reply = format_help()

                elif command == "/weather":
                    # validate_city() returns an error message, or None so the lookup runs
                    reply = validate_city(argument, command) or get_weather(argument, weather_key)

                elif command == "/iss":
                    reply = get_iss_location(weather_key)

                elif command == "/sky":
                    # Extension feature: tonight's stargazing forecast from Open-Meteo
                    reply = validate_city(argument, command) or get_sky_forecast(argument, weather_key)

                elif command == "/quit":
                    send_message(token, room_id, "🔭 AstroBot is shutting down. Clear skies!")
                    break

                else:
                    reply = "❓ Unknown command. Send `/help` to see what I can do."

            except requests.RequestException as error:
                print("API request failed:", type(error).__name__)
                reply = "⚠️ Sorry, I couldn't reach one of the data services. Please try again in a minute."
            except (KeyError, TypeError, ValueError) as error:
                print("Unexpected API data:", type(error).__name__, error)
                reply = "⚠️ Sorry, a data service sent an unexpected response. Please try again later."

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
