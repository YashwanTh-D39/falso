"""PyPI and Package Documentation tool.

Retrieves official package versions, descriptions, and release notes from PyPI JSON API.
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
class PyPITool(Tool):
    """Retrieves PyPI package versions, release details, and documentation URLs."""

    name = "pypi"
    description = (
        "Lookup Python package versions, PyPI releases, descriptions, and official documentation URLs."
    )
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "package": {
                "type": "string",
                "description": "Package name (e.g. fastapi, pydantic, httpx, uvicorn, numpy).",
            },
        },
        "required": ["package"],
    }

    @classmethod
    def match_prompt(cls, prompt: str, context: Any = None) -> dict | None:
        prompt_stripped = prompt.strip()
        prompt_lower = prompt_stripped.lower()

        pypi_triggers = [
            "package version", "pypi version", "latest version of", "pypi for", "version of package"
        ]
        if any(re.search(r'\b' + re.escape(trig) + r'\b', prompt_lower) for trig in pypi_triggers):
            match = re.search(r'(?:version of|version for|pypi for|package)\s+([a-zA-Z0-9_\-]+)', prompt_stripped, re.IGNORECASE)
            pkg = match.group(1).strip() if match else "fastapi"
            logger.info("[PYPI] Tool selected for package: %r", pkg)
            return {"package": pkg}
        return None

    @classmethod
    def format_result(cls, result: ToolResult) -> str:
        if not result.success:
            return "Unable to check package version right now."
        return str(result.data)

    async def execute(self, **kwargs: Any) -> ToolResult:
        package = kwargs.get("package", "").strip()
        if not package:
            return ToolResult(success=False, error="No package specified.")

        try:
            url = f"https://pypi.org/pypi/{package}/json"
            logger.info("[PYPI] HTTP Request -> %s", url)

            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url)
                if resp.status_code == 404:
                    return ToolResult(
                        success=True,
                        data=f"Package '{package}' not found on PyPI."
                    )
                resp.raise_for_status()
                data = resp.json()

            info = data.get("info", {})
            version = info.get("version", "Unknown")
            summary = info.get("summary", "")
            project_url = info.get("project_url", f"https://pypi.org/project/{package}/")

            output = (
                f"Package: {package} v{version}\n"
                f"Summary: {summary}\n"
                f"PyPI URL: {project_url}"
            )
            logger.info("[PYPI] Response received -> %r", output)
            return ToolResult(success=True, data=output)

        except Exception as exc:
            logger.error("[PYPI] Exception in PyPI provider: %s", exc, exc_info=True)
            return ToolResult(
                success=False,
                data="Unable to check package version right now.",
                error=str(exc)
            )
