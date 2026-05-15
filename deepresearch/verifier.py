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

# USD per 1M tokens, keyed by model name substring.
# Update entries here when adding new models via llm.py routing.
MODEL_PRICING = {
    "gpt-4o":           (2.50, 10.00),
    "gpt-4o-mini":      (0.15,  0.60),
    "claude-sonnet":    (3.00, 15.00),
    "claude-haiku":     (1.00,  5.00),
    "deepseek-chat":    (0.27,  1.10),
    "deepseek-reasoner": (0.55, 2.19),
    "glm-4":            (0.14,  0.14),
    "qwen-max":         (1.40,  5.60),
}
DEFAULT_PRICING = (2.50, 10.00)  # fallback when model name doesn't match


def _estimate_cost(model_name: str, n_input_tokens: int, n_output_tokens: int) -> float:
    """Estimate USD cost for an LLM call by matching model name prefix."""
    for key, (in_rate, out_rate) in MODEL_PRICING.items():
        if key in (model_name or "").lower():
            return n_input_tokens * in_rate / 1e6 + n_output_tokens * out_rate / 1e6
    in_rate, out_rate = DEFAULT_PRICING
    return n_input_tokens * in_rate / 1e6 + n_output_tokens * out_rate / 1e6


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _build_evidence_text(claim: Claim) -> str:
    """Concatenate all citation texts for a claim into one evidence block."""
    parts = []
    for cit in claim.citations:
        parts.append(f"[{cit.source_id}] {cit.text}")
    return "\n\n".join(parts)


def _verify_single(claim: Claim, evidence: str, review_pass: int = 1) -> dict:
    """Run a single NLI verification pass. Returns parsed JSON result."""
    prompt_template = _load_prompt()
    prompt = prompt_template.format(
        claim_text=claim.text,
        evidence_text=evidence,
    )

    from .llm import get_model

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        timeout=60.0,
    )
    model = get_model("verifier")

    system_msg = "你是一个严格的事实核验员。只输出 JSON。"
    if review_pass == 2:
        system_msg += " 这是二次复核。请特别谨慎：只有在证据与论断存在明确、不可调和的矛盾时，才判 contradicted。如果有任何合理的解释角度使论断可能成立，请判 neutral。只输出 JSON。"

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
    except Exception:
        return {}


def verify_claim(claim: Claim) -> Claim:
    """Verify a single claim against its citations using a two-pass NLI prompt.

    First pass: standard NLI classification.
    Second pass (only if contradicted): stricter review to reduce false positives.

    Returns the same Claim object with verifier_* fields populated.
    """
    evidence = _build_evidence_text(claim)

    if not evidence.strip():
        claim.verifier_label = "neutral"
        claim.verifier_score = 0.0
        claim.verifier_reasoning = "No evidence provided to verify."
        return claim

    # First pass
    result = _verify_single(claim, evidence, review_pass=1)

    label = result.get("label", "unchecked")
    score = float(result.get("score", 0))
    reasoning = result.get("reasoning", "核验失败。")

    # Second pass: if contradicted, re-verify with a higher bar
    if label == "contradicted":
        result2 = _verify_single(claim, evidence, review_pass=2)
        label2 = result2.get("label", label)
        score2 = float(result2.get("score", score))
        reasoning2 = result2.get("reasoning", reasoning)

        if label2 != "contradicted":
            # Second pass overturned the contradiction
            label = label2
            score = score2
            reasoning = f"[复核后修正] {reasoning2}"
        else:
            # Confirmed contradiction — use second pass reasoning
            reasoning = f"[二次复核确认] {reasoning2}"

    claim.verifier_label = label
    claim.verifier_score = score
    claim.verifier_reasoning = reasoning

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

    # Cost estimate via model-name-keyed pricing table (see MODEL_PRICING).
    # Two-pass verification roughly doubles tokens for contradicted claims.
    contradicted_count = labels.get("contradicted", 0)
    base_calls = total
    extra_calls = contradicted_count  # second-pass review
    est_input_tokens = (base_calls + extra_calls) * 500
    est_output_tokens = (base_calls + extra_calls) * 100

    from .llm import get_model

    verifier_model = get_model("verifier")
    cost = _estimate_cost(verifier_model, est_input_tokens, est_output_tokens)

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
