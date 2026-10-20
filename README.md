# 🚀 Space Bot API Investigation Sheet

**Total Marks: 40**  
**TASK 1: Collect Required API Documentation**

This investigation sheet helps you gather key technical information from the three APIs required for the Space Bot project: **Webex Messaging API**, **ISS Current Location API**, **Weather API** and a **Geocoding API** , plus the Python time module. Also furhter investigate the application of Web Architecture and MVC design pattern in development of the Bot

---

##  Webex Messaging API (4 marks)

| Criteria | Details |
|---------|---------|
| API Base URL | `https://webexapis.com/v1` |
| Authentication Method | OAuth 2.0 **Bearer token** in the `Authorization` header. AstroBot uses a *personal access token* from developer.webex.com, which acts as your own account and expires 12 hours after you sign in to the Developer Portal. Bot and integration tokens are sent the same way. |
| Endpoint to list rooms | `GET /rooms` (`https://webexapis.com/v1/rooms`). Optional query parameters: `type` (`direct` or `group`), `sortBy` (`id`, `lastactivity` or `created`) and `max` (1–1000, default 100). |
| Endpoint to get messages | `GET /messages?roomId={roomId}&max={n}`. `roomId` is **required**, and `max` defaults to 50. Messages come back newest first, so `max=1` returns only the latest one. |
| Endpoint to send message | `POST /messages` with a JSON body such as `{"roomId": "...", "text": "..."}`. A `markdown` field can be used for rich text, with `text` as the plain-text fallback. The maximum message length is 7439 bytes. |
| Required headers | `Authorization: Bearer <access token>` on every request, plus `Content-Type: application/json` on the `POST`. (`Accept: application/json` is optional.) |
| Sample full GET or POST request | `curl -X POST "https://webexapis.com/v1/messages" -H "Authorization: Bearer $WEBEX_ACCESS_TOKEN" -H "Content-Type: application/json" -d '{"roomId": "Y2lzY29zcGFyazovL3VzL1JPT00v...", "text": "Hello from AstroBot"}'` |

**Example response for `GET /messages?roomId=...&max=1`** (the documented format, trimmed to the fields AstroBot reads; the `text` has been changed to an AstroBot command):

```json
{
  "items": [
    {
      "id": "Y2lzY29zcGFyazovL3VzL01FU1NBR0UvOTJkYjNiZTAtNDNiZC0xMWU2LThhZTktZGQ1YjNkZmM1NjVk",
      "roomId": "Y2lzY29zcGFyazovL3VzL1JPT00vYmJjZWIxYWQtNDNmMS0zYjU4LTkxNDctZjE0YmIwYzRkMTU0",
      "roomType": "group",
      "text": "/weather London",
      "personId": "Y2lzY29zcGFyazovL3VzL1BFT1BMRS9mNWIzNjE4Ny1jOGRkLTQ3MjctOGIyZi1mOWM0NDdmMjkwNDY",
      "personEmail": "matt@example.com",
      "created": "2015-10-18T14:26:16+00:00"
    }
  ]
}
```

**Other findings that affect the bot**

- **Rate limiting:** Webex answers `429 Too Many Requests` with a `Retry-After` header that says how long to wait. Most endpoints allow about 300 requests a minute; `/messages` has a higher, dynamically adjusted quota. AstroBot polls once every 5 seconds (12 requests a minute).
- **Bot accounts:** in group spaces, a bot account can only read messages that @mention it. This is why AstroBot uses a personal access token, which can read every message in the selected room.
- **Personal tokens:** any message AstroBot sends appears as coming from you, so the bot has to recognise and skip its own replies when it reads the latest message.

---

##  ISS Current Location API (2 marks)

| Criteria | Details |
|---------|---------|
| API Base URL | `http://api.open-notify.org`. HTTP only: HTTPS connections to this host are refused. |
| Endpoint for current ISS location | `GET /iss-now.json` (`http://api.open-notify.org/iss-now.json`). No authentication and no parameters. |
| Sample response format (example JSON) | Live response captured on 23 Oct 2026 (below) |

```json
{
  "timestamp": 1792780126,
  "message": "success",
  "iss_position": {
    "latitude": "10.0567",
    "longitude": "80.7557"
  }
}
```

**Findings**

- `timestamp` is a Unix epoch time in seconds (UTC) for when the position was valid. `1792780126` converts to **2026-10-23 18:28:46 UTC** (see the epoch section below).
- `latitude` and `longitude` are returned as **strings**, so AstroBot converts them with `float()` before reverse geocoding and formatting them.
- `message` is `"success"` when the request worked.
- Poll rate: the docs ask each client to poll at most about once every 5 seconds, since the position is only recalculated once a second. AstroBot calls this API only when someone sends `/iss`.
- Because the API is plain HTTP, its responses could be read or altered in transit. No credentials are ever sent to it, so the only risk is to the data's integrity.
- **Reliability:** Open Notify is a volunteer-run service. On 23 Oct 2026, one in four direct `curl` calls hung for the full 12-second timeout, another took 3.3 seconds, and one bot test failed with `ConnectTimeout`. AstroBot therefore waits at most 5 seconds for it and then switches to a backup provider.

**Backup ISS provider: "Where the ISS at?"**

| Criteria | Details |
|---------|---------|
| API Base URL | `https://api.wheretheiss.at/v1` (HTTPS) |
| Endpoint | `GET /satellites/25544` (25544 is the ISS's NORAD catalogue ID). Optional parameters: `units` (`kilometers` or `miles`) and `timestamp`. |
| Authentication | None. The docs ask clients to stay at roughly one request per second. |
| Used for | Automatic fallback in `get_iss_backup_position()`, which reshapes the reply into Open Notify's format. Unlike Open Notify, `latitude` and `longitude` are numbers. |

```json
{
  "name": "iss",
  "id": 25544,
  "latitude": -3.5136102100201,
  "longitude": -110.36503394941,
  "altitude": 422.80524224197,
  "velocity": 27567.288735574,
  "visibility": "daylight",
  "timestamp": 1792781908,
  "units": "kilometers"
}
```
*(Live response captured on 23 Oct 2026, trimmed: the `footprint`, `daynum` and `solar_lat`/`solar_lon` fields are omitted.)*

---

##  Geocoding API (4 marks)

| Criteria | Details |
|---------|---------|
| Provider used (Choose one) | **OpenWeatherMap Geocoding API.** It uses the same account and API key as the Weather API, so the bot needs only one weather key. |
| API Base URL | `https://api.openweathermap.org/geo/1.0`. The docs show `http://`, but HTTPS works and keeps the API key encrypted in transit. |
| Endpoint for geocoding | `GET /direct?q={city name},{state code},{country code}&limit={limit}&appid={API key}` (place name to coordinates) |
| Endpoint for reverse geocoding | `GET /reverse?lat={lat}&lon={lon}&limit={limit}&appid={API key}` (coordinates to place name) |
| Authentication method | API key passed as the `appid` query parameter |
| Required query parameters | Direct: `q` and `appid`; `limit` is optional, up to 5 results. Reverse: `lat`, `lon` and `appid`; `limit` is optional. Country codes in `q` use ISO 3166, e.g. `q=Paris,FR`. |
| Sample request with latitude/longitude | `https://api.openweathermap.org/geo/1.0/reverse?lat=51.5098&lon=-0.1180&limit=1&appid={API key}` |
| Sample JSON response (formatted example) | First result of the documented reverse-geocoding example (below; the `local_names` translations are omitted) |

```json
[
  {
    "name": "City of London",
    "lat": 51.5128,
    "lon": -0.0918,
    "country": "GB"
  }
]
```

**Findings**

- Both endpoints return a JSON **array**, best match first. AstroBot asks for `limit=1` and uses `data[0]`.
- A direct lookup for `London` with `limit=5` returns London (GB), City of London, London (Ontario, CA), Chelsea and London (Kentucky, US). Adding a country code (`London,GB`) makes the result unambiguous.
- `state` is only present for some locations, so the bot reads it with `.get()` and handles it being missing.
- **Reverse geocoding over the ocean returns an empty array `[]`.** The ISS is over water most of the time, so AstroBot then shows *"Over Ocean / No Nearby City"*.

---


##  Weather API (3 marks)

| Criteria | Details |
|---------|---------|
| API Provider (Choose one) | **OpenWeather Current Weather Data API.** The free plan allows 60 calls a minute and 1,000,000 calls a month, and includes the Geocoding API. |
| API Base URL | `https://api.openweathermap.org/data/2.5` |
| Endpoint for current weather | `GET /weather?lat={lat}&lon={lon}&appid={API key}&units=metric` |
| Authentication method | API key passed as the `appid` query parameter. A new key activates automatically up to 2 hours after registration; until then every call returns `401 Invalid API key`. |
| Required query parameters | `lat`, `lon` and `appid`. Optional: `units` (`standard` is the default and gives Kelvin; `metric` gives °C and m/s), `lang` and `mode`. Looking a city up by name (`q=`) is deprecated, so AstroBot gets coordinates from the Geocoding API first. |
| Sample JSON response (formatted example) | The documented example (below). It uses the default `standard` units, so `temp` is in Kelvin. |

```json
{
  "coord": { "lon": 10.99, "lat": 44.34 },
  "weather": [
    { "id": 501, "main": "Rain", "description": "moderate rain", "icon": "10d" }
  ],
  "base": "stations",
  "main": {
    "temp": 298.48,
    "feels_like": 298.74,
    "temp_min": 297.56,
    "temp_max": 300.05,
    "pressure": 1015,
    "humidity": 64,
    "sea_level": 1015,
    "grnd_level": 933
  },
  "visibility": 10000,
  "wind": { "speed": 0.62, "deg": 349, "gust": 1.18 },
  "rain": { "1h": 3.16 },
  "clouds": { "all": 100 },
  "dt": 1661870592,
  "sys": {
    "type": 2,
    "id": 2075663,
    "country": "IT",
    "sunrise": 1661834187,
    "sunset": 1661882248
  },
  "timezone": 7200,
  "id": 3163858,
  "name": "Zocca",
  "cod": 200
}
```

**Fields AstroBot uses**

| Field | Meaning | Used for |
|-------|---------|----------|
| `weather[0].id`, `weather[0].description` | Condition code (2xx thunderstorm, 3xx drizzle, 5xx rain, 6xx snow, 7xx fog/haze, 800 clear, 80x clouds) and its text | Conditions line; rain, snow and fog rule out stargazing |
| `main.temp`, `main.feels_like`, `main.humidity` | Temperature (°C with `units=metric`) and relative humidity (%) | Temperature and humidity lines |
| `clouds.all` | Cloud cover (%) | Main input to the stargazing verdict |
| `visibility` | Visibility in metres, capped at 10,000 | Haze check in the stargazing verdict |
| `wind.speed` | Wind speed (m/s with `metric`) | Wind line (strong wind shakes telescopes) |
| `dt`, `timezone`, `sys.sunrise`, `sys.sunset` | UTC epoch times and the location's offset from UTC in seconds | Local observation time, sunrise and sunset, and whether it is currently dark |
| `name`, `sys.country` | Place name and two-letter country code. Over the ocean `name` is an empty string and `country` is missing. | Location line, with an "Unknown" fallback |

---

##  Epoch to Human Time Conversion (Python time module) (2 marks)

| Criteria | Details |
|---------|---------|
| Library used | `time` (Python standard library). `datetime` is also used, to show weather times in each city's local time. |
| Function used to convert epoch | `time.gmtime()` converts epoch seconds to a UTC `struct_time`, and `time.strftime()` formats it as text. Both are wrapped in `epoch_to_utc()` in `astro_bot.py`. |
| Sample code to convert timestamp | See the code below |
| Output (human-readable time) | `2026-10-23 18:28:46 UTC` |

```python
import time

timestamp = 1792780126                      # "timestamp" field from the ISS API response
utc_time = time.gmtime(timestamp)           # struct_time in UTC
print(time.strftime("%Y-%m-%d %H:%M:%S UTC", utc_time))   # -> 2026-10-23 18:28:46 UTC
```

**Findings**

- The Python docs define the epoch as *"January 1, 1970, 00:00:00 (UTC) on all platforms"*. API timestamps are seconds since that moment.
- `time.gmtime()` was chosen over `time.localtime()` and `time.ctime()` because those two use the **server's** time zone. On this PC (UK, BST) `time.ctime(1792780126)` gives `Fri Oct 23 19:28:46 2026`, an hour ahead of UTC. The ISS is never in the server's time zone, so its time is shown in UTC.
- For `/weather`, OpenWeather supplies `dt`, `sys.sunrise` and `sys.sunset` (UTC epoch) plus `timezone` (the offset in seconds). `format_local_time()` uses `datetime.fromtimestamp(ts, tz=timezone(timedelta(seconds=offset)))` to show them in the **city's own local time**. For example, Sydney showed `Sat 24 Oct 2026, 05:59` when UTC was 18:59 on 23 Oct.

---

##  Extended Feature API ( 3 marks)

| Criteria | Details |
|---------|---------|
| API Provider | **Open-Meteo Forecast API**: free, open-source weather and astronomy data, used for the new `/sky <city>` command |
| API Base URL | `https://api.open-meteo.com/v1` |
| Endpoint | `GET /forecast` |
| Authentication method | None for non-commercial use. An `apikey` is only needed for the commercial `customer-` API. |
| Required query parameters | `latitude` and `longitude`. AstroBot also sends `hourly=cloud_cover,visibility,precipitation_probability,is_day`, `daily=sunrise,sunset,moonrise,moonset,moon_phase`, `timezone=auto` (times in the city's local time; required when asking for daily values), `past_days=1` and `forecast_days=2`. |
| Sample JSON response (formatted example) | Live response for London captured on 23 Oct 2026 (below), trimmed to three evening hours and one day |

```json
{
  "latitude": 51.51147,
  "longitude": -0.13078308,
  "utc_offset_seconds": 3600,
  "timezone": "Europe/London",
  "timezone_abbreviation": "GMT+1",
  "elevation": 16.0,
  "hourly_units": { "time": "iso8601", "cloud_cover": "%", "visibility": "m", "precipitation_probability": "%", "is_day": "" },
  "hourly": {
    "time": ["2026-10-23T20:00", "2026-10-23T21:00", "2026-10-23T22:00"],
    "cloud_cover": [78, 91, 66],
    "visibility": [26840.0, 28260.0, 32020.0],
    "precipitation_probability": [39, 20, 6],
    "is_day": [0, 0, 0]
  },
  "daily_units": { "time": "iso8601", "sunrise": "iso8601", "sunset": "iso8601", "moonrise": "iso8601", "moonset": "iso8601", "moon_phase": "fraction" },
  "daily": {
    "time": ["2026-10-23"],
    "sunrise": ["2026-10-23T07:38"],
    "sunset": ["2026-10-23T17:50"],
    "moonrise": ["2026-10-23T16:33"],
    "moonset": ["2026-10-23T04:06"],
    "moon_phase": [0.403]
  }
}
```

**Why Open-Meteo?** It was one of the suggested APIs and is the one most useful for *planning* observation nights:

- It forecasts **hourly cloud cover**, which matters most for stargazing. OpenWeather's free current-weather call only describes the present moment.
- It provides **moonrise, moonset and moon phase**. A bright Moon washes out faint galaxies and nebulae, so these decide what is worth observing.
- It needs **no API key**, so there is no extra secret to manage and nothing to sign up for. It is reached over HTTPS.
- `/sky` reuses the OpenWeather geocoding call (`get_city_coordinates()`) to turn a city name into coordinates, so the extension fits into the existing structure.

**Findings from testing the data**

- Hourly `time` values are **local clock times without an offset** (with `timezone=auto`), so the bot compares them with the city's local "now", computed from `utc_offset_seconds`.
- `moon_phase` is not documented on the docs page. Fetching a month of values showed it climbs steadily from 0 to 1 through the lunar cycle: it wrapped from 0.993 to 0.026 at the 10 Oct 2026 new moon and passed 0.5 at the 26 Oct full moon. So **0 = new, 0.25 = first quarter, 0.5 = full, 0.75 = last quarter**, and the illuminated fraction is (1 − cos 2π·phase) / 2. For 0.403 that gives about 91%.
- `moonrise`/`moonset` can be `null` on days when the Moon does not rise or set, so the bot skips missing values.
- `is_day` (1 or 0) marks the dark hours. In places with the midnight sun no hour is dark, and the bot says so instead of reporting an empty forecast.

**How `/sky` turns the data into advice** (`ASTRONOMY EXTENSION FUNCTIONS` in `astro_bot.py`)

1. `get_night_hours()` takes the dark hours from now until the next sunrise. If fewer than 3 are left (a request at dawn), it moves on to the next night.
2. `find_best_window()` finds the longest run of hours with cloud cover of 30% or less and a rain chance under 50%.
3. `describe_moon()` names the phase and works out how much of the Moon is lit. `describe_moon_visibility()` reports moonrise and moonset during the dark hours.
4. `assess_sky()` gives a Good, Fair or Poor verdict from the average cloud cover. It then adds moonlight advice (dark skies for galaxies, or a bright Moon that suits the Moon and planets) and a warning if the forecast visibility drops below 2 km (mist or fog).

Example reply (live, 23 Oct 2026):

```text
🔭 Stargazing forecast for London, England, GB, night of Fri 23 Oct
🌇 Sunset 17:50 · 🌅 Sunrise 07:39 (local time)
☁️ Cloud after dark: 48% on average (lowest 0% at 02:00)
✨ Best viewing window: 00:00-04:00 (cloud 30% or less)
🌧️ Highest chance of rain: 39%
🌔 Moon: Waxing Gibbous, 91% lit, sets 05:26
🔭 Verdict: ⚠️ Fair - partly cloudy with clear spells; the bright Moon favours the Moon and planets over faint galaxies
```

--- 

##  Evaluation – Web Architecture, MVC Design & Security 

In this section, evaluate how web technologies, architecture, and design patterns have been applied in your **AstroBot**. Your responses must relate directly to your implementation and include reflection on your design decisions.

---

###  Web Architecture – Client–Server Model (3 marks)

Explain how the client–server model applies to your AstroBot:

- Identify the **client** 
- Identify the **server(s)** 
- Describe how data flows between:
  - User, AstroBot and APIs

Include a **simple block diagram** to illustrate this interaction.

####  Security Considerations: (3 marks )
- Consider but not limiting to secure handling of API keys and tokens, API rate limiting, and Input validation (e.g., handling user commands safely), include examples from code where necessary to illustrate.

---

###  RESTful API Usage in Your Application (3 marks )

Explain how REST APIs are used in your AstroBot: 

- Describe how HTTP methods (GET, POST) are used  
- Explain how your bot interacts with APIs (Webex, Weather, ISS, Geocoding)  
- Describe how JSON responses are received and processed  

Note: Relate your explanation directly to your code for higher grade. 

#### Security Considerations: (2 marks)
- Check response status codes, Handling invalid or unexpected API responses, Avoiding excessive API calls

---

###  MVC Design Pattern in AstroBot (3 Marks)

Explain how the **Model–View–Controller (MVC)** pattern applies to your solution:
Provide a short example based on your implementation

| Component   | Description and Example (Relate to your Bot) |
|------------|----------------------------------|
| **Model**  |  |
| **View**   |  |
| **Controller** |  |

---

### 📝 Reflection and Evaluation ( 8 marks )

Reflect on your AstroBot (400 words):

- How effective is your bot in meeting the Astronomy Club’s needs?  
- What design decisions worked well?  
- What challenges did you face when integrating APIs?  
- What security risks did you identify and how were they handled?  
- How could your solution be improved in the future?  

---

 **Tip:** Link your answers directly to your code and examples for higher marks.
### Notes

- Use official documentation for accuracy (e.g. developer.webex.com, locationiq.com or Mapbox, open-notify.org or other ISS API).
- Be prepared to explain your findings to your instructor or demo how you retrieved them using tools like Postman, Curl, or Python scripts.

---

###  Total: /40