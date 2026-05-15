"""Web subagent: searches via Tavily and extracts text content."""
from __future__ import annotations

import asyncio
import hashlib
import os
from typing import List

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tavily import TavilyClient

from deepresearch.schemas import Citation

from .base import Subagent, chunk_text, make_source_id

load_dotenv()


class WebSubagent(Subagent):
    """Search the web using Tavily and extract page content."""

    def __init__(self):
        super().__init__("web")
        api_key = os.getenv("TAVILY_API_KEY", "")
        # Only init client if a real API key is provided
        if api_key and api_key != "tvly-your-key-here" and len(api_key) > 10:
            self.client = TavilyClient(api_key=api_key)
        else:
            self.client = None

    async def search(self, query: str) -> List[Citation]:
        if self.client is None:
            return []

        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.search(query, max_results=5, search_depth="advanced")
            )
        except Exception:
            return []

        results = response.get("results", [])
        citations: List[Citation] = []
        for i, result in enumerate(results):
            url = result.get("url", "")
            title = result.get("title", "")
            content = result.get("content", "")

            source_id = make_source_id("web", url)
            chunks = chunk_text(content)

            for j, chunk in enumerate(chunks):
                char_start = j * 350  # Approx original offset (400 - 50 overlap)
                citations.append(Citation(
                    source_id=source_id,
                    source_title=title,
                    source_url=url,
                    chunk_id=f"chunk-{j}",
                    text=chunk,
                    char_span=(char_start, char_start + len(chunk)),
                    score=1.0 / (i + 1),  # Rank-based scoring
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


if __name__ == "__main__":
    asyncio.run(main())
