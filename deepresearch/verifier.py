"""Verifier: NLI-based claim verification (Layer 2).

Independent LLM instance judges whether each claim is entailed, contradicted,
or neutral with respect to its supporting evidence. Runs asynchronously with
a concurrency limit.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv
from openai import OpenAI

from .schemas import Claim, ResearchReport

load_dotenv()

PROMPT_PATH = Path(__file__).parent / "prompts" / "verifier.txt"
MAX_CONCURRENT = 5


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _build_evidence_text(claim: Claim) -> str:
    """Concatenate all citation texts for a claim into one evidence block."""
    parts = []
    for cit in claim.citations:
        parts.append(f"[{cit.source_id}] {cit.text}")
    return "\n\n".join(parts)


def verify_claim(claim: Claim) -> Claim:
    """Verify a single claim against its citations using an NLI prompt.

    Returns the same Claim object with verifier_* fields populated.
    """
    prompt_template = _load_prompt()
    evidence = _build_evidence_text(claim)

    if not evidence.strip():
        claim.verifier_label = "neutral"
        claim.verifier_score = 0.0
        claim.verifier_reasoning = "No evidence provided to verify."
        return claim

    prompt = prompt_template.format(
        claim_text=claim.text,
        evidence_text=evidence,
    )

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        timeout=60.0,
    )
    model = os.getenv("OPENAI_MODEL", "gpt-4o")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个严格的事实核验员。只输出 JSON。"},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        content = response.choices[0].message.content or "{}"
        result = json.loads(content)
    except Exception:
        result = {}

    claim.verifier_label = result.get("label", "unchecked")
    claim.verifier_score = float(result.get("score", 0))
    claim.verifier_reasoning = result.get("reasoning", "核验失败。")

    return claim


async def verify_claim_async(claim: Claim) -> Claim:
    """Async wrapper for verify_claim."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, verify_claim, claim)


async def _verify_batch(claims: List[Claim]) -> List[Claim]:
    """Verify claims with a concurrency limit."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def bounded_verify(claim: Claim) -> Claim:
        async with semaphore:
            return await verify_claim_async(claim)

    return await asyncio.gather(*(bounded_verify(c) for c in claims))


async def verify_report(report: ResearchReport) -> ResearchReport:
    """Verify all claims in a report (Day 1: full verification, no sampling).

    Modifies the report in-place and returns it.
    """
    start_time = time.time()

    if not report.claims:
        report.verifier_summary = {
            "total": 0, "entailed": 0, "neutral": 0, "contradicted": 0,
            "cost_usd": 0.0, "elapsed_seconds": 0.0,
        }
        return report

    verified_claims = await _verify_batch(report.claims)
    report.claims = verified_claims

    # Build summary
    labels: Dict[str, int] = {"entailed": 0, "neutral": 0, "contradicted": 0, "unchecked": 0}
    for c in verified_claims:
        label = c.verifier_label
        labels[label] = labels.get(label, 0) + 1

    total = len(verified_claims)
    elapsed = time.time() - start_time

    # Rough cost estimate: each claim ~500 tokens in/out
    est_input_tokens = total * 500
    est_output_tokens = total * 100
    cost = (
        est_input_tokens * 2.5 / 1_000_000
        + est_output_tokens * 10 / 1_000_000
    )

    report.verifier_summary = {
        "total": total,
        "entailed": labels["entailed"],
        "neutral": labels["neutral"],
        "contradicted": labels["contradicted"],
        "unchecked": labels.get("unchecked", 0),
        "entailed_pct": round(labels["entailed"] / total * 100, 1) if total else 0,
        "neutral_pct": round(labels["neutral"] / total * 100, 1) if total else 0,
        "contradicted_pct": round(labels["contradicted"] / total * 100, 1) if total else 0,
        "cost_usd": round(cost, 6),
        "elapsed_seconds": round(elapsed, 2),
    }

    return report


def verify_hardcoded_samples() -> List[dict]:
    """Run verifier on 3 hardcoded samples (entailed / contradicted / neutral).

    Returns list of results for manual inspection.
    """
    from .schemas import Citation

    samples = [
        {
            "name": "entailed",
            "claim": Claim(
                text="Transformers use self-attention mechanisms.",
                citations=[Citation(
                    source_id="test:entailed",
                    source_title="Test",
                    source_url="",
                    chunk_id="c0",
                    text="The Transformer architecture relies entirely on self-attention to compute representations.",
                    char_span=(0, 90),
                    score=0.9,
                )],
            ),
        },
        {
            "name": "contradicted",
            "claim": Claim(
                text="Transformers use recurrent neural networks for sequence processing.",
                citations=[Citation(
                    source_id="test:contra",
                    source_title="Test",
                    source_url="",
                    chunk_id="c0",
                    text="The Transformer eschews recurrence and instead relies entirely on an attention mechanism.",
                    char_span=(0, 95),
                    score=0.9,
                )],
            ),
        },
        {
            "name": "neutral",
            "claim": Claim(
                text="Transformers achieve state-of-the-art on all NLP benchmarks.",
                citations=[Citation(
                    source_id="test:neutral",
                    source_title="Test",
                    source_url="",
                    chunk_id="c0",
                    text="The Transformer model achieved 28.4 BLEU on the WMT 2014 English-to-German translation task.",
                    char_span=(0, 90),
                    score=0.9,
                )],
            ),
        },
    ]

    results = []
    for s in samples:
        result = verify_claim(s["claim"])
        results.append({
            "name": s["name"],
            "claim": result.text,
            "label": result.verifier_label,
            "score": result.verifier_score,
            "reasoning": result.verifier_reasoning,
        })

    return results
