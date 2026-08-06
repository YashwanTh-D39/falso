import logging
import pytest
from app.tools.weather_tool import WeatherTool


@pytest.mark.asyncio
async def test_weather_tool_matching():
    """Verify prompt matching for weather queries."""
    res1 = WeatherTool.match_prompt("What is today's weather?")
    assert res1 is not None
    assert res1.get("location") == "New York"

    res2 = WeatherTool.match_prompt("Weather in Tokyo")
    assert res2 is not None
    assert res2.get("location") == "Tokyo"


@pytest.mark.asyncio
async def test_weather_tool_execution():
    """Verify WeatherTool execution returns temperature and condition."""
    tool = WeatherTool()
    res = await tool.execute(location="New York")
    assert res.success is True
    assert "weather in New York" in res.data or "weather" in res.data.lower()


@pytest.mark.asyncio
async def test_weather_tool_fallback_on_failure(monkeypatch, caplog):
    """Verify fallback message and exception logging when weather provider fails."""
    caplog.set_level(logging.ERROR)
    
    async def mock_get(*args, **kwargs):
        raise RuntimeError("Simulated network timeout")

    tool = WeatherTool()
    # Mock execute exception
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)

    res = await tool.execute(location="InvalidCity")
    assert res.success is False
    assert res.data == "I can't access live weather right now."
    assert "[WEATHER] Exception in weather provider" in caplog.text
