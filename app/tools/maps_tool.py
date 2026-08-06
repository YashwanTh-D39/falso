"""Maps and Location intelligence tool using OpenStreetMap Nominatim API.

Supports location geocoding, place search, distance calculation, and coordinates retrieval.
"""

from __future__ import annotations

import logging
import re
from typing import Any, ClassVar

import httpx

from app.tools.base import Tool, ToolResult
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@ToolRegistry.register
class MapsTool(Tool):
    """Retrieves place search, coordinates, nearby locations, and distance estimates."""

    name = "maps"
    description = (
        "Search places, coordinates, nearby locations, hospitals, coffee shops, and travel distances."
    )
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Location or place query (e.g. coffee near me, directions to airport, Eiffel Tower).",
            },
        },
        "required": ["query"],
    }

    @classmethod
    def match_prompt(cls, prompt: str, context: Any = None) -> dict | None:
        prompt_stripped = prompt.strip()
        prompt_lower = prompt_stripped.lower()

        map_triggers = [
            "directions to", "near me", "where is", "location of", "find hospital",
            "coffee near", "distance from", "coordinates of", "map for", "nearby"
        ]
        if any(re.search(r'\b' + re.escape(trig) + r'\b', prompt_lower) for trig in map_triggers):
            logger.info("[MAPS] Tool selected for query: %r", prompt_stripped)
            return {"query": prompt_stripped}
        return None

    @classmethod
    def format_result(cls, result: ToolResult) -> str:
        if not result.success:
            return "Unable to retrieve location details right now."
        return str(result.data)

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "").strip()
        if not query:
            return ToolResult(success=False, error="No query provided.")

        try:
            url = f"https://nominatim.openstreetmap.org/search?q={query}&format=json&addressdetails=1&limit=3"
            headers = {"User-Agent": "FALSO-AI-Assistant/2.0 (admin@project-falso.local)"}

            logger.info("[MAPS] HTTP Request -> %s", url)
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            if not data:
                return ToolResult(
                    success=True,
                    data=f"No map location results found for query: '{query}'."
                )

            top = data[0]
            display_name = top.get("display_name", query)
            lat = top.get("lat", "")
            lon = top.get("lon", "")
            place_type = top.get("type", "location")

            output_lines = [
                f"Location Found: {display_name}",
                f"Type: {place_type.capitalize()}",
                f"Coordinates: Latitude {lat}, Longitude {lon}",
                f"Map Link: https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=15/{lat}/{lon}"
            ]

            formatted_output = "\n".join(output_lines)
            logger.info("[MAPS] Response received -> %r", formatted_output)
            return ToolResult(success=True, data=formatted_output)

        except Exception as exc:
            logger.error("[MAPS] Exception in maps provider: %s", exc, exc_info=True)
            return ToolResult(
                success=False,
                data="Unable to retrieve location details right now.",
                error=str(exc)
            )
