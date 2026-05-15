"""Research graph pipeline: orchestrates the full research flow.

Day 1 simplified implementation: async pipeline instead of full LangGraph StateGraph.
Each node is independently callable (for future MCP Server exposure).
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List

from .citation import rrf_fusion
from .orchestrator import classify_intent, decompose_query
from .schemas import Claim, Citation, ResearchReport
from .subagents.arxiv import ArxivSubagent
from .subagents.mock import MockSubagent
from .subagents.web import WebSubagent
from .synthesizer import synthesize
from .verifier import verify_report


async def run_pipeline(query: str) -> ResearchReport:
    """Execute the full deep research pipeline.

    Flow: classify → decompose → search (web + arxiv + mock) → synthesize → verify
    """
    start_time = time.time()
    stats: Dict[str, float] = {}

    # Step 1: Intent classification + query decomposition
    t0 = time.time()
    intent = classify_intent(query)
    sub_questions = decompose_query(query, intent)
    stats["classify"] = round(time.time() - t0, 2)

    # Step 2: Concurrent subagent search (web + arxiv + mock fallback)
    t0 = time.time()
    web = WebSubagent()
    arxiv_sub = ArxivSubagent()
    mock = MockSubagent()

    web_citations, arxiv_citations, mock_citations = await asyncio.gather(
        web.search(query),
        arxiv_sub.search(query),
        mock.search(query),
    )

    # Also search sub-questions with web only (arXiv rate-limits quickly)
    for sq in sub_questions[:3]:
        wc = await web.search(sq)
        web_citations.extend(wc)

    total_search = len(web_citations) + len(arxiv_citations) + len(mock_citations)
    stats["search"] = round(time.time() - t0, 2)
    stats["sources_found"] = total_search

    # Step 3: RRF fusion + dedup
    t0 = time.time()
    citation_pool = rrf_fusion([web_citations, arxiv_citations, mock_citations])
    stats["fuse"] = round(time.time() - t0, 2)
    stats["citations_after_fusion"] = len(citation_pool)

    # Step 4: Synthesize report
    t0 = time.time()
    report = synthesize(query, intent, citation_pool, sub_questions)
    stats["synthesize"] = round(time.time() - t0, 2)

    # Attach sub_questions to report (synthesizer may already set them, but ensure)
    if not report.sub_questions:
        report.sub_questions = sub_questions

    # Step 5: Verify (async)
    t0 = time.time()
    report = await verify_report(report)
    stats["verify"] = round(time.time() - t0, 2)

    stats["total"] = round(time.time() - start_time, 2)
    report.pipeline_stats = stats
    report.elapsed_seconds = stats["total"]
    return report
