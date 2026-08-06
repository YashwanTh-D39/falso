"""GitHub search and intelligence tool using GitHub Public REST API.

Supports searching open source repositories, topics, stars, issues, and releases.
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
class GitHubTool(Tool):
    """Searches GitHub repositories, stars, issues, and releases."""

    name = "github"
    description = (
        "Search GitHub for open source repositories, Python packages, framework code, stars, and releases."
    )
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "GitHub search query (e.g. fastapi, threejs, llama-index, ollama).",
            },
        },
        "required": ["query"],
    }

    @classmethod
    def match_prompt(cls, prompt: str, context: Any = None) -> dict | None:
        prompt_stripped = prompt.strip()
        prompt_lower = prompt_stripped.lower()

        github_triggers = [
            "github", "repo for", "github repo", "github repository", "open source project", "stars on github"
        ]
        if any(re.search(r'\b' + re.escape(trig) + r'\b', prompt_lower) for trig in github_triggers):
            clean_q = re.sub(r'^(?:search\s+)?(?:github\s+)?(?:repo\s+for|repository\s+for|github\s+repo\s+for|github\s+repo|github)?\s*', '', prompt_stripped, flags=re.IGNORECASE).strip()
            logger.info("[GITHUB] Tool selected for query: %r", clean_q or prompt_stripped)
            return {"query": clean_q or prompt_stripped}
        return None

    @classmethod
    def format_result(cls, result: ToolResult) -> str:
        if not result.success:
            return "Unable to search GitHub right now."
        return str(result.data)

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "").strip()
        if not query:
            return ToolResult(success=False, error="No GitHub query provided.")

        try:
            url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=3"
            headers = {
                "User-Agent": "FALSO-AI-Assistant/2.0",
                "Accept": "application/vnd.github.v3+json"
            }

            logger.info("[GITHUB] HTTP Request -> %s", url)
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            items = data.get("items", [])
            if not items:
                return ToolResult(
                    success=True,
                    data=f"No GitHub repositories found matching '{query}'."
                )

            lines = [f"GitHub Search Results for '{query}':"]
            for repo in items[:3]:
                name = repo.get("full_name", "")
                desc = repo.get("description") or "No description provided."
                stars = repo.get("stargazers_count", 0)
                lang = repo.get("language") or "Code"
                html_url = repo.get("html_url", "")
                lines.append(f"• [{name}]({html_url}) — {stars:,} ⭐ ({lang})\n  {desc}")

            formatted_output = "\n".join(lines)
            logger.info("[GITHUB] Response received -> %r", formatted_output[:120])
            return ToolResult(success=True, data=formatted_output)

        except Exception as exc:
            logger.error("[GITHUB] Exception in GitHub provider: %s", exc, exc_info=True)
            return ToolResult(
                success=False,
                data="Unable to search GitHub right now.",
                error=str(exc)
            )
