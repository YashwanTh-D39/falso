import logging
import pytest
from app.tools.weather_tool import WeatherTool
from app.services.user_profile import user_profile_service


@pytest.mark.asyncio
async def test_weather_tool_matching():
    """Verify prompt matching and location extraction for various cities."""
    res1 = WeatherTool.match_prompt("Weather in Visakhapatnam")
    assert res1 is not None
    assert res1.get("location") == "Visakhapatnam"

    res2 = WeatherTool.match_prompt("Weather Hyderabad")
    assert res2 is not None
    assert res2.get("location") == "Hyderabad"

    res3 = WeatherTool.match_prompt("Delhi weather")
    assert res3 is not None
    assert res3.get("location") == "Delhi"

    res4 = WeatherTool.match_prompt("Mumbai temperature")
    assert res4 is not None
    assert res4.get("location") == "Mumbai"


@pytest.mark.asyncio
async def test_weather_tool_execution_visakhapatnam():
    """Verify WeatherTool execution for Visakhapatnam updates user profile and returns weather."""
    tool = WeatherTool()
    res = await tool.execute(location="Visakhapatnam")
    assert res.success is True
    assert "Visakhapatnam" in res.data
    assert user_profile_service.get_profile().get("preferred_city") == "Visakhapatnam"


@pytest.mark.asyncio
async def test_weather_tool_fallback_on_failure(monkeypatch, caplog):
    """Verify fallback message and exception logging when weather provider fails."""
    caplog.set_level(logging.ERROR)

    async def mock_get(*args, **kwargs):
        raise RuntimeError("Simulated network timeout")

    tool = WeatherTool()
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)

    res = await tool.execute(location="InvalidCityName9999")
    assert res.success is False
    assert res.data == "I can't access live weather right now."
    assert "[WEATHER] Exception in weather provider" in caplog.text
