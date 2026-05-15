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

    # Step 1: Intent classification + query decomposition
    intent = classify_intent(query)
    sub_questions = decompose_query(query, intent)

    # Step 2: Concurrent subagent search (web + arxiv + mock fallback)
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

    # Step 3: RRF fusion + dedup
    citation_pool = rrf_fusion([web_citations, arxiv_citations, mock_citations])

    # Step 4: Synthesize report
    report = synthesize(query, intent, citation_pool, sub_questions)

    # Step 5: Verify (async)
    report = await verify_report(report)

    report.elapsed_seconds = round(time.time() - start_time, 2)
    return report
