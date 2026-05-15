"""Research graph pipeline: LangGraph StateGraph orchestration.

Flow: classify → search → fuse → reflect → synthesize → verify
Each node is a callable function operating on a shared ResearchState.
The graph is compiled once at module load and reused across requests.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from openai import OpenAI

from .citation import rrf_fusion
from .orchestrator import classify_intent, decompose_query
from .schemas import Citation, ResearchReport
from .subagents.arxiv import ArxivSubagent
from .subagents.mock import MockSubagent
from .subagents.web import WebSubagent
from .synthesizer import synthesize
from .verifier import verify_report

load_dotenv()

REFLECTOR_PROMPT_PATH = Path(__file__).parent / "prompts" / "reflector.txt"


# ── State ────────────────────────────────────────────────────────────────────

class ResearchState(TypedDict, total=False):
    query: str
    intent: str
    sub_questions: List[str]
    citation_pool: List[Citation]
    report: ResearchReport
    stats: Dict[str, float]
    error: str


# ── Node functions ───────────────────────────────────────────────────────────

async def _classify_node(state: ResearchState) -> dict:
    """Step 1: Intent classification + query decomposition."""
    t0 = time.time()
    query = state["query"]

    intent = classify_intent(query)
    sub_questions = decompose_query(query, intent)

    stats: Dict[str, float] = state.get("stats", {})
    stats["classify"] = round(time.time() - t0, 2)

    return {"intent": intent, "sub_questions": sub_questions, "stats": stats}


async def _search_node(state: ResearchState) -> dict:
    """Step 2: Concurrent subagent search (web + arxiv + mock fallback), using cache."""
    t0 = time.time()
    query = state["query"]
    sub_questions: List[str] = state.get("sub_questions", [])
    stats: Dict[str, float] = state.get("stats", {})

    web = WebSubagent()
    arxiv_sub = ArxivSubagent()
    mock = MockSubagent()

    from .cache import get_cached_citations, cache_citations

    web_citations = get_cached_citations(f"__main__:{query}") or []
    arxiv_citations: List[Citation] = []

    if not web_citations:
        web_citations, arxiv_citations = await asyncio.gather(
            web.search(query),
            arxiv_sub.search(query),
        )
        if web_citations:
            cache_citations(f"__main__:{query}", web_citations)

    mock_citations: List[Citation] = []
    if not web_citations and not arxiv_citations:
        mock_citations = await mock.search(query)

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

    return {
        "citation_pool": web_citations + arxiv_citations + mock_citations,
        "stats": stats,
    }


async def _fuse_node(state: ResearchState) -> dict:
    """Step 3: RRF fusion + dedup by source_id prefix groups."""
    t0 = time.time()
    stats: Dict[str, float] = state.get("stats", {})
    raw: List[Citation] = state.get("citation_pool", [])

    # Partition into groups by source_id prefix for RRF
    web_group = [c for c in raw if c.source_id.startswith("web:")]
    arxiv_group = [c for c in raw if c.source_id.startswith(("arxiv:", "ss:"))]
    mock_group = [c for c in raw if c.source_id.startswith("mock:")]

    groups = [g for g in [web_group, arxiv_group, mock_group] if g]
    if not groups:
        groups = [raw]

    citation_pool = rrf_fusion(groups)
    stats["fuse"] = round(time.time() - t0, 2)
    stats["citations_after_fusion"] = len(citation_pool)

    return {"citation_pool": citation_pool, "stats": stats}


async def _reflect_node(state: ResearchState) -> dict:
    """Step 3.5: Review evidence for gaps, execute supplementary searches."""
    t0 = time.time()
    query = state["query"]
    sub_questions: List[str] = state.get("sub_questions", [])
    citation_pool: List[Citation] = state.get("citation_pool", [])
    stats: Dict[str, float] = state.get("stats", {})

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
        stats["reflect"] = round(time.time() - t0, 2)
        stats["citations_after_reflect"] = len(citation_pool)
        return {"stats": stats}

    searches: list[str] = data.get("searches", [])
    if not data.get("gaps_found") or not searches:
        stats["reflect"] = round(time.time() - t0, 2)
        stats["citations_after_reflect"] = len(citation_pool)
        return {"stats": stats}

    web = WebSubagent()
    new_citations: List[Citation] = []
    for sq in searches[:3]:
        try:
            results = await web.search(sq)
            new_citations.extend(results)
        except Exception:
            continue

    if new_citations:
        citation_pool = rrf_fusion([citation_pool, new_citations])

    stats["reflect"] = round(time.time() - t0, 2)
    stats["citations_after_reflect"] = len(citation_pool)

    return {"citation_pool": citation_pool, "stats": stats}


async def _synthesize_node(state: ResearchState) -> dict:
    """Step 4: Synthesize report from evidence pool."""
    t0 = time.time()
    stats: Dict[str, float] = state.get("stats", {})

    report = synthesize(
        query=state["query"],
        intent=state.get("intent", "exploration"),
        citation_pool=state.get("citation_pool", []),
        sub_questions=state.get("sub_questions"),
    )

    if not report.sub_questions:
        report.sub_questions = state.get("sub_questions", [])

    stats["synthesize"] = round(time.time() - t0, 2)

    return {"report": report, "stats": stats}


async def _verify_node(state: ResearchState) -> dict:
    """Step 5: NLI verification (async, all claims)."""
    t0 = time.time()
    stats: Dict[str, float] = state.get("stats", {})

    report = state.get("report")
    if report is not None:
        report = await verify_report(report)

    stats["verify"] = round(time.time() - t0, 2)

    return {"report": report, "stats": stats}


# ── Graph construction (compiled once at module load) ────────────────────────

_builder = StateGraph(ResearchState)

_builder.add_node("classify", _classify_node)
_builder.add_node("search", _search_node)
_builder.add_node("fuse", _fuse_node)
_builder.add_node("reflect", _reflect_node)
_builder.add_node("synthesize", _synthesize_node)
_builder.add_node("verify", _verify_node)

_builder.add_edge(START, "classify")
_builder.add_edge("classify", "search")
_builder.add_edge("search", "fuse")
_builder.add_edge("fuse", "reflect")
_builder.add_edge("reflect", "synthesize")
_builder.add_edge("synthesize", "verify")
_builder.add_edge("verify", END)

_compiled_graph = _builder.compile()


def render_mermaid() -> str:
    """Return the Mermaid diagram source for the compiled LangGraph pipeline."""
    return _compiled_graph.get_graph().draw_mermaid()


# ── Public API ───────────────────────────────────────────────────────────────

async def run_pipeline(query: str) -> ResearchReport:
    """Execute the full deep research pipeline via LangGraph StateGraph.

    Flow: classify → search → fuse → reflect → synthesize → verify
    """
    start_time = time.time()

    result = await _compiled_graph.ainvoke({"query": query})

    report = result.get("report")
    stats: Dict[str, float] = result.get("stats", {})

    if report is not None:
        stats["total"] = round(time.time() - start_time, 2)
        report.pipeline_stats = stats
        report.elapsed_seconds = stats["total"]

    return report
