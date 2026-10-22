"""Offline unit tests for astro_bot.py.

Every HTTP call is replaced with a fake response, so the tests need no API keys or network.
Run from the project folder with:  python -m unittest discover -s tests -v
"""
import contextlib
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import requests  # noqa: E402

import astro_bot as bot  # noqa: E402


class FakeResponse:
    """Just enough of requests.Response for the bot's code."""

    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}

    def json(self):
        return self._payload


def route(responses):
    """Fake requests.get that picks a response (or raises) by a substring of the URL."""
    def fake_get(url, **kwargs):
        for fragment, outcome in responses.items():
            if fragment in url:
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome
        raise AssertionError(f"unexpected request to {url}")
    return fake_get


LONDON = {"name": "London", "state": "England", "country": "GB", "lat": 51.5073, "lon": -0.1276}
CLEAR_NIGHT = {
    "weather": [{"id": 800, "description": "clear sky"}],
    "main": {"temp": 7.3, "feels_like": 5.0, "humidity": 70},
    "clouds": {"all": 5}, "visibility": 10000, "wind": {"speed": 3.1},
    "dt": 1792790000, "timezone": 3600,
    "sys": {"country": "GB", "sunrise": 1792737480, "sunset": 1792773000},
}


class ConfigurationTests(unittest.TestCase):
    def test_saved_key_is_used_when_user_accepts(self):
        with mock.patch("builtins.input", return_value="y"):
            self.assertEqual(bot.get_api_key("OpenWeather API key", "saved"), "saved")

    def test_user_can_type_a_different_key_hidden(self):
        with mock.patch("builtins.input", return_value="n"), \
                mock.patch.object(bot, "getpass", return_value=" typed ") as hidden:
            self.assertEqual(bot.get_api_key("OpenWeather API key", "saved"), "typed")
        hidden.assert_called_once()

    def test_missing_key_prompts_until_one_is_entered(self):
        with mock.patch.object(bot, "getpass", side_effect=["", "  ", "typed"]), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(bot.get_api_key("OpenWeather API key", None), "typed")

    def test_webex_token_gets_single_bearer_prefix(self):
        with mock.patch.dict(os.environ, {"WEBEX_ACCESS_TOKEN": "Bearer abc"}), \
                mock.patch("builtins.input", return_value="y"):
            self.assertEqual(bot.get_webex_token(), "Bearer abc")


class WebexTests(unittest.TestCase):
    def test_get_rooms_sends_authorised_get(self):
        rooms = [{"id": "R1", "title": "Astro Club Room", "type": "group"}]
        with mock.patch.object(bot.requests, "get", return_value=FakeResponse(200, {"items": rooms})) as get:
            self.assertEqual(bot.get_rooms("Bearer T"), rooms)
        url = get.call_args.args[0]
        self.assertEqual(url, "https://webexapis.com/v1/rooms")
        self.assertEqual(get.call_args.kwargs["headers"], {"Authorization": "Bearer T"})

    def test_get_rooms_returns_empty_list_on_error_status(self):
        with mock.patch.object(bot.requests, "get", return_value=FakeResponse(401)):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bot.get_rooms("Bearer bad"), [])

    def test_latest_message_requests_only_newest(self):
        payload = {"items": [{"id": "M1", "text": "/iss"}]}
        with mock.patch.object(bot.requests, "get", return_value=FakeResponse(200, payload)) as get:
            self.assertEqual(bot.get_latest_message("Bearer T", "R1"), ("M1", "/iss"))
        self.assertEqual(get.call_args.kwargs["params"], {"roomId": "R1", "max": 1})

    def test_rate_limit_waits_for_retry_after(self):
        with mock.patch.object(bot.requests, "get", return_value=FakeResponse(429, headers={"Retry-After": "7"})), \
                mock.patch.object(bot.time, "sleep") as sleep, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(bot.get_latest_message("Bearer T", "R1"), (None, None))
        sleep.assert_called_once_with(7)

    def test_expired_token_stops_the_bot(self):
        with mock.patch.object(bot.requests, "get", return_value=FakeResponse(401)):
            with self.assertRaises(SystemExit):
                bot.get_latest_message("Bearer old", "R1")

    def test_send_message_posts_markdown_and_plain_text(self):
        with mock.patch.object(bot.requests, "post", return_value=FakeResponse(200, {"id": "NEW"})) as post:
            self.assertEqual(bot.send_message("Bearer T", "R1", "**Hi**\n`/iss`"), "NEW")
        body = json.loads(post.call_args.kwargs["data"])
        self.assertEqual(body, {"roomId": "R1", "text": "Hi\n/iss", "markdown": "**Hi**  \n`/iss`"})
        self.assertEqual(post.call_args.kwargs["headers"]["Content-Type"], "application/json")

    def test_send_message_survives_network_errors(self):
        with mock.patch.object(bot.requests, "post", side_effect=requests.ConnectionError("down")), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(bot.send_message("Bearer T", "R1", "hi"))


class WeatherTests(unittest.TestCase):
    def test_weather_report_contains_key_readings(self):
        responses = route({"/geo/1.0/direct": FakeResponse(200, [LONDON]),
                           "/data/2.5/weather": FakeResponse(200, CLEAR_NIGHT)})
        with mock.patch.object(bot.requests, "get", side_effect=responses) as get:
            reply = bot.get_weather("London,GB", "KEY")
        self.assertIn("Weather for London, England, GB", reply)
        self.assertIn("Temperature: 7.3°C", reply)
        self.assertIn("Stargazing: Good - 5% cloud cover", reply)
        weather_call = get.call_args_list[-1]
        self.assertEqual(weather_call.kwargs["params"]["units"], "metric")

    def test_unknown_city_gets_helpful_message(self):
        with mock.patch.object(bot.requests, "get", return_value=FakeResponse(200, [])):
            self.assertIn("couldn't find a city called 'Atlantis'", bot.get_weather("Atlantis", "KEY"))

    def test_missing_fields_show_na(self):
        with mock.patch.object(bot.requests, "get", route({"/geo/1.0/direct": FakeResponse(200, [LONDON]),
                                                           "/data/2.5/weather": FakeResponse(200, {"main": {}})})):
            reply = bot.get_weather("London", "KEY")
        self.assertIn("Temperature: N/A", reply)
        self.assertIn("Stargazing: Unknown", reply)

    def test_stargazing_rules(self):
        night = {"dt": 2000, "sys": {"sunrise": 1000, "sunset": 1500}}
        cases = [
            ({"weather": [{"id": 501}], "clouds": {"all": 100}}, "Poor - rain"),
            ({"weather": [{"id": 741}], "clouds": {"all": 0}}, "Poor - mist"),
            ({"weather": [{"id": 804}], "clouds": {"all": 90}}, "Poor - 90%"),
            ({"weather": [{"id": 802}], "clouds": {"all": 40}}, "Fair - 40%"),
            ({"weather": [{"id": 800}], "clouds": {"all": 5}, "visibility": 3000}, "Fair - clear but hazy"),
            ({"weather": [{"id": 800}], "clouds": {"all": 5}}, "Good - 5%"),
        ]
        for weather, expected in cases:
            with self.subTest(expected=expected):
                self.assertIn(expected, bot.assess_stargazing({**weather, **night}))

    def test_daytime_is_flagged(self):
        day = {"weather": [{"id": 800}], "clouds": {"all": 0}, "dt": 1200, "sys": {"sunrise": 1000, "sunset": 1500}}
        self.assertIn("daytime", bot.assess_stargazing(day))


class IssTests(unittest.TestCase):
    ISS = {"message": "success", "timestamp": 1792780126, "iss_position": {"latitude": "10.0567", "longitude": "80.7557"}}

    def test_iss_report_over_ocean(self):
        with mock.patch.object(bot.requests, "get", route({"open-notify": FakeResponse(200, self.ISS),
                                                           "/geo/1.0/reverse": FakeResponse(200, []),
                                                           "/data/2.5/weather": FakeResponse(200, CLEAR_NIGHT)})):
            reply = bot.get_iss_location("KEY")
        self.assertIn("2026-10-23 18:28:46 UTC", reply)
        self.assertIn("10.0567° N, 80.7557° E", reply)
        self.assertIn("Over Ocean / No Nearby City", reply)

    def test_backup_api_used_when_open_notify_times_out(self):
        backup = {"latitude": -3.5, "longitude": -110.4, "timestamp": 1792781908}
        with mock.patch.object(bot.requests, "get", route({"open-notify": requests.ConnectTimeout("slow"),
                                                           "wheretheiss": FakeResponse(200, backup),
                                                           "/geo/1.0/reverse": FakeResponse(200, []),
                                                           "/data/2.5/weather": FakeResponse(200, CLEAR_NIGHT)})), \
                contextlib.redirect_stdout(io.StringIO()):
            reply = bot.get_iss_location("KEY")
        self.assertIn("3.5000° S, 110.4000° W", reply)

    def test_both_iss_apis_down(self):
        with mock.patch.object(bot.requests, "get", route({"open-notify": FakeResponse(503),
                                                           "wheretheiss": FakeResponse(500)})), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertIn("could not be retrieved", bot.get_iss_location("KEY"))

    def test_malformed_iss_data(self):
        with mock.patch.object(bot.requests, "get", return_value=FakeResponse(200, {"iss_position": {"latitude": "N"}})):
            self.assertIn("incomplete data", bot.get_iss_location("KEY"))

    def test_epoch_conversion(self):
        self.assertEqual(bot.epoch_to_utc(1792780126), "2026-10-23 18:28:46 UTC")
        self.assertEqual(bot.epoch_to_utc(None), "Unknown time")


def make_forecast(cloud=lambda hour: 10, always_day=False, rain=lambda hour: 0):
    """Two days of Open-Meteo data for London (local times), dark from 18:00 to 07:59."""
    start = bot.datetime(2026, 10, 23)
    hours = [start + bot.timedelta(hours=n) for n in range(48)]
    return {
        "utc_offset_seconds": 3600,
        "hourly": {
            "time": [hour.strftime("%Y-%m-%dT%H:%M") for hour in hours],
            "is_day": [1 if always_day or 8 <= hour.hour < 18 else 0 for hour in hours],
            "cloud_cover": [cloud(hour) for hour in hours],
            "visibility": [24000 for _ in hours],
            "precipitation_probability": [rain(hour) for hour in hours],
        },
        "daily": {
            "time": ["2026-10-23", "2026-10-24"],
            "sunrise": ["2026-10-23T07:38", "2026-10-24T07:39"],
            "sunset": ["2026-10-23T17:50", "2026-10-24T17:48"],
            "moonrise": ["2026-10-23T16:33", "2026-10-24T16:45"],
            "moonset": ["2026-10-23T04:06", "2026-10-24T05:26"],
            "moon_phase": [0.403, 0.437],
        },
    }


def sky_reply(forecast, now):
    """Run get_sky_forecast() with fake geocoding and Open-Meteo responses at a fixed local time."""
    responses = route({"/geo/1.0/direct": FakeResponse(200, [LONDON]), "open-meteo": FakeResponse(200, forecast)})
    with mock.patch.object(bot.requests, "get", side_effect=responses), \
            mock.patch.object(bot, "local_now", return_value=now), contextlib.redirect_stdout(io.StringIO()):
        return bot.get_sky_forecast("London", "KEY")


class SkyExtensionTests(unittest.TestCase):
    NOON = bot.datetime(2026, 10, 23, 12, 0)

    def test_night_runs_from_dark_until_sunrise(self):
        night = bot.get_night_hours(make_forecast(), now=self.NOON)
        self.assertEqual(night[0]["time"], bot.datetime(2026, 10, 23, 18))
        self.assertEqual(night[-1]["time"], bot.datetime(2026, 10, 24, 7))

    def test_dawn_request_forecasts_the_next_night(self):
        night = bot.get_night_hours(make_forecast(), now=bot.datetime(2026, 10, 23, 6, 30))
        self.assertEqual(night[0]["time"], bot.datetime(2026, 10, 23, 18))

    def test_late_request_starts_at_the_current_hour(self):
        night = bot.get_night_hours(make_forecast(), now=bot.datetime(2026, 10, 23, 23, 20))
        self.assertEqual(night[0]["time"], bot.datetime(2026, 10, 23, 23))

    def test_moon_phases_and_illumination(self):
        for phase, name, lit in [(0.0, "New Moon", 0.0), (0.25, "First Quarter", 0.5),
                                 (0.5, "Full Moon", 1.0), (0.75, "Last Quarter", 0.5), (0.403, "Waxing Gibbous", 0.91)]:
            with self.subTest(phase=phase):
                described_name, _, illumination = bot.describe_moon(phase)
                self.assertEqual(described_name, name)
                self.assertAlmostEqual(illumination, lit, places=2)
        self.assertEqual(bot.describe_moon(None)[0], "Unknown phase")

    def test_best_window_is_longest_clear_run(self):
        cloudy_until_midnight = lambda hour: 80 if hour.hour >= 18 else 10
        night = bot.get_night_hours(make_forecast(cloud=cloudy_until_midnight), now=self.NOON)
        window = bot.find_best_window(night)
        self.assertEqual((window[0]["time"].hour, window[-1]["time"].hour), (0, 7))

    def test_sky_report(self):
        responses = route({"/geo/1.0/direct": FakeResponse(200, [LONDON]),
                           "open-meteo": FakeResponse(200, make_forecast())})
        with mock.patch.object(bot.requests, "get", side_effect=responses) as get, \
                mock.patch.object(bot, "local_now", return_value=self.NOON):
            reply = bot.get_sky_forecast("London", "KEY")
        self.assertIn("night of Fri 23 Oct", reply)
        self.assertIn("Sunset 17:50 · 🌅 Sunrise 07:39", reply)
        self.assertIn("Best viewing window: 18:00-07:39", reply)
        self.assertIn("Waxing Gibbous, 91% lit, sets 05:26", reply)
        self.assertIn("Verdict: ✅ Good - mostly clear", reply)
        params = get.call_args.kwargs["params"]
        self.assertEqual((params["timezone"], params["latitude"]), ("auto", 51.5073))

    def test_open_meteo_error(self):
        responses = route({"/geo/1.0/direct": FakeResponse(200, [LONDON]), "open-meteo": FakeResponse(503)})
        with mock.patch.object(bot.requests, "get", side_effect=responses), contextlib.redirect_stdout(io.StringIO()):
            self.assertIn("could not be retrieved", bot.get_sky_forecast("London", "KEY"))


def make_night(hours=10, cloud=10, rain=0):
    """Dark hours from 18:00 for the /sky rules; cloud and rain may be values or functions of the hour index."""
    start = bot.datetime(2026, 10, 23, 18)
    pick = lambda value, n: value(n) if callable(value) else value
    return [{"time": start + bot.timedelta(hours=n), "cloud": pick(cloud, n), "visibility": 24000,
             "rain": pick(rain, n), "moon_up": False} for n in range(hours)]


class SkyReviewRegressionTests(unittest.TestCase):
    """Regression tests for the issues found in the code review of the /sky extension."""

    def test_high_rain_chance_is_never_rated_good(self):
        verdict = bot.assess_sky(make_night(cloud=10, rain=90), illumination=0.1)
        self.assertTrue(verdict.startswith("❌ Poor"), verdict)
        self.assertIn("rain likely for most of the night (up to 90% chance)", verdict)

    def test_occasional_rain_caps_the_verdict_at_fair(self):
        verdict = bot.assess_sky(make_night(cloud=10, rain=lambda n: 70 if n >= 8 else 0), illumination=0.1)
        self.assertTrue(verdict.startswith("⚠️ Fair"), verdict)
        self.assertIn("rain likely at times (up to 70% chance)", verdict)

    def test_dry_clear_night_is_still_good(self):
        self.assertTrue(bot.assess_sky(make_night(cloud=10, rain=10), illumination=0.1).startswith("✅ Good"))

    def window_line(self, night):
        report = bot.format_sky_report(LONDON, {"daily": {}}, night)
        return next(line for line in report.splitlines() if "Best viewing window" in line)

    def test_no_window_blames_cloud_only_when_it_is_cloudy(self):
        self.assertIn("none - cloud stays above 30% all night", self.window_line(make_night(cloud=80)))

    def test_no_window_because_the_clear_hours_are_rainy(self):
        line = self.window_line(make_night(cloud=10, rain=90))
        self.assertIn("50% or higher chance of rain", line)
        self.assertNotIn("cloud stays above", line)

    def test_no_window_because_cloud_data_is_missing(self):
        line = self.window_line(make_night(cloud=None))
        self.assertIn("no cloud forecast available", line)
        self.assertNotIn("cloud stays above", line)

    def test_no_window_with_some_cloud_data_missing(self):
        line = self.window_line(make_night(cloud=lambda n: None if n < 3 else 80))
        self.assertIn("above 30% in every hour with a forecast (3 hours have no data)", line)
        line = self.window_line(make_night(cloud=lambda n: None if n == 0 else 80))
        self.assertIn("(1 hour has no data)", line)

    def test_missing_is_day_values_are_not_treated_as_dark(self):
        noon = bot.datetime(2026, 10, 23, 12)
        forecast = make_forecast()
        forecast["hourly"]["is_day"] = [None] * 48
        self.assertEqual(bot.get_night_hours(forecast, now=noon), [])
        forecast = make_forecast()
        forecast["hourly"]["is_day"][20] = None  # 20:00 has no day/night value
        night_times = [hour["time"] for hour in bot.get_night_hours(forecast, now=noon)]
        self.assertNotIn(bot.datetime(2026, 10, 23, 20), night_times)

    def test_incomplete_forecast_is_not_reported_as_midnight_sun(self):
        no_is_day = make_forecast(always_day=True)
        del no_is_day["hourly"]["is_day"]
        too_short = make_forecast(always_day=True)
        too_short["hourly"] = {key: values[12:18] for key, values in too_short["hourly"].items()}  # 6 hours left
        cases = {"empty hourly data": {"hourly": {}, "daily": {}}, "no is_day values": no_is_day,
                 "only 6 hours of data": too_short, "not a JSON object": []}
        for label, forecast in cases.items():
            with self.subTest(label):
                reply = sky_reply(forecast, now=bot.datetime(2026, 10, 23, 12))
                self.assertIn("came back incomplete", reply)
                self.assertNotIn("midnight sun", reply)

    def test_rain_chance_is_read_for_the_hour_it_covers(self):
        # Open-Meteo documents precipitation_probability as covering the preceding hour,
        # so the value stamped 19:00 describes the 18:00-19:00 slot
        forecast = make_forecast(rain=lambda hour: 80 if hour == bot.datetime(2026, 10, 23, 19) else 0)
        night = bot.get_night_hours(forecast, now=bot.datetime(2026, 10, 23, 12))
        self.assertEqual([hour["rain"] for hour in night[:2]], [80, 0])

    def test_complete_daylight_forecast_is_midnight_sun(self):
        reply = sky_reply(make_forecast(always_day=True), now=bot.datetime(2026, 10, 23, 12))
        self.assertIn("midnight sun", reply)


class FormattingAndValidationTests(unittest.TestCase):
    def test_format_helpers(self):
        self.assertEqual(bot.format_value(None), "N/A")
        self.assertEqual(bot.format_value(80, "%", decimals=0), "80%")
        self.assertEqual(bot.format_place({}), "Unknown location")
        self.assertEqual(bot.format_local_time(1792780126, 3600, "%H:%M"), "19:28")
        self.assertEqual(bot.format_coordinates(-33.8688, 151.2093), "33.8688° S, 151.2093° E")

    def test_city_validation(self):
        for city in ["London", "London,GB", "St. John's", "São Paulo", "Washington, D.C."]:
            with self.subTest(city=city):
                self.assertIsNone(bot.validate_city(city, "/weather"))
        for city in ["", "<script>", "Paris; rm -rf", "12345", "x" * 86, "Paris\n/quit"]:
            with self.subTest(city=city):
                self.assertIsNotNone(bot.validate_city(city, "/weather"))


class FakeWebexRoom:
    """Simulated Webex room: one scripted user message per poll; bot posts become the newest message."""

    def __init__(self, script, fail_poll=None):
        self.messages = [{"id": "OLD", "text": "/quit", "who": "user"}]  # an old command must not be replayed
        self.script, self.polls, self.fail_poll = list(script), 0, fail_poll

    def get(self, url, **kwargs):
        if url.endswith("/rooms"):
            return FakeResponse(200, {"items": [{"id": "R1", "title": "Astro Club Room", "type": "group"}]})
        self.polls += 1
        if self.polls == self.fail_poll:
            raise requests.ConnectionError("network blip")
        if self.polls > 1 and self.script:
            text = self.script.pop(0)
            if text is not None:
                self.messages.append({"id": f"U{self.polls}", "text": text, "who": "user"})
        if self.polls > 50:
            raise SystemExit("bot never quit")
        latest = self.messages[-1]
        return FakeResponse(200, {"items": [{"id": latest["id"], "text": latest["text"]}]})

    def post(self, url, **kwargs):
        body = json.loads(kwargs["data"])
        self.messages.append({"id": f"B{len(self.messages)}", "text": body["text"], "who": "bot"})
        return FakeResponse(200, {"id": self.messages[-1]["id"]})

    def bot_replies(self):
        return [m["text"] for m in self.messages if m["who"] == "bot"]


def run_bot(room, extra_get=None):
    """Run main() against a fake room; returns the console output."""
    def get(url, **kwargs):
        if "webexapis" in url:
            return room.get(url, **kwargs)
        return extra_get(url, **kwargs)

    answers = iter(["y", "y", "1"])
    output = io.StringIO()
    with mock.patch.object(bot, "load_dotenv"), \
            mock.patch.dict(os.environ, {"WEBEX_ACCESS_TOKEN": "T", "OPENWEATHER_API_KEY": "SECRETKEY"}), \
            mock.patch.object(bot.requests, "get", get), mock.patch.object(bot.requests, "post", room.post), \
            mock.patch.object(bot.time, "sleep"), mock.patch("builtins.input", lambda prompt="": next(answers)), \
            contextlib.redirect_stdout(output):
        bot.main()
    return output.getvalue()


class MainLoopTests(unittest.TestCase):
    def test_commands_are_answered_once_and_chat_is_ignored(self):
        room = FakeWebexRoom(["hello", "/help", None, None, "/WEATHER", "/sky", "/marsrover", "/quit"])
        console = run_bot(room)
        replies = room.bot_replies()
        self.assertEqual(len(replies), 5, replies)  # help, 2x usage, unknown, shutdown - nothing twice
        self.assertTrue(replies[0].startswith("🔭 AstroBot commands"))
        self.assertIn("Usage: /weather <city>", replies[1])
        self.assertIn("Usage: /sky <city>", replies[2])
        self.assertIn("Unknown command", replies[3])
        self.assertIn("shutting down", replies[4])
        self.assertNotIn("Received: 🔭", console)  # the bot never reads back its own replies

    def test_own_reply_that_looks_like_a_command_is_not_processed(self):
        # The starter's help text began with "/weather"; replies are posted with the user's token,
        # so without the reply-ID check the bot would treat its own reply as a new command
        room = FakeWebexRoom(["/help", None, None, "/quit"])
        with mock.patch.object(bot, "format_help", return_value="/weather <city>\n/iss\n/help\n/quit"):
            run_bot(room)
        self.assertEqual(room.bot_replies(), ["/weather <city>\n/iss\n/help\n/quit", "🔭 AstroBot is shutting down. Clear skies!"])

    def test_network_errors_do_not_stop_the_bot_or_leak_the_key(self):
        def weather_down(url, **kwargs):
            raise requests.ConnectionError(f"Max retries exceeded with url: /geo/1.0/direct?q=Paris&appid=SECRETKEY")

        room = FakeWebexRoom(["/weather Paris", "/quit"], fail_poll=2)
        console = run_bot(room, extra_get=weather_down)
        self.assertIn("Could not reach Webex: ConnectionError", console)
        self.assertIn("couldn't reach one of the data services", room.bot_replies()[0])
        self.assertNotIn("SECRETKEY", console)


if __name__ == "__main__":
    unittest.main()
