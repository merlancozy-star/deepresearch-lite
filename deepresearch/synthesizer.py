"""Synthesizer: two-stage report generation (outline → section-by-section).

Stage 1: Generate report outline from evidence summaries.
Stage 2: Write each section with relevance-filtered evidence.
Stage 3: Assemble final report with executive summary and references.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI

from .schemas import Citation, Claim, ResearchReport

load_dotenv()

PROMPT_DIR = Path(__file__).parent / "prompts"
SYNTHESIZER_PROMPT_PATH = PROMPT_DIR / "synthesizer.txt"
OUTLINE_PROMPT_PATH = PROMPT_DIR / "outline.txt"
SECTION_WRITER_PROMPT_PATH = PROMPT_DIR / "section_writer.txt"

TOP_K_PER_SECTION = 15  # Max citations to pass per section


def _load_prompt(name: str) -> str:
    path = PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


def _build_citation_map(citations: List[Citation]) -> Dict[str, Dict[str, Citation]]:
    """Build source_id → {chunk_id → Citation} lookup."""
    mapping: Dict[str, Dict[str, Citation]] = {}
    for c in citations:
        if c.source_id not in mapping:
            mapping[c.source_id] = {}
        mapping[c.source_id][c.chunk_id] = c
    return mapping


def _make_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        timeout=120.0,
    )


def _get_model() -> str:
    from .llm import get_model
    return get_model("synthesizer")


# ── Stage 1: Outline Generation ───────────────────────────────────────────

def _format_evidence_summary(citations: List[Citation]) -> str:
    """Compact summary of evidence pool for outline generation."""
    lines = []
    seen_titles = set()
    for i, c in enumerate(citations):
        if c.source_title not in seen_titles:
            seen_titles.add(c.source_title)
            lines.append(f"[{c.source_id}] {c.source_title[:120]}")
        if len(lines) >= 30:
            break
    return "\n".join(lines)


def _generate_outline(
    query: str,
    intent: str,
    citations: List[Citation],
) -> List[dict]:
    """Stage 1: Generate a report outline from evidence summaries."""
    prompt = _load_prompt("outline.txt")
    evidence_summary = _format_evidence_summary(citations)

    system_msg = prompt.format(
        evidence_summary=evidence_summary,
        query=query,
        intent=intent,
    )

    client = _make_client()
    try:
        response = client.chat.completions.create(
            model=_get_model(),
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"请为以下研究问题规划报告大纲：{query}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        data = json.loads(response.choices[0].message.content or "{}")
        sections = data.get("sections", [])
        if sections:
            return sections
    except Exception:
        pass

    # Fallback: build basic outline from sub-questions
    return [{"title": "核心分析", "key_question": query, "description": "回答用户查询的核心内容"}]


# ── Relevance Filtering ────────────────────────────────────────────────────

def _tokenize(text: str) -> set[str]:
    """Simple tokenization for keyword overlap scoring."""
    # Split on non-alphanumeric, keep tokens >= 2 chars
    tokens = re.findall(r"[a-zA-Z0-9一-鿿]{2,}", text.lower())
    return set(tokens)


def _relevance_score(citation: Citation, section: dict) -> float:
    """Compute relevance of a citation to a section via keyword overlap."""
    section_text = f"{section.get('title', '')} {section.get('key_question', '')} {section.get('description', '')}"
    section_tokens = _tokenize(section_text)
    if not section_tokens:
        return 0.0

    cit_text = f"{citation.source_title} {citation.text}"
    cit_tokens = _tokenize(cit_text)

    overlap = section_tokens & cit_tokens
    return len(overlap) / max(len(section_tokens), 1)


def _filter_evidence(
    citations: List[Citation],
    section: dict,
    top_k: int = TOP_K_PER_SECTION,
) -> List[Citation]:
    """Select the most relevant citations for a section."""
    scored = [(c, _relevance_score(c, section)) for c in citations]
    scored.sort(key=lambda x: x[1], reverse=True)

    # Remove duplicates (same source_id) keeping highest score per source
    seen_sources: set[str] = set()
    filtered: List[Citation] = []
    for c, score in scored:
        if score <= 0 and len(filtered) >= 3:
            continue  # Skip zero-relevance unless we have very few
        if c.source_id not in seen_sources:
            seen_sources.add(c.source_id)
            filtered.append(c)
        if len(filtered) >= top_k:
            break

    return filtered


# ── Stage 2: Section Writing ───────────────────────────────────────────────

def _format_section_evidence(citations: List[Citation]) -> str:
    """Format citations as evidence text for a section."""
    lines = []
    for i, c in enumerate(citations):
        lines.append(
            f"[{i}] source_id={c.source_id} chunk_id={c.chunk_id}\n"
            f"    title={c.source_title}\n"
            f"    text={c.text[:500]}"
        )
    return "\n".join(lines)


def _write_section(
    query: str,
    section: dict,
    citations: List[Citation],
    citation_map: Dict[str, Dict[str, Citation]],
    max_retries: int = 2,
) -> Tuple[str, List[Claim]]:
    """Stage 2: Write a single report section with filtered evidence."""
    prompt = _load_prompt("section_writer.txt")
    evidence_text = _format_section_evidence(citations)

    system_msg = prompt.format(
        section_title=section.get("title", ""),
        key_question=section.get("key_question", ""),
        description=section.get("description", ""),
        query=query,
        section_evidence=evidence_text,
    )

    client = _make_client()

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=_get_model(),
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"请撰写「{section.get('title', '')}」章节。"},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            data = json.loads(response.choices[0].message.content or "{}")
        except Exception:
            if attempt == max_retries - 1:
                return "", []
            continue

        section_md = data.get("section_markdown", "")
        raw_claims = data.get("claims", [])
        claims: List[Claim] = []
        all_valid = True

        for rc in raw_claims:
            claim_text = rc.get("text", "")
            source_ids = rc.get("source_ids", [])
            chunk_ids = rc.get("chunk_ids", [])

            matched_citations: List[Citation] = []
            for sid in source_ids:
                if sid in citation_map:
                    chunks = citation_map[sid]
                    for cid in chunk_ids:
                        if cid in chunks:
                            matched_citations.append(chunks[cid])
                            break
                    else:
                        if chunks:
                            matched_citations.append(next(iter(chunks.values())))

            if not matched_citations:
                all_valid = False
                if attempt == max_retries - 1:
                    claim_text = "[UNCITED] " + claim_text
                    matched_citations = [Citation(
                        source_id="synthesizer:fallback",
                        source_title="Fallback",
                        source_url="",
                        chunk_id="fallback-0",
                        text="No evidence found.",
                        char_span=(0, 20),
                        score=0.0,
                    )]
                else:
                    continue

            claims.append(Claim(
                text=claim_text,
                section=section.get("title", ""),
                citations=matched_citations,
            ))

        # If no valid claims and we have retries left, retry the LLM call
        if not all_valid and attempt < max_retries - 1:
            continue

        return section_md, claims

    return "", []


# ── Stage 3: Final Assembly ────────────────────────────────────────────────

def _assemble_report(
    query: str,
    intent: str,
    sections: List[dict],
    section_contents: List[Tuple[str, List[Claim]]],
    all_citations: List[Citation],
    citation_map: Dict[str, Dict[str, Citation]],
    sub_questions: List[str],
) -> Tuple[str, List[Claim], List[dict], str]:
    """Stage 3: Generate executive summary, compile references, assemble final markdown."""
    # Build the detailed analysis section
    detailed_md = ""
    for i, (section_info, (section_md, _)) in enumerate(zip(sections, section_contents)):
        title = section_info.get("title", f"章节{i+1}")
        detailed_md += f"### {title}\n\n{section_md}\n\n"

    # Collect all claims
    all_claims: List[Claim] = []
    for _, claims in section_contents:
        all_claims.extend(claims)

    # Collect unique source_ids used in claims
    used_source_ids: set[str] = set()
    for claim in all_claims:
        for cit in claim.citations:
            if cit.source_id != "synthesizer:fallback":
                used_source_ids.add(cit.source_id)

    # Build references list
    references: List[dict] = []
    for sid in sorted(used_source_ids):
        if sid in citation_map:
            first_chunk = next(iter(citation_map[sid].values()))
            references.append({
                "ref_id": sid,
                "title": first_chunk.source_title,
                "url": first_chunk.source_url,
                "excerpt": first_chunk.text[:150],
            })

    # Generate summary + key findings using the original synthesizer prompt
    synth_prompt = _load_prompt("synthesizer.txt")
    evidence_text = _format_section_evidence(all_citations[:40])

    sub_q_text = "\n".join(f"- {q}" for q in sub_questions)

    system_msg = synth_prompt.format(
        evidence_pool=evidence_text,
        sub_questions=sub_q_text,
        query=query,
    )

    # Add context that detailed analysis is already written
    system_msg += f"\n\n## 已完成的详细分析\n\n{detailed_md[:3000]}\n\n请基于以上详细分析，生成摘要、核心发现、调研方法和参考文献。详细分析部分已经完成，请直接保留。"

    client = _make_client()
    try:
        response = client.chat.completions.create(
            model=_get_model(),
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"请撰写最终报告：{query}\n\n意图类型：{intent}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        data = json.loads(response.choices[0].message.content or "{}")
    except Exception:
        data = {}

    # Build final markdown
    final_md = data.get("markdown", "")
    if not final_md:
        # Manual assembly as fallback
        sub_q_list = "\n".join(f"- {q}" for q in sub_questions)
        ref_text = "\n\n".join(
            f"[^{r['ref_id']}]: **{r['title']}** — [{r['url']}]({r['url']})\n"
            f"  > 源文摘录：\"{r['excerpt']}...\""
            for r in references[:10]
        )
        final_md = f"""## 摘要

基于对 {len(all_citations)} 条证据片段的调研，本报告分析了 {query}。

## 调研方法

- 搜索策略：Web (Tavily) + 学术 (Semantic Scholar/arXiv)
- 检索子问题：
{sub_q_list}
- 分析方法：每条论断独立核验（NLI 三分类）

## 核心发现

（请查看详细分析章节中的具体发现）

## 详细分析

{detailed_md}

## 参考文献

{ref_text}
"""

    # Merge claims from section writing with any additional claims from assembly
    additional_claims = []
    for rc in data.get("claims", []):
        claim_text = rc.get("text", "")
        source_ids = rc.get("source_ids", [])
        chunk_ids = rc.get("chunk_ids", [])
        section = rc.get("section", "")

        matched: List[Citation] = []
        for sid in source_ids:
            if sid in citation_map:
                chunks = citation_map[sid]
                for cid in chunk_ids:
                    if cid in chunks:
                        matched.append(chunks[cid])
                        break
                else:
                    if chunks:
                        matched.append(next(iter(chunks.values())))
        if matched:
            additional_claims.append(Claim(
                text=claim_text,
                section=section,
                citations=matched,
            ))

    # Merge: claims from assembly + claims from sections (dedup by text prefix)
    seen_texts = {c.text[:80] for c in all_claims}
    for ac in additional_claims:
        if ac.text[:80] not in seen_texts:
            all_claims.append(ac)
            seen_texts.add(ac.text[:80])

    refs = data.get("references", references)
    methodology = data.get("methodology", "")

    return final_md, all_claims, refs, methodology


# ── Main Entry Point ───────────────────────────────────────────────────────

def synthesize(
    query: str,
    intent: str,
    citation_pool: List[Citation],
    sub_questions: Optional[List[str]] = None,
    max_retries: int = 3,
) -> ResearchReport:
    """Two-stage synthesis: outline → section-by-section writing → assembly.

    Args:
        query: The user's original query.
        intent: One of exploration/comparison/latest.
        citation_pool: All citations from subagents.
        sub_questions: Decomposed sub-questions (optional).
        max_retries: Max LLM retries on citation validation failure.

    Returns:
        A ResearchReport with citation-backed claims.
    """
    start_time = time.time()

    if sub_questions is None:
        sub_questions = [query]

    citation_map = _build_citation_map(citation_pool)

    # ── Stage 1: Generate outline ──
    sections = _generate_outline(query, intent, citation_pool)

    # ── Stage 2: Write each section ──
    section_contents: List[Tuple[str, List[Claim]]] = []
    for section in sections:
        section_citations = _filter_evidence(citation_pool, section)
        section_md, claims = _write_section(
            query, section, section_citations, citation_map
        )
        section_contents.append((section_md, claims))

    # ── Stage 3: Assemble final report ──
    markdown, all_claims, references, methodology = _assemble_report(
        query, intent, sections, section_contents,
        citation_pool, citation_map, sub_questions,
    )

    elapsed = time.time() - start_time

    return ResearchReport(
        query=query,
        intent=intent,  # type: ignore
        sub_questions=sub_questions,
        claims=all_claims,
        references=references,
        markdown=markdown,
        methodology=methodology,
        cost_usd=0.0,  # Will be estimated by caller
        elapsed_seconds=round(elapsed, 2),
    )
