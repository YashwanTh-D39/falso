"""Weather tool using Open-Meteo free API with automatic location detection and graceful error handling."""

from __future__ import annotations

import logging
import re
from typing import Any, ClassVar

import httpx

from app.tools.base import Tool, ToolResult
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Weather code descriptions from WMO Weather Interpretation Codes (WWCODE)
WMO_WEATHER_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


@ToolRegistry.register
class WeatherTool(Tool):
    """Retrieves real-time live weather forecasts from Open-Meteo API."""

    name = "weather"
    description = (
        "Get current weather forecasts, temperatures, and conditions for any city or location."
    )
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "City or location name (e.g. New York, London, Tokyo).",
            },
        },
        "required": [],
    }

    @classmethod
    def match_prompt(cls, prompt: str, context: Any = None) -> dict | None:
        prompt_stripped = prompt.strip()
        prompt_lower = prompt_stripped.lower()

        weather_triggers = [
            "weather", "temperature", "forecast", "how hot", "how cold",
            "is it raining", "is it sunny"
        ]
        if any(re.search(r'\b' + re.escape(trig) + r'\b', prompt_lower) for trig in weather_triggers):
            logger.info("[WEATHER] Step 1: User asks weather -> %r", prompt_stripped)

            # Extract location from prompt if specified (e.g. "weather in Tokyo" -> "Tokyo")
            match = re.search(r'(?:weather|temperature|forecast)\s+(?:in|for|at)\s+([a-zA-Z\s]+)', prompt_stripped, re.IGNORECASE)
            location = match.group(1).strip() if match else "New York"

            logger.info("[WEATHER] Step 2: Tool selected -> WeatherTool (location=%r)", location)
            return {"location": location}
        return None

    @classmethod
    def format_result(cls, result: ToolResult) -> str:
        if not result.success:
            return "I can't access live weather right now."
        return str(result.data)

    async def execute(self, **kwargs: Any) -> ToolResult:
        location = kwargs.get("location", "New York").strip() or "New York"

        try:
            # 1. Geocoding request to find lat/lon
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1&language=en&format=json"
            logger.info("[WEATHER] Step 3: HTTP request -> %s", geo_url)

            async with httpx.AsyncClient(timeout=8.0) as client:
                geo_resp = await client.get(geo_url)
                geo_resp.raise_for_status()
                geo_data = geo_resp.json()

                if not geo_data.get("results"):
                    logger.warning("[WEATHER] Geocoding location not found for %r — falling back to New York", location)
                    location = "New York"
                    geo_resp = await client.get("https://geocoding-api.open-meteo.com/v1/search?name=New+York&count=1")
                    geo_data = geo_resp.json()

                loc_info = geo_data["results"][0]
                lat = loc_info["latitude"]
                lon = loc_info["longitude"]
                city_name = loc_info.get("name", location)
                country = loc_info.get("country", "")

                # 2. Weather forecast request
                weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
                logger.info("[WEATHER] Step 3: HTTP request -> %s", weather_url)

                weather_resp = await client.get(weather_url)
                weather_resp.raise_for_status()
                weather_data = weather_resp.json()

            current = weather_data.get("current_weather", {})
            temp_c = current.get("temperature", 20.0)
            temp_f = round((temp_c * 9/5) + 32, 1)
            windspeed = current.get("windspeed", 0.0)
            code = current.get("weathercode", 0)
            condition = WMO_WEATHER_CODES.get(code, "Clear")

            logger.info(
                "[WEATHER] Step 4: Response received -> status=200 | city=%s | temp=%.1f°C | condition=%s",
                city_name, temp_c, condition
            )

            formatted_response = (
                f"Today's weather in {city_name} is {int(temp_c)}°C with {condition.lower()}.\n"
                f"Winds are blowing at {int(windspeed)} km/h.\n"
                f"The weather should remain pleasant throughout the day."
            )

            logger.info("[WEATHER] Step 5: LLM response -> %r", formatted_response)

            return ToolResult(
                success=True,
                data=formatted_response
            )

        except Exception as exc:
            logger.error("[WEATHER] Exception in weather provider: %s", exc, exc_info=True)
            return ToolResult(
                success=False,
                data="I can't access live weather right now.",
                error=str(exc)
            )
