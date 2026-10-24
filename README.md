# 🚀 Space Bot API Investigation Sheet

**Total Marks: 40**  
**TASK 1: Collect Required API Documentation**

This investigation sheet helps you gather key technical information from the three APIs required for the Space Bot project: **Webex Messaging API**, **ISS Current Location API**, **Weather API** and a **Geocoding API** , plus the Python time module. Also furhter investigate the application of Web Architecture and MVC design pattern in development of the Bot

---

##  Webex Messaging API

**Official documentation:** [Getting started](https://developer.webex.com/messaging/docs/getting-started) · [List Rooms](https://developer.webex.com/messaging/docs/api/v1/rooms/list-rooms) · [List Messages](https://developer.webex.com/messaging/docs/api/v1/messages/list-messages) · [Create a Message](https://developer.webex.com/messaging/docs/api/v1/messages/create-a-message) · [API basics: handling 429 errors](https://developer.webex.com/docs/basics#handling-429-errors) (the same page explains markdown line breaks)

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

##  ISS Current Location API

**Official documentation:** [Open Notify: ISS Current Location](http://open-notify.org/Open-Notify-API/ISS-Location-Now/) · backup provider: [Where the ISS at? REST API](https://wheretheiss.at/w/developer)

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

##  Geocoding API

**Official documentation:** [OpenWeather Geocoding API](https://openweathermap.org/api/geocoding-api)

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


##  Weather API

**Official documentation:** [Current Weather Data](https://openweathermap.org/current) · [FAQ: key activation and error 401](https://openweathermap.org/faq#error401) · [Pricing and free-plan limits](https://openweathermap.org/price) · [Licences and attribution](https://openweathermap.org/full-price#licenses)

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

**Licence and attribution:** OpenWeather's self-service plans, the free plan included, are provided under the Open Database License (ODbL). OpenWeather requires "visible attribution to OpenWeather" on the screen where its data appears and recommends the line *"Weather data © OpenWeather"*. AstroBot ends every `/weather` and `/iss` reply with that line (`OPENWEATHER_CREDIT` in `astro_bot.py`).

---

##  Epoch to Human Time Conversion (Python time module) (2 marks)

**Official documentation:** [`time` module](https://docs.python.org/3/library/time.html) ([`time.gmtime()`](https://docs.python.org/3/library/time.html#time.gmtime), [`time.strftime()`](https://docs.python.org/3/library/time.html#time.strftime)) · [`datetime.fromtimestamp()`](https://docs.python.org/3/library/datetime.html#datetime.datetime.fromtimestamp)

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

##  Extended Feature API

**Official documentation:** [Open-Meteo Forecast API](https://open-meteo.com/en/docs) · [Terms of use (free-tier limits)](https://open-meteo.com/en/terms) · [Licence (CC BY 4.0, attribution)](https://open-meteo.com/en/licence)

| Criteria | Details |
|---------|---------|
| API Provider | **Open-Meteo Forecast API**: free, open-source weather and astronomy data, used for the new `/sky <city>` command |
| API Base URL | `https://api.open-meteo.com/v1` |
| Endpoint | `GET /forecast` |
| Authentication method | None for non-commercial use. An `apikey` is only needed for the commercial `customer-` API. The free tier is for non-commercial use only and allows fewer than 10,000 calls a day, 5,000 an hour and 600 a minute. |
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

**What the official docs define** (quoted from the [parameter definitions](https://open-meteo.com/en/docs))

- `is_day`: *"1 if the current time step has daylight, 0 at night."* This marks the dark hours.
- `cloud_cover`: *"Total cloud cover as an area fraction"*, an instant value in %. `visibility`: *"Viewing distance in meters. Influenced by low clouds, humidity and aerosols"*, also instant.
- `precipitation_probability`: *"Probability of precipitation with more than 0.1 mm of the preceding hour."* The value stamped 23:00 therefore describes 22:00–23:00, so AstroBot reads the **next** hour's value for each hourly slot.
- `sunrise`, `sunset`: *"Sun rise and set times."*
- `timezone`: the resulting offset is *"returned as `utc_offset_seconds` and used for ISO 8601 timestamps and daily boundaries throughout the response."* The times are local clock times with no offset written in, so the bot compares them with the city's local "now" (`local_now()`). The docs also warn that *"Daylight saving time (DST) changes within the requested range are ignored"*: around a clock change (UK clocks go back on 25 Oct 2026), times after the change can be shown an hour off.

**Moon fields: assumptions, not documentation**

The docs only list "Moonrise", "Moonset" and "Moon Phase" in their variable picker. They give no definition, scale or time of day for them. AstroBot's Moon output therefore rests on the assumptions below, worked out from observed data rather than official documentation:

| Field | What the docs say | What AstroBot assumes | Evidence | If the assumption is wrong |
|---|---|---|---|---|
| `moon_phase` | Name only; the response gives the unit `fraction` | Position in the lunar cycle from 0 to 1: 0 = new, 0.25 = first quarter, 0.5 = full, 0.75 = last quarter | Over 32 days of London values (7 Oct to 7 Nov 2026) it climbed steadily, wrapped from 0.993 to 0.026 at the 10 Oct new moon and read 0.510 on 26 Oct, the full moon | The phase name, the Moon emoji, the "% lit" figure and the moonlight advice in the verdict would all be wrong |
| "% lit" | Not provided by Open-Meteo | Calculated as (1 − cos 2π·phase) / 2 from the assumed phase | 0.403, three days before full moon, gives 91% | Even if the phase assumption holds, this is an approximation that treats the Moon as moving at a constant speed |
| Time of day of the daily `moon_phase` | Not stated | Used for the date the night begins | None | The phase advances about 0.034 a day, which can shift "% lit" by up to about 10 percentage points a day around the quarter phases |
| `moonrise`, `moonset` | Names only | Local clock times of the Moon crossing the horizon (same time zone as sunrise and sunset); `null` means no such event that day | The times fit the phase (a waxing gibbous Moon rising at 16:33 and setting before dawn). Over 108 days (23 Jul to 7 Nov 2026), `moonrise` was `null` on 4 days and `moonset` on 4 days, each time between neighbours just before and after midnight (e.g. 23:45, `null`, 00:40) | The Moon line (e.g. "sets 05:26") and the moon-free hours used in the verdict would be wrong |

These assumptions are also marked in the code comments of `get_moon_events()`, `get_moon_phase()` and `describe_moon()`. If Open-Meteo documents these fields in future, those functions are the only places to update.

**How `/sky` turns the data into advice** (`ASTRONOMY EXTENSION FUNCTIONS` in `astro_bot.py`)

1. `get_sky_forecast()` first checks the response is a JSON object, before anything reads it. Then `local_now()` works out the city's local time, and `find_forecast_problem()` checks the forecast is complete enough to use: at least 24 upcoming hours, each with an `is_day` value of 0 or 1. If either check fails (for example, a list or `null` instead of an object), `/sky` replies that the forecast came back incomplete instead of guessing.
2. `get_night_hours()` takes the hours where `is_day` is 0, from now until the next sunrise. A missing value never counts as dark. If fewer than 3 dark hours are left (a request at dawn), it moves on to the next night. If the complete data has no dark hour at all, the reply reports the midnight sun.
3. `find_best_window()` finds the longest run of hours with cloud cover of 30% or less and a rain chance under 50%. If there is none, `explain_no_window()` gives the real reason: cloud above 30%, rain during the clear hours, or no cloud forecast.
4. `describe_moon()` names the phase and works out how much of the Moon is lit. `describe_moon_visibility()` reports moonrise and moonset during the dark hours. Both rely on the assumptions above.
5. `assess_sky()` rates the night as the **worse** of two ratings:
   - **Cloud:** an average of 30% or less is Good, 60% or less is Fair, anything higher is Poor.
   - **Rain:** any hour with a 50%+ chance caps the night at Fair; wet hours for at least half the night make it Poor.

   For Good and Fair nights it then adds moonlight advice. It also warns if the forecast visibility drops below 2 km (mist or fog).
6. The reply ends with *"Weather data by Open-Meteo.com (https://open-meteo.com/)"*. Open-Meteo's CC BY 4.0 licence requires a link wherever its data is shown, and OpenWeather is credited for the place search.

Example reply (live, 23 Oct 2026, after the review fixes):

```text
🔭 Stargazing forecast for London, England, GB, night of Fri 23 Oct
🌇 Sunset 17:50 · 🌅 Sunrise 07:39 (local time)
☁️ Cloud after dark: 45% on average (lowest 0% at 23:00)
✨ Best viewing window: 22:00-03:00 (cloud 30% or less)
🌧️ Highest chance of rain: 6%
🌔 Moon: Waxing Gibbous, 91% lit, sets 05:26
🔭 Verdict: ⚠️ Fair - partly cloudy with clear spells; the bright Moon favours the Moon and planets over faint galaxies
Weather data by Open-Meteo.com (https://open-meteo.com/) · place search © OpenWeather
```

The same evening, Edinburgh had a clear spell but up to an 84% chance of rain. The old rules ignored rain; the verdict now reads *"❌ Poor - mostly cloudy, rain likely at times (up to 84% chance)"*.

--- 

##  Evaluation – Web Architecture, MVC Design & Security 

In this section, evaluate how web technologies, architecture, and design patterns have been applied in your **AstroBot**. Your responses must relate directly to your implementation and include reflection on your design decisions.

---

###  Web Architecture – Client–Server Model

Explain how the client–server model applies to your AstroBot:

- Identify the **client** 
- Identify the **server(s)** 
- Describe how data flows between:
  - User, AstroBot and APIs

Include a **simple block diagram** to illustrate this interaction.

**Clients**

- **AstroBot itself (`astro_bot.py`) is an HTTP client.** It never listens on a port. Every exchange is a request that AstroBot starts, and a server answers it.
- Club members' **Webex apps** (phone or desktop) are also clients of the same Webex cloud. Members never talk to AstroBot directly: both sides meet in the shared room.

**Servers**

| Server | Role | Called from |
|--------|------|-------------|
| Webex cloud (`webexapis.com`) | Stores rooms and messages; delivers replies to members | `get_rooms()`, `get_latest_message()`, `send_message()` |
| OpenWeather (`api.openweathermap.org`) | Geocoding (city to coordinates and back) and current weather | `get_city_coordinates()`, `reverse_geocode()`, `get_current_weather()` |
| Open Notify (`api.open-notify.org`), with `api.wheretheiss.at` as backup | Live ISS position | `get_iss_location()`, `get_iss_backup_position()` |
| Open-Meteo (`api.open-meteo.com`) | Hourly cloud forecast, sun and Moon times for `/sky` | `get_sky_forecast()` |

**Data flow for one command, e.g. `/weather London,GB`**

1. A member types the command. Their Webex app sends it to the Webex cloud, which stores it in the room.
2. AstroBot's polling loop in `main()` sends `GET /v1/messages?roomId=…&max=1` every 5 seconds and receives the newest message as JSON.
3. The controller sees a new message ID that starts with `/` and splits it into the command `/weather` and the argument `London,GB`. It validates the argument, then calls `get_weather()`.
4. `get_weather()` calls the OpenWeather Geocoding API (JSON array of matches, giving latitude and longitude), then the Current Weather API (JSON object).
5. `format_weather_report()` builds the reply text, and `send_message()` sends it with `POST /v1/messages`. The Webex cloud stores it and pushes it to every member's app.

```mermaid
flowchart LR
    U["Club member<br/>(Webex app)"] -- "1. sends /weather London,GB" --> W[("Webex cloud<br/>webexapis.com")]
    B["AstroBot<br/>astro_bot.py on the club server"] -- "2. GET /v1/messages (every 5 s)" --> W
    B -- "4. GET /geo/1.0/direct, then /data/2.5/weather" --> OW["OpenWeather<br/>Geocoding + Weather"]
    B -- "GET /iss-now.json (/iss)" --> ON["Open Notify ISS<br/>(backup: wheretheiss.at)"]
    B -- "GET /v1/forecast (/sky)" --> OM["Open-Meteo"]
    B -- "5. POST /v1/messages (reply)" --> W
    W -- "reply delivered" --> U
```

*Every arrow from AstroBot is a request that AstroBot starts. Each server sends back a JSON response along the same connection. Every connection uses HTTPS except Open Notify, which only offers HTTP.*

**Design decision: polling instead of webhooks.** Webex could instead push each new message to AstroBot (a webhook). That would make AstroBot a *server*, needing a public HTTPS address and a hole in the club's firewall. Polling keeps AstroBot a pure client that can run behind the club's Wi-Fi with no inbound connections. The cost is a reply delay of up to 5 seconds and 12 requests a minute, well inside Webex's limit of roughly 300 requests a minute.

####  Security Considerations:
- Consider but not limiting to secure handling of API keys and tokens, API rate limiting, and Input validation (e.g., handling user commands safely), include examples from code where necessary to illustrate.

**1. API keys and tokens**

- **Nothing secret is in the source code or Git history.** `.gitignore`, which excludes `.env` and `.venv/`, was committed (`3f63890`) straight after the provided starter files (`22cc4d1`), before any other project files and before any key or `.env` file existed. The committed `.env.example` documents the variable names with empty values. A scan of the full history before the first push found neither the real token nor the API key.
- **Keys are loaded at run time.** `main()` calls `load_dotenv()`, and `get_api_key()` offers the saved value. If the user types a key instead, `getpass` hides it, so it never appears on screen or in terminal recordings for the video:

  ```python
  key = getpass(f"Enter your {prompt}: ").strip()
  ```

- **Keys are never written to logs.** Exception messages from `requests` include the full URL, and the OpenWeather URL contains `appid=<key>`. Every handler therefore prints only the exception's type:

  ```python
  except requests.RequestException as error:
      print("API request failed:", type(error).__name__)
  ```

  The unit test `test_network_errors_do_not_stop_the_bot_or_leak_the_key` passes a fake key inside an error message and checks it never reaches the console. A deliberately broken version of the bot that printed the full error failed this test. During the live Webex test, neither the token nor the key appeared in the bot's log.
- **Traffic is encrypted.** Webex, OpenWeather (although its docs show `http://`), Open-Meteo and the backup ISS API are all called over HTTPS. Open Notify only offers HTTP, but no credential is ever sent to it.
- **The token has limits.** A personal access token acts as the user and expires after 12 hours. When it expires, `get_latest_message()` stops the bot with a clear message instead of failing silently. A dedicated bot account would follow the principle of least privilege better, but in group spaces bots can only read messages that @mention them (see the Webex findings above).

**2. Rate limiting and timeouts**

- Polling every `POLL_INTERVAL = 5` seconds gives 12 requests a minute to Webex. On HTTP 429 the bot waits for the period in the `Retry-After` header before polling again.
- The ISS, weather and forecast APIs are called **only when a member asks**. Each command makes at most four calls, far below OpenWeather's free limit of 60 a minute, and Open Notify's "one request every 5 seconds" guidance is respected.
- Every request has a timeout (`REQUEST_TIMEOUT = 10` seconds, and `ISS_TIMEOUT = 5` for Open Notify), so a slow server cannot freeze the bot. A failed call is not retried in a loop. The only extra request is a single call to the backup ISS API.

**3. Input validation and safe command handling**

- Only messages starting with `/` are treated as commands, and the command word must match exactly (`/weatherParis` is rejected as unknown).
- City names go through `validate_city()`: at most 85 characters of letters, spaces, commas, full stops, apostrophes and hyphens (`CITY_PATTERN`). In the live test, `/weather <script>alert(1)</script>` was rejected with a polite message. The city is passed to `requests` as a `params=` value, which is URL-encoded, so it cannot change the request URL.
- The bot remembers the ID of every reply it posts and never processes its own messages, so it cannot get stuck answering itself. This was a real bug in the starter design, found in testing; see the commit `fix(webex): stop the bot from answering its own replies`.
- **Remaining risk:** any member of the room can send `/quit`. Limiting it to the person running the bot is listed as a future improvement.

---

###  RESTful API Usage in Your Application
Explain how REST APIs are used in your AstroBot: 

- Describe how HTTP methods (GET, POST) are used  
- Explain how your bot interacts with APIs (Webex, Weather, ISS, Geocoding)  
- Describe how JSON responses are received and processed  

Note: Relate your explanation directly to your code for higher grade. 

AstroBot uses REST APIs throughout. Each piece of data is a **resource** with its own URL (`/rooms`, `/messages`, `/weather`, `/iss-now.json`, `/forecast`), and the **HTTP method** says what to do with it. The requests are **stateless**: every request carries its own credentials (the `Authorization: Bearer …` header for Webex, the `appid` parameter for OpenWeather), so no server keeps a session for the bot.

| Function in `astro_bot.py` | Method and endpoint | Main parameters and body | Response used |
|---|---|---|---|
| `get_rooms()` | `GET webexapis.com/v1/rooms` | `sortBy=lastactivity`, `max=100` | `items[]` with `title`, `type` and `id` |
| `get_latest_message()` | `GET webexapis.com/v1/messages` | `roomId`, `max=1` | `items[0].id`, `items[0].text` |
| `send_message()` | **`POST`** `webexapis.com/v1/messages` | JSON body `{"roomId", "text", "markdown"}` | `id` of the new message, used to skip the bot's own replies |
| `get_city_coordinates()` | `GET …/geo/1.0/direct` | `q`, `limit=1`, `appid` | `[0].lat`, `[0].lon`, `name`, `state`, `country` |
| `reverse_geocode()` | `GET …/geo/1.0/reverse` | `lat`, `lon`, `limit=1`, `appid` | `[0]`, or `[]` over the ocean |
| `get_current_weather()` | `GET …/data/2.5/weather` | `lat`, `lon`, `units=metric`, `appid` | `weather[0]`, `main`, `clouds`, `wind`, `visibility`, `dt`, `timezone` and `sys` |
| `get_iss_location()` / `get_iss_backup_position()` | `GET api.open-notify.org/iss-now.json` / `GET api.wheretheiss.at/v1/satellites/25544` | none | `iss_position.latitude/longitude`, `timestamp` |
| `get_sky_forecast()` | `GET api.open-meteo.com/v1/forecast` | `latitude`, `longitude`, `hourly`, `daily`, `timezone=auto` | `hourly.*[]`, `daily.*[]`, `utc_offset_seconds` |

**GET and POST.** `GET` is used for everything AstroBot *reads*. These requests are safe (they change nothing on the server), so the bot can repeat them every 5 seconds. `POST` is used only to *create* a new message in the room. It sends a JSON body, which is why `send_message()` adds the `Content-Type: application/json` header and calls `json.dumps()`:

```python
headers = {"Authorization": token, "Content-Type": "application/json"}
data = {"roomId": room_id, "text": ..., "markdown": ...}
response = requests.post(url, headers=headers, data=json.dumps(data), timeout=REQUEST_TIMEOUT)
```

**How JSON is received and processed.** `response.json()` turns the body into Python dictionaries and lists. The bot then:

- picks out what it needs, e.g. `response.json().get("items", [])` for Webex, or `data[0] if data else None` for geocoding results, which arrive as arrays;
- converts types where needed: Open Notify returns `"latitude": "10.0567"` as a **string**, so it is converted with `float()`, while the backup API already returns numbers;
- converts epoch timestamps to readable times (`epoch_to_utc()` for the ISS, `format_local_time()` for city times) and the Moon's `moon_phase` fraction to a name and percentage lit (`describe_moon()`);
- passes the result to the formatting functions. These build the reply text, and `send_message()` encodes it back into JSON for the `POST`.

#### Security Considerations: (2 marks)
- Check response status codes, Handling invalid or unexpected API responses, Avoiding excessive API calls

- **Status codes are always checked before data is used.** Every function compares `response.status_code` with `200` first. Specific codes get specific handling:
  - Webex `429`: wait for the `Retry-After` period;
  - Webex `401`: the token has expired, so stop with instructions;
  - OpenWeather `401`: logged as e.g. `Geocoding API error: 401` (OpenWeather really did return 401 during development, while the new key was still activating);
  - any other non-200: a friendly reply such as *"⚠️ Sorry, the weather data could not be retrieved right now"*, never a crash.
- **Invalid or unexpected responses are handled safely.**
  - Fields are read with `.get()` and defaults, and `format_value()` / `format_place()` show **N/A** or **Unknown** for anything missing.
  - Malformed ISS coordinates are caught (`KeyError`, `TypeError`, `ValueError`).
  - As a last line of defence, the controller catches network errors and unexpected data around each command, including fields of the wrong type (`AttributeError`, `KeyError`, `TypeError`, `ValueError`), so the bot always replies and keeps running.
  - If Open Notify times out (it did, several times in testing), `/iss` automatically uses the backup provider.
  - The Open-Meteo forecast is checked before use (`find_forecast_problem()`). If it isn't a JSON object, covers fewer than 24 upcoming hours, or lacks `is_day` values, `/sky` says the forecast came back incomplete instead of guessing. A missing `is_day` value is never treated as darkness, so incomplete data can't be mistaken for the midnight sun.
- **Excessive API calls are avoided.**
  - One `GET` every 5 seconds, using `max=1` so only one message is downloaded.
  - External APIs are called only when a command needs them, and never in retry loops. `/sky` makes two calls (geocoding and forecast), far inside Open-Meteo's free limit of 10,000 a day.
  - Timeouts on every request.
  - Commands with invalid input are rejected *before* any API call is made.

---

###  MVC Design Pattern in AstroBot

Explain how the **Model–View–Controller (MVC)** pattern applies to your solution:
Provide a short example based on your implementation

| Component   | Description and Example (Relate to your Bot) |
|------------|----------------------------------|
| **Model**  | **Data and rules, with no knowledge of chat formatting.** The API functions fetch and return raw data: `get_city_coordinates()`, `get_current_weather()`, `reverse_geocode()`, `get_iss_backup_position()`, `get_latest_message()`, and the Open-Meteo call in `get_sky_forecast()`. The domain rules check data and turn it into decisions: `find_forecast_problem()`, `assess_stargazing()`, `is_daytime()`, `get_night_hours()`, `find_best_window()`, `explain_no_window()`, `describe_moon()` and `assess_sky()`. *Example:* `get_current_weather(51.5, -0.13, key)` returns the OpenWeather dictionary, and `assess_stargazing()` turns it into `"Poor - 87% cloud cover"`. |
| **View**   | **Presentation only.** The FORMATTING FUNCTIONS section turns model data into readable chat replies: `format_weather_report()`, `format_iss_report()`, `format_sky_report()`, `format_help()`, plus helpers such as `format_value()` (N/A for missing data), `format_coordinates()` and `format_local_time()`. `send_message()` hands the reply to Webex as markdown with a plain-text fallback, and the Webex app does the final rendering on members' screens. *Example:* `format_iss_report()` turns `lat=-46.8871, lon=-60.0843` into `📍 Coordinates: 46.8871° S, 60.0843° W` and adds a map link. |
| **Controller** | **Decides what happens.** `main()` loads the configuration, lets the operator pick a room, polls Webex, ignores old, duplicate and non-command messages, parses the command word and argument, validates input (`validate_city()`), and calls the right model and view functions. It also handles errors and remembers the bot's own reply IDs. *Example:* for `/sky Edinburgh`, `main()` validates `Edinburgh`, calls `get_sky_forecast()` and posts the result with `send_message()`. |

**Reflection on the design.** Separating the layers had practical benefits:

- The formatting could be redesigned in step 9 (markdown, emoji, local times) without touching any API code.
- The data rules can be unit-tested with fixed input, e.g. `test_stargazing_rules` and `SkyExtensionTests`, without a network.
- The `/sky` extension slotted into all three layers: it reuses the model's geocoding function, adds its own view function, and needs only one new branch in the controller.

Because the brief requires a single starter script, MVC is applied as **separate groups of functions** rather than separate classes or files. There is one compromise: `get_weather()`, `get_iss_location()` and `get_sky_forecast()` *coordinate* a command by fetching data and then calling the matching formatter. This kept the starter's function names and return values unchanged. A larger version would move that coordination into the controller and split the layers into modules (`models.py`, `views.py`, `bot.py`).

---

### 📝 Reflection and Evaluation

Reflect on your AstroBot (400 words):

- How effective is your bot in meeting the Astronomy Club’s needs?  
- What design decisions worked well?  
- What challenges did you face when integrating APIs?  
- What security risks did you identify and how were they handled?  
- How could your solution be improved in the future?  

 My AstroBot provides the Astronomy Club with Weather updates, the current position of the International Space Station, as well as the star watching forecast. Information is not gathered from several different sites; instead, members can simply use basic commands to get updates. My responsibilities include creating accounts and setting up APIs and repositories on GitHub, as well as checking the responses within Webex.

In general, one of the most efficient aspects of the software design was the division of the program into several functions. Functions are created to send requests via an API, process the received command, format the output message and perform other tasks separately. This will allow to check separate segments of code for errors. The `/sky` extension has practical usage because it suggests viewing windows using cloud cover and rain probability, as well as the information regarding the Moon.

As for the main challenges associated with API integration in the program, the first one was the necessity to wait for activation of OpenWeather API key because, in case of an authentication error, there might be a problem with the code. There were timeouts with Open Notify API. Another solution, where an alternative ISS provider was used, increased the system's reliability if the main provider went down. All those mistakes clearly explained the need for timeouts, correct error messages, and proper reaction to request failure in a program.

Security is also an important aspect. The secret API key and Webex token are kept in the .env file which is not stored in Git. This helps to avoid the publication of access credentials in the repository. The program controls the names of the cities, checks HTTP status code and reacts on failed requests. Polling every five seconds makes it possible to limit frequent checking of Webex, but rate-limited answers get additional handling.

Testing revealed issues that would remain undetected by successful API calls. At the code review stage, the star gazing prediction could report the weather as good even in case of a very likely rain. Lacking information about weather could return a false answer too. Such misbehavior got fixed and regression tests implemented. Next, I sent /weather, /iss and /sky to Webex manually and checked if the responses were clear enough.
Even though, there are shortcomings with the bot. For instance, reading only the last message implies that commands given close to each other will not be executed properly. The personal Webex token will get invalid after some time and the room members have the freedom of stopping the bot anytime. The Moon calculation is done based on certain assumptions about undocumented parameters. Similarly, the time for forecasting may change based on daylight-saving effects.

Some of the modifications that should be done for future work will include reading all the messages that were not seen before, limitation on administration commands as well as use of an astronomy service that is well documented. In conclusion, the whole process shows that Python programming language is capable of joining multiple web services together in order to form one application.


---


### Notes

- Use official documentation for accuracy (e.g. developer.webex.com, locationiq.com or Mapbox, open-notify.org or other ISS API).
- Be prepared to explain your findings to your instructor or demo how you retrieved them using tools like Postman, Curl, or Python scripts.

---

###  

---

## Running AstroBot

**Requirements:** Python 3.15 (pinned in `.python-version`), a Webex account with a personal access token, and an OpenWeather API key. Open-Meteo and the ISS APIs need no key.

1. **Create the virtual environment and install the dependencies**
   ```bash
   uv venv .venv                        # or: python -m venv .venv
   uv pip install -r requirements.txt   # or: .venv\Scripts\pip install -r requirements.txt
   ```
2. **Add your keys:** copy `.env.example` to `.env` and fill in `WEBEX_ACCESS_TOKEN` and `OPENWEATHER_API_KEY`. `.env` is git-ignored, so never commit it.
3. **Start the bot**
   ```bash
   .venv\Scripts\python astro_bot.py    # Windows   (macOS/Linux: .venv/bin/python astro_bot.py)
   ```
   Answer `y` to use the keys saved in `.env` (or `n` to type a different one; it stays hidden). Then choose the room by its number or part of its name. Stop the bot with `/quit` in the room or **Ctrl+C**.
4. **Run the tests** (offline: no keys or network needed)
   ```bash
   .venv\Scripts\python -m unittest discover -s tests -v
   ```

| Command | What it does | APIs used |
|---------|--------------|-----------|
| `/weather <city>` | Current weather in the city's local time, plus a Good/Fair/Poor stargazing verdict | OpenWeather Geocoding + Current Weather |
| `/iss` | Live ISS position (UTC time, coordinates, place below it, weather there, map link) | Open Notify (backup: wheretheiss.at), OpenWeather reverse geocoding + weather |
| `/sky <city>` | **Extension:** the night's cloud and rain forecast, best viewing window, Moon phase, moonrise and moonset, and a Good/Fair/Poor verdict | OpenWeather Geocoding + Open-Meteo |
| `/help` | Lists the commands | none |
| `/quit` | Stops the bot | none |

Tip: add a country code if a city name is ambiguous, e.g. `/weather London,GB` or `/sky Paris,FR`.

---

## Test evidence

Each development step was tested before it was committed. The commit messages record what was tested. All the tests below were **actually run** on 23 Oct 2026 (Windows 11, Python 3.15.1).

**Automated:** `python -m unittest discover -s tests -v` runs **46 offline tests**, and all pass. They cover:

- credential prompts;
- Webex requests and status codes (401, 429 with `Retry-After`);
- the JSON body sent to Webex;
- weather, ISS and `/sky` replies, including missing and malformed data;
- the ISS backup API;
- the stargazing and Moon rules;
- city validation;
- the providers' credit lines;
- the main loop (duplicates, the bot's own replies, network errors, no key in logs).

The suite was checked by deliberately breaking the bot. Each of these makes the matching tests fail:

- removing the own-reply fix;
- logging full exception text;
- removing a provider credit;
- reading the clock before checking the forecast's type;
- dropping `AttributeError` from the controller's safety net.

**Regression tests from the code reviews** (`SkyReviewRegressionTests`, 12 tests). The 9 that target the reported bugs did not pass against the code before each fix, and all 12 pass now. The other 3 guard behaviour that was already right: a dry, clear night stays Good; cloud is still blamed when it really is cloudy; a complete all-daylight forecast still reports the midnight sun.

| Review finding | What the tests check |
|---|---|
| 1. A Good verdict despite a 90% chance of rain | High rain is never rated Good; occasional rain caps the night at Fair; a dry, clear night stays Good |
| 2. The no-window message always blamed cloud | The reason given is cloud, rain or missing cloud data, as appropriate (including a count of hours with no data) |
| 3. Missing `is_day` treated as darkness, false midnight sun | Missing values are not dark. Empty data, no `is_day`, or only 6 hours of data all give "came back incomplete". Only a complete all-daylight forecast gives the midnight sun |
| Follow-up review: a list or `null` forecast crashed `local_now()` and could stop the bot | With the real clock (no mocking), `[]` and `null` give "came back incomplete". In the full bot loop (`MainLoopTests`), a list and an object with a wrongly typed `hourly` field both get a reply, and the bot carries on to `/quit` |
| Found while checking the docs | The rain chance is read for the hour it covers (`precipitation_probability` describes the preceding hour) |

**Live API checks:**

- **Webex:** `GET /rooms` found "Astro Club Room".
- **OpenWeather:**
  - `/weather` for London, Tokyo, Sydney and Reykjavik, plus an unknown city;
  - reverse geocoding over the mid-Atlantic returned `[]`;
  - weather over the ocean has `name: ""` and no country.
- **Open Notify:** worked, but timed out intermittently, which led to adding the backup API.
- **Backup ISS API:** used live, both when Open Notify was failed on purpose (in a test) and after a real timeout.
- **Open-Meteo `/sky`:** London, Sydney (asked at dawn), Tromsø, Honolulu and Atacama.
- **`/sky` after the review fixes:**
  - London: Fair with clear spells.
  - Edinburgh: Poor, rain likely at times (up to 84%).
  - Real Open-Meteo data run through the bot's own functions for two polar places. For the **South Pole**, all 39 upcoming hours were daylight and the data passed the completeness check, so `/sky` would correctly report the midnight sun. **Longyearbyen** produced a 14-hour night with a rain-aware verdict.

**Live end-to-end test (brief Step 11)**, rerun on 23 Oct 2026 against the current code (`astro_bot.py` as of commit `9b07799`, which includes all the review fixes) in the Webex space "Astro Club Room". A test script started the real bot, posted the messages through the Webex API as the room owner, and read the room back afterwards. To test duplicate handling it:

- posted a `/help` *before* the bot started, which the bot must treat as old and ignore;
- after each reply, kept watching for 16 more seconds (three more 5-second polls) to catch any duplicate reply;
- sent `/help` a second time near the end, which is a new message and should get exactly one new reply.

| Message sent | Bot's reply | Result |
|---|---|---|
| `/help` *(posted before the bot started)* | none: an old message | ✅ ignored |
| `Hello again, AstroBot retest …` | none: not a command | ✅ ignored |
| `/help` | Command list (6 lines) | ✅ |
| `/weather London,GB` | 10-line report ending "Stargazing: Poor - 72% cloud cover" and "Weather data © OpenWeather" | ✅ |
| `/weather Qwzxv` | "❌ I couldn't find a city called 'Qwzxv'…" | ✅ |
| `/weather` | "ℹ️ Usage: /weather <city>…" | ✅ |
| `/weather <script>alert(1)</script>` | "⚠️ Please send a plain city name…" | ✅ rejected before any API call |
| `/iss` | Position 51.3488° N, 141.5959° E (over the ocean), the weather below, and "Weather data © OpenWeather" | ✅ |
| `/sky Edinburgh` | Night forecast: best window 00:00–03:00, rain chance up to 84%, Moon 91% lit and setting at 05:43. Verdict: "❌ Poor - mostly cloudy, rain likely at times (up to 84% chance)". Ends with the Open-Meteo credit and link | ✅ |
| `/sky` | "ℹ️ Usage: /sky <city>…" | ✅ |
| `/sky 12345` | "⚠️ Please send a plain city name…" | ✅ |
| `/stars` | "❓ Unknown command…" | ✅ |
| `/help` *(again)* | Command list | ✅ answered once, as a new message |
| `/quit` | "🔭 AstroBot is shutting down. Clear skies!" and the bot exited (code 0) | ✅ |

Every command got **exactly one** reply. The old message, the chat message and the bot's own replies got none. The bot logged each of the 13 messages it received exactly once, and replies arrived 4–7 seconds after each command. The HTML that Webex stored has the expected number of line breaks for every reply (for example, 10 lines for `/weather`, including the credit line), plus `<strong>` and `<code>` formatting. The bot's console log contained neither the token nor the API key.

An earlier run, on the code from before the review fixes (commit `12b7113`), also passed. In that run Open Notify timed out during `/iss`, and the backup ISS API answered automatically.

A later follow-up fix checks the forecast's type before reading it and adds `AttributeError` to the controller's safety net. It only changes how *malformed* API responses are handled, which can't be triggered from Webex, so it is covered by the offline tests above rather than by this run.

**Not yet tested:**

- A person looking at the replies in the Webex app on desktop and mobile. (Only the stored HTML has been checked so far.)
- Commands sent by a second member account, and commands typed by hand rather than posted through the API.
- A real expired token (401) and real Webex rate limiting (429). Both are covered only by mocked tests.
- Running for many hours, and running on the club's own server rather than the development PC.

---

## Known limitations and future improvements

- **Only the newest message is read.** With `max=1`, if two messages arrive within one 5-second poll (or while the bot is replying), the earlier one is skipped. Reading the last few messages and handling every unseen one in order would fix this.
- **Anyone in the room can send `/quit`.** It could be limited to the operator by comparing the message's `personId` with `GET /people/me`.
- **Personal tokens expire after 12 hours**, so the bot needs restarting. A Webex bot account (with @mentions) or an OAuth integration would suit long-term use.
- **Polling adds up to 5 seconds of delay.** Webhooks would be instant but need a public HTTPS endpoint on the club's server.
- **The `/sky` verdict uses simple cloud, rain and Moon thresholds.** Astronomical twilight, light pollution or seeing conditions (e.g. from the Astronomy API) would make it more accurate.
- **The Moon data rests on assumptions.** Open-Meteo does not document `moon_phase`, `moonrise` or `moonset` (see *Moon fields* above). If its definitions differ from what the data suggests, the phase, "% lit" and moonrise/moonset lines would be wrong. A documented astronomy API would remove this risk.
- **Daylight-saving changes.** Open-Meteo applies one fixed UTC offset to the whole response. `/sky` times just after a clock change (such as 25 Oct 2026 in the UK) can therefore be an hour off. Requesting `timeformat=unixtime` and converting with the returned time zone would fix this.
