import pytest
from aiohttp.test_utils import TestClient, TestServer

from backend.api import WEATHER, WEATHER_ENABLED, WEATHER_STATS, create_app
from backend.native_weather import payload
from backend.validation import Invalid
from tests.test_security import auth

NOW = 1793556000


def weather():
    return payload(
        {"condition": "sunny", "temperature": 0, "humidity": 0},
        [{"time": NOW + 3600, "temperature": -2, "humidity": 75}],
        [{"time": NOW, "low": -5, "high": 5}],
        "America/New_York",
        NOW,
    )


def test_native_weather_shape_bounds_and_zero():
    result = weather()
    assert result["current"] == {"temp_c": 0, "humidity": 0, "icon": "sunny"}
    assert result["forecast"]["hourly"][0]["hour"] == 1
    assert "humidity" not in result["forecast"]["daily"][0]
    assert result["location"]["timezone_long"] == "America/New_York"


@pytest.mark.parametrize("value", [None, True, float("nan"), float("inf"), 90, "20"])
def test_bad_weather_is_not_fabricated(value):
    with pytest.raises(Invalid):
        payload({"condition": "sunny", "temperature": value, "humidity": 50}, [], [], "UTC", NOW)


@pytest.mark.parametrize("timezone", ["../../etc/passwd", "Invalid/Timezone", None, ""])
def test_weather_timezone_is_known_and_not_path_input(timezone):
    with pytest.raises(Invalid):
        payload({"condition": "sunny", "temperature": 20, "humidity": 50}, [], [], timezone, NOW)


async def test_weather_disabled_auth_query_limits_and_payload(rig):
    app = create_app(rig[0], native_telemetry=True, native_controls=True)
    enabled = [False]
    requests = []

    async def provider():
        requests.append(True)
        return weather()

    app[WEATHER], app[WEATHER_ENABLED] = provider, lambda: enabled[0]
    async with TestClient(TestServer(app)) as client:
        assert (await client.get("/nest/weather/v1")).status == 503
        assert (await client.get("/v1/manage/devices")).status == 401
        assert (await client.get("/nest/entry")).status == 401
        assert (await client.post("/nest/transport/put", json={})).status == 401
        headers = auth(rig[1])
        assert (await client.get("/nest/weather/v1", headers=headers)).status == 503
        entry = await (await client.get("/nest/entry", headers=headers)).json()
        assert "weather_url" not in entry
        enabled[0] = True
        entry = await (await client.get("/nest/entry", headers=headers)).json()
        assert entry["weather_url"].endswith("/nest/weather/v1?query=")
        assert (
            await client.get("/nest/weather/v1?url=https://invalid.example", headers=headers)
        ).status == 400
        assert (
            await client.get("/nest/weather/v1?query=" + "x" * 257, headers=headers)
        ).status == 400
        assert not requests
        expected = weather()
        expected["location"].update(zip="00000", country="US")
        assert (
            await (await client.get("/nest/weather/v1?query=00000,US", headers=headers)).json()
            == expected
        )
        assert len(requests) == 1
        public = await client.get("/nest/weather/v1?query=00000,US")
        assert public.status == 200 and (await public.json()) == expected
        assert app[WEATHER_STATS]["served"] == 2
        await client.get(
            "/nest/weather/v1?query=00000,US", headers={"User-Agent": "HearthReadOnlyCheck/1"}
        )
        assert app[WEATHER_STATS]["host_checks"] == 1
        assert app[WEATHER_STATS]["client_requests"] > 0


@pytest.mark.parametrize(
    "query", ["", "00000", "a,b,c", "../../etc,US", "00000,USA", "00000,\nUS", "x" * 16 + ",US"]
)
def test_weather_query_cannot_redirect_or_erase_country(query):
    from backend.native_weather import query_location

    with pytest.raises(Invalid):
        query_location(query)


def test_weather_query_preserves_native_country_and_postal():
    from backend.native_weather import query_location

    assert query_location("00000,US") == {"zip": "00000", "country": "US"}
    assert query_location("SW1A 1AA,GB") == {"zip": "SW1A 1AA", "country": "GB"}


def test_native_ipv4_token_uses_only_explicit_location():
    from backend.native_weather import query_location, query_shape

    assert query_location("ipv4", {"zip": "SW1A 1AA", "country": "gb"}) == {
        "zip": "SW1A 1AA",
        "country": "GB",
    }
    assert query_shape("ipv4")["native_ipv4_fallback"] is True
    # A normal request must not be replaced by the configured fallback.
    assert query_location("00000,US", {"zip": "SW1A 1AA", "country": "GB"})["country"] == "US"


@pytest.mark.parametrize(
    "fallback",
    [
        None,
        {},
        {"zip": "", "country": "US"},
        {"zip": "00000", "country": ""},
        {"zip": "00000", "country": "USA"},
        {"zip": "../../etc", "country": "US"},
        {"zip": 123, "country": "US"},
        {"zip": "00000", "country": "US", "url": "https://invalid.example"},
    ],
)
def test_ipv4_fallback_requires_complete_bounded_configuration(fallback):
    from backend.native_weather import query_location

    with pytest.raises(Invalid):
        query_location("ipv4", fallback)


async def test_ipv4_weather_no_external_lookup_no_query_poisoning(rig):
    app = create_app(rig[0], native_telemetry=True)
    configured = [False]

    async def provider():
        result = weather()
        if configured[0]:
            result["location"]["fallback"] = {"zip": "00000", "country": "US"}
        return result

    app[WEATHER], app[WEATHER_ENABLED] = provider, lambda: True
    async with TestClient(TestServer(app)) as client:
        # A public request cannot seed a location for subsequent callers.
        assert (await client.get("/nest/weather/v1?query=SW1A%201AA,GB")).status == 200
        assert (await client.get("/nest/weather/v1?query=ipv4")).status == 503
        configured[0] = True
        response = await client.get("/nest/weather/v1?query=ipv4")
        assert response.status == 200
        result = await response.json()
        assert result["location"]["zip"] == "00000"
        assert result["location"]["country"] == "US"
        assert "fallback" not in result["location"]
        assert result["location"]["timezone_long"] == "America/New_York"
        assert app[WEATHER_STATS]["invalid_query"] == 0
        assert app[WEATHER_STATS]["unavailable"] == 1


@pytest.mark.parametrize("query", ["PRIVATE-POSTAL,", "12.3456,-45.6789", "PRIVATE-LOCATION"])
def test_weather_shape_never_retains_location_values(query):
    import json

    from backend.native_weather import query_shape

    shape = query_shape(query)
    text = json.dumps(shape)
    assert query not in text and "PRIVATE" not in text and "12.3456" not in text
    assert shape["length"] <= 257 and len(shape["part_lengths"]) <= 3


async def test_invalid_weather_envelope_diagnostics_do_not_expose_query_or_unknown_names(rig):
    import json

    from aiohttp.test_utils import TestClient, TestServer

    from backend.api import create_app

    app = create_app(rig[0], native_telemetry=True)
    async with TestClient(TestServer(app)) as client:
        response = await client.get(
            "/nest/weather/v1",
            params={"query": "PRIVATE-PLACE,US", "PRIVATE-PARAMETER": "PRIVATE-VALUE"},
        )
        assert response.status == 400
        response = await client.get(
            "/v1/manage/devices", headers={"Authorization": "Bearer " + rig[2]}
        )
        assert response.status == 200
        diagnostics = (await response.json())["weather_diagnostics"]
    assert diagnostics["last_invalid_query"]["unknown_member_count"] == 1
    assert "PRIVATE" not in json.dumps(diagnostics)
