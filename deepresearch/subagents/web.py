"""Web subagent: searches via Tavily and extracts full page text content."""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
from typing import List

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tavily import TavilyClient

from deepresearch.schemas import Citation

from .base import Subagent, chunk_text, make_source_id

load_dotenv()

# Number of top Tavily results to fetch full page content for
FULL_FETCH_COUNT = 3
# Max characters of cleaned text to keep per page
MAX_PAGE_TEXT = 3000

# Tags/classes to strip before text extraction
STRIP_SELECTORS = [
    "script", "style", "noscript", "nav", "footer", "header",
    "aside", ".sidebar", ".nav", ".footer", ".header", ".menu",
    '[role="navigation"]', '[role="banner"]', '[role="contentinfo"]',
]


def _clean_html(html: str) -> str:
    """Extract clean, readable text from HTML."""
    try:
        soup = BeautifulSoup(html, "html.parser")

        # Remove noise elements
        for selector in STRIP_SELECTORS:
            for el in soup.select(selector):
                el.decompose()

        # Prefer main content areas
        main = soup.find("main") or soup.find("article") or soup.find(id=re.compile(r"content|article|post|main", re.I))
        if main:
            text = main.get_text(separator="\n")
        else:
            text = soup.body.get_text(separator="\n") if soup.body else soup.get_text(separator="\n")

        # Collapse whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        lines = [line.strip() for line in text.split("\n")]
        lines = [line for line in lines if len(line) > 40]  # Skip nav lines / short fragments
        cleaned = "\n\n".join(lines)
        return cleaned[:MAX_PAGE_TEXT]
    except Exception:
        return ""


async def _fetch_page(url: str, timeout: float = 10.0) -> str:
    """Fetch and clean a single web page."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
                follow_redirects=True,
            )
            if resp.status_code != 200:
                return ""
            return _clean_html(resp.text)
    except Exception:
        return ""


class WebSubagent(Subagent):
    """Search the web using Tavily and extract full page content."""

    def __init__(self):
        super().__init__("web")
        api_key = os.getenv("TAVILY_API_KEY", "")
        if api_key and api_key != "tvly-your-key-here" and len(api_key) > 10:
            self.client = TavilyClient(api_key=api_key)
        else:
            self.client = None

    async def search(self, query: str) -> List[Citation]:
        if self.client is None:
            return []

        # Step 1: Get Tavily search results
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.search(query, max_results=5, search_depth="advanced")
            )
        except Exception:
            return []

        results = response.get("results", [])
        if not results:
            return []

        # Step 2: Concurrently fetch full pages for top results
        urls_to_fetch = [r.get("url", "") for r in results[:FULL_FETCH_COUNT] if r.get("url")]
        full_pages = await asyncio.gather(*[_fetch_page(url) for url in urls_to_fetch])

        # Build url → full_text map
        url_text_map: dict[str, str] = {}
        for url, text in zip(urls_to_fetch, full_pages):
            if text:
                url_text_map[url] = text

        # Step 3: Build citations from Tavily snippets + full page content
        citations: List[Citation] = []
        for i, result in enumerate(results):
            url = result.get("url", "")
            title = result.get("title", "")
            snippet = result.get("content", "")

            source_id = make_source_id("web", url)

            # Use full page text if available, otherwise fall back to snippet
            full_text = url_text_map.get(url, "")
            source_text = full_text if full_text else snippet

            if not source_text.strip():
                continue

            chunks = chunk_text(source_text)
            for j, chunk in enumerate(chunks):
                char_start = j * 350
                citations.append(Citation(
                    source_id=source_id,
                    source_title=title,
                    source_url=url,
                    chunk_id=f"chunk-{j}",
                    text=chunk,
                    char_span=(char_start, char_start + len(chunk)),
                    score=1.0 / (i + 1),
                ))

        return citations


async def main():
    """CLI entry point: python -m deepresearch.subagents.web "query"."""
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m deepresearch.subagents.web <query>")
        return

    query = sys.argv[1]
    sub = WebSubagent()
    results = await sub.search(query)
    print(f"Found {len(results)} citations for query: {query}")
    for c in results[:5]:
        print(f"  [{c.source_id}] {c.source_title[:80]} (score={c.score:.3f})")
        print(f"    text preview: {c.text[:120]}...")


if __name__ == "__main__":
    asyncio.run(main())
