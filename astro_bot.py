#Contains partially completed code with sections for you to complete
#IT IS MANDATORY TO USE THE RESOURCE PROVIDED
#The starter code is structured into functions and modules. You are required to complete the missing sections while maintaining this modular design.  Further step by step instructions can be found in the appendix A of this assignment brief. 
#For extended features implement it within the existing modular structure. The new feature must be triggered using a new command (e.g., /stars, /moon, /sky) and follow the same approach 
#Use Git for version control. Maintain a repository on GitHub to track your project’s progress and changes. Ensure regular commits for each step with meaningful messages that document your step by stepdevelopment process. 

# =========================
# REQUIRED LIBRARIES
# =========================

import #complete the import statement to include the requests library
import #complete the import statement to include the json library
import #complete the import statement to include the time library
from #complete the import statement to include the datetime library

# =========================
# CONFIGURATION FUNCTIONS
# =========================
def get_webex_token():
    choice = input("Use hard-coded Webex token? (y/n): ").lower()
    if choice == "n":
        token = input("Enter your Webex Access Token: ")
        return f"Bearer {token}"
    else:
        return "Bearer YOUR_WEBEX_TOKEN"

def get_api_key(prompt, hardcoded_key):
  #complete the function to get the API key from user input or use a hardcoded key

# =========================
# WEBEX FUNCTIONS
# =========================
def get_rooms(token):
    url = #complete the URL to fetch rooms from Webex API
    headers = #complete the headers dictionary to include the Authorization header with the token
    response = #complete the request to get rooms using requests.get with the url and headers

    if response.status_code != #complete the condition to check if the response status code is not xxx:
        print("Error fetching rooms:", response.status_code)
        return []

    return response.json().get("items", [])


def print_rooms(rooms):
    for room in rooms:
        print(#complete the print statement to display the room title and id)


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

    token = get_webex_token()

    weather_key = get_api_key(
        "Weather API key",
        "YOUR_OPENWEATHER_API_KEY"
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
