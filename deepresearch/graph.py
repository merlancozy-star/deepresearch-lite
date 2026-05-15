"""Research graph pipeline: orchestrates the full research flow.

Flow: classify → decompose → search → fuse → reflect → synthesize → verify
Each node is independently callable (for future MCP Server exposure).
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI

from .citation import rrf_fusion
from .orchestrator import classify_intent, decompose_query
from .schemas import Citation, Claim, ResearchReport
from .subagents.arxiv import ArxivSubagent
from .subagents.mock import MockSubagent
from .subagents.web import WebSubagent
from .synthesizer import synthesize
from .verifier import verify_report

load_dotenv()

REFLECTOR_PROMPT_PATH = Path(__file__).parent / "prompts" / "reflector.txt"


async def _reflect_and_search(
    query: str,
    sub_questions: List[str],
    citation_pool: List[Citation],
) -> List[Citation]:
    """Step 3.5: Review collected evidence for gaps, execute supplementary searches.

    Returns an augmented citation pool.
    """
    # Build a compact evidence summary
    seen_titles: set[str] = set()
    summary_lines: list[str] = []
    for c in citation_pool[:30]:
        if c.source_title not in seen_titles:
            seen_titles.add(c.source_title)
            summary_lines.append(f"- {c.source_title[:120]}")
    evidence_summary = "\n".join(summary_lines) if summary_lines else "（无证据）"

    sub_q_text = "\n".join(f"- {q}" for q in sub_questions)

    prompt_template = REFLECTOR_PROMPT_PATH.read_text(encoding="utf-8")
    system_msg = prompt_template.format(
        query=query,
        sub_questions=sub_q_text,
        evidence_summary=evidence_summary,
    )

    from .llm import get_model

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        timeout=60.0,
    )
    model = get_model("reflector")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"审阅以下研究的证据完整性：{query}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        data = json.loads(response.choices[0].message.content or "{}")
    except Exception:
        return citation_pool  # If reflection fails, proceed with what we have

    if not data.get("gaps_found"):
        return citation_pool

    searches = data.get("searches", [])
    if not searches:
        return citation_pool

    # Execute supplementary searches
    web = WebSubagent()
    new_citations: List[Citation] = []
    for sq in searches[:3]:
        try:
            results = await web.search(sq)
            new_citations.extend(results)
        except Exception:
            continue

    if new_citations:
        # Re-fuse: merge new into existing pool
        return rrf_fusion([citation_pool, new_citations])

    return citation_pool


async def run_pipeline(query: str) -> ResearchReport:
    """Execute the full deep research pipeline.

    Flow: classify → decompose → search → fuse → reflect → synthesize → verify
    """
    start_time = time.time()
    stats: Dict[str, float] = {}

    # Step 1: Intent classification + query decomposition
    t0 = time.time()
    intent = classify_intent(query)
    sub_questions = decompose_query(query, intent)
    stats["classify"] = round(time.time() - t0, 2)

    # Step 2: Concurrent subagent search (web + arxiv + mock fallback), using cache
    t0 = time.time()
    web = WebSubagent()
    arxiv_sub = ArxivSubagent()
    mock = MockSubagent()

    from .cache import get_cached_citations, cache_citations

    # Check cache for main query
    web_citations = get_cached_citations(f"__main__:{query}") or []
    arxiv_citations: List[Citation] = []

    if not web_citations:
        web_citations, arxiv_citations = await asyncio.gather(
            web.search(query),
            arxiv_sub.search(query),
        )
        if web_citations:
            cache_citations(f"__main__:{query}", web_citations)

    # Only enable mock when both web and arxiv fail (e.g. API blocked)
    mock_citations: List[Citation] = []
    if not web_citations and not arxiv_citations:
        mock_citations = await mock.search(query)

    # Also search sub-questions with web (arXiv rate-limits quickly), using cache
    from .cache import get_cached_citations, cache_citations

    for sq in sub_questions[:3]:
        cached = get_cached_citations(sq)
        if cached:
            web_citations.extend(cached)
        else:
            wc = await web.search(sq)
            web_citations.extend(wc)
            if wc:
                cache_citations(sq, wc)

    total_search = len(web_citations) + len(arxiv_citations) + len(mock_citations)
    stats["search"] = round(time.time() - t0, 2)
    stats["sources_found"] = total_search

    # Step 3: RRF fusion + dedup
    t0 = time.time()
    citation_pool = rrf_fusion([web_citations, arxiv_citations, mock_citations])
    stats["fuse"] = round(time.time() - t0, 2)
    stats["citations_after_fusion"] = len(citation_pool)

    # Step 3.5: Reflection — check for information gaps and supplement
    t0 = time.time()
    citation_pool = await _reflect_and_search(query, sub_questions, citation_pool)
    stats["reflect"] = round(time.time() - t0, 2)
    stats["citations_after_reflect"] = len(citation_pool)

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
