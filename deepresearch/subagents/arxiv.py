"""Academic subagent: searches papers via Semantic Scholar API (no key needed).

Falls back to arXiv API if S2 is also unavailable.
"""
from __future__ import annotations

import asyncio
from typing import List

import httpx

from deepresearch.schemas import Citation

from .base import Subagent, chunk_text, make_source_id

S2_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
S2_FIELDS = "title,url,abstract,externalIds"


class ArxivSubagent(Subagent):
    """Search academic papers via Semantic Scholar (primary) or arXiv (fallback)."""

    def __init__(self):
        super().__init__("arxiv")

    async def search(self, query: str) -> List[Citation]:
        results = await self._search_s2(query)
        if results:
            return results
        return await self._search_arxiv(query)

    async def _search_s2(self, query: str) -> List[Citation]:
        """Search via Semantic Scholar (free, no API key)."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    S2_SEARCH_URL,
                    params={
                        "query": query,
                        "limit": 5,
                        "fields": S2_FIELDS,
                    },
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()
        except Exception:
            return []

        papers = data.get("data", [])
        citations: List[Citation] = []
        for i, paper in enumerate(papers):
            paper_id = paper.get("paperId", f"s2:{i}")
            source_id = make_source_id("arxiv", paper_id[:20])
            title = paper.get("title", "Unknown")
            url = paper.get("url", "") or f"https://api.semanticscholar.org/CorpusID:{paper.get('externalIds', {}).get('CorpusId', '')}"
            abstract = paper.get("abstract") or "No abstract available."

            chunks = chunk_text(abstract)
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

    async def _search_arxiv(self, query: str) -> List[Citation]:
        """Fallback: arXiv API via httpx."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "http://export.arxiv.org/api/query",
                    params={
                        "search_query": f"all:{query}",
                        "max_results": 5,
                        "sortBy": "relevance",
                    },
                    headers={"User-Agent": "DeepResearch-Lite/1.0"},
                )
                if resp.status_code != 200:
                    return []
                text = resp.text
        except Exception:
            return []

        # Parse arXiv Atom XML response
        citations: List[Citation] = []
        try:
            from xml.etree import ElementTree as ET
            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "arxiv": "http://arxiv.org/schemas/atom",
            }
            root = ET.fromstring(text)
            entries = root.findall("atom:entry", ns)
            for i, entry in enumerate(entries):
                title_el = entry.find("atom:title", ns)
                summary_el = entry.find("atom:summary", ns)
                id_el = entry.find("atom:id", ns)
                link_el = entry.find("atom:link", ns)

                title = title_el.text.strip() if title_el is not None and title_el.text else "Unknown"
                abstract = summary_el.text.strip() if summary_el is not None and summary_el.text else ""
                paper_url = link_el.get("href", "") if link_el is not None else ""
                paper_id = id_el.text.split("/")[-1] if id_el is not None and id_el.text else f"arxiv:{i}"

                source_id = make_source_id("arxiv", paper_id)
                chunks = chunk_text(abstract)
                for j, chunk in enumerate(chunks):
                    char_start = j * 350
                    citations.append(Citation(
                        source_id=source_id,
                        source_title=title,
                        source_url=paper_url,
                        chunk_id=f"chunk-{j}",
                        text=chunk,
                        char_span=(char_start, char_start + len(chunk)),
                        score=1.0 / (i + 1),
                    ))
        except Exception:
            pass

        return citations


async def main():
    """CLI entry point: python -m deepresearch.subagents.arxiv "query"."""
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m deepresearch.subagents.arxiv <query>")
        return

    query = sys.argv[1]
    sub = ArxivSubagent()
    results = await sub.search(query)
    print(f"Found {len(results)} citations for query: {query}")
    for c in results[:5]:
        print(f"  [{c.source_id}] {c.source_title[:80]} (score={c.score:.3f})")


if __name__ == "__main__":
    asyncio.run(main())
