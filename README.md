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

---

##  Geocoding API (4 marks)

| Criteria | Details |
|---------|---------|
| Provider used (Choose one) | **LocationIQ / Mapbox/ OpenWeatherMap other -provide detail** |
| API Base URL | `_______________________________` |
| Endpoint for geocoding | `_______________________________` |
| Endpoint for reverse geocoding | `_______________________________` |
| Authentication method | `_______________________________` |
| Required query parameters | `_______________________________` |
| Sample request with latitude/longitude | `_______________________________` |
| Sample JSON response (formatted example) |  
```

```
|

---


##  Weather API (3 marks)

| Criteria | Details |
|---------|---------|
| API Provider (Choose one) | **OpenWeather, OpenWeatherMap (or other – provide details)** |
| API Base URL | `_______________________________` |
| Endpoint for current weather | `_______________________________` |
| Authentication method | `_______________________________` |
| Required query parameters | `_______________________________` |
| Sample JSON response (formatted example) |  
```

```
|

---

##  Epoch to Human Time Conversion (Python time module) (2 marks)

| Criteria | Details |
|---------|---------|
| Library used | `_______________________________` |
| Function used to convert epoch | `_______________________________` |
| Sample code to convert timestamp |  
```  
```
|
| Output (human-readable time) | `_______________________________` |

---

##  Extended Feature API ( 3 marks)

| Criteria | Details |
|---------|---------|
| API Provider | '_________' |
| API Base URL | `_______________________________` |
| Endpoint | `_______________________________` |
| Authentication method | `_______________________________` |
| Required query parameters | `_______________________________` |
| Sample JSON response (formatted example) |  
```

```
|

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