from __future__ import annotations

import html
import logging
import re
from typing import Any, ClassVar
from urllib.parse import unquote

import httpx

from app.tools.base import Tool, ToolResult
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@ToolRegistry.register
class WebSearchTool(Tool):
    """Real-time internet search tool to retrieve live up-to-date web information.
    
    Returns recent news, sports, weather, stock quotes, software releases, GitHub repos,
    documentation, and real-time world events complete with source titles and URLs.
    """

    name = "web_search"
    description = (
        "Search the live internet for current up-to-date information, news, weather, "
        "stocks, sports, software documentation, and real-time world events. "
        "Returns search snippets with source titles and clickable URLs."
    )
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query string to look up on the live internet.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of search results to return (1-10). Default is 5.",
            },
        },
        "required": ["query"],
    }

    keywords: ClassVar[list[str]] = [
        "search", "google", "ddg", "duckduckgo", "news", "latest", "current",
        "today", "weather", "stock", "price", "score", "release", "repo",
        "github", "docs", "live", "internet", "web", "find out", "what happened"
    ]

    @classmethod
    def match_prompt(cls, prompt: str, context: Any = None) -> dict | None:
        prompt_stripped = prompt.strip()
        prompt_lower = prompt_stripped.lower()
        
        search_triggers = [
            "search", "google", "ddg", "duckduckgo", "news", "latest", "current",
            "weather", "stock", "price", "score", "release", "github", "repo",
            "docs", "today", "right now", "what happened", "who won", "market",
            "trending", "live stream", "population", "gdp", "president",
            "prime minister", "ceo", "version", "flight", "score", "match"
        ]
        
        if any(re.search(r'\b' + re.escape(trig) + r'\b', prompt_lower) for trig in search_triggers):
            clean_q = re.sub(
                r'^(?:can you\s+)?(?:please\s+)?(?:search|look up|find|google|check)\s+(?:for|about\s+)?',
                '',
                prompt_stripped,
                flags=re.IGNORECASE,
            ).strip()
            return {"query": clean_q or prompt_stripped}
        return None

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "").strip()
        max_results = min(max(1, kwargs.get("max_results", 5)), 10)

        if not query:
            return ToolResult(
                success=False,
                error="No search query provided.",
            )

        logger.info("WebSearchTool executing query: %r (max_results=%d)", query, max_results)

        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(url, params={"q": query}, headers=headers)
                resp.raise_for_status()

            title_matches = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
            snippet_matches = re.findall(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', resp.text, re.DOTALL)

            results = []
            for i, (href, raw_title) in enumerate(title_matches[:max_results]):
                clean_title = html.unescape(re.sub(r'<[^>]+>', '', raw_title).strip())
                clean_snippet = (
                    html.unescape(re.sub(r'<[^>]+>', '', snippet_matches[i]).strip())
                    if i < len(snippet_matches)
                    else ""
                )

                actual_url = href
                if "uddg=" in href:
                    actual_url = unquote(href.split("uddg=")[1].split("&")[0])
                elif href.startswith("//"):
                    actual_url = "https:" + href

                results.append({
                    "title": clean_title,
                    "url": actual_url,
                    "snippet": clean_snippet,
                })

            if not results:
                return ToolResult(
                    success=True,
                    data=f"No web search results found for query: {query!r}",
                )

            output_lines = [f"Web Search Results for '{query}':\n"]
            for r in results:
                output_lines.append(f"• [{r['title']}]({r['url']})\n  {r['snippet']}\n")

            return ToolResult(
                success=True,
                data="\n".join(output_lines),
            )

        except Exception as exc:
            logger.exception("WebSearchTool execution failed")
            return ToolResult(
                success=False,
                error=f"Web search failed: {exc}",
            )
