"""Multi-provider LLM client factory.

Supports per-stage model selection via environment variables:
  LLM_MODEL_ORCHESTRATOR  — intent classify + decompose (default: OPENAI_MODEL)
  LLM_MODEL_SYNTHESIZER   — report synthesis (default: OPENAI_MODEL)
  LLM_MODEL_VERIFIER      — NLI verification (default: OPENAI_MODEL)
  LLM_MODEL_REFLECTOR     — gap reflection (default: OPENAI_MODEL)

All use the same OPENAI_BASE_URL / OPENAI_API_KEY for simplicity.
"""
from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Per-stage model defaults (fall back to OPENAI_MODEL, then gpt-4o)
_DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

_STAGE_MODELS = {
    "orchestrator": os.getenv("LLM_MODEL_ORCHESTRATOR", _DEFAULT_MODEL),
    "synthesizer": os.getenv("LLM_MODEL_SYNTHESIZER", _DEFAULT_MODEL),
    "verifier": os.getenv("LLM_MODEL_VERIFIER", _DEFAULT_MODEL),
    "reflector": os.getenv("LLM_MODEL_REFLECTOR", _DEFAULT_MODEL),
}


def get_client(stage: Optional[str] = None) -> OpenAI:
    """Get an OpenAI client. Stage name determines model selection."""
    return OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        timeout=120.0,
    )


def get_model(stage: Optional[str] = None) -> str:
    """Get the model name for a given pipeline stage."""
    if stage and stage in _STAGE_MODELS:
        return _STAGE_MODELS[stage]
    return _DEFAULT_MODEL


def get_cost_estimate(prompt_tokens: int, completion_tokens: int, stage: str = "default") -> float:
    """Estimate cost based on token usage and model pricing tier.

    Uses rough pricing:
      - DeepSeek models: $0.28/1M input, $1.10/1M output
      - GPT-4o class: $2.50/1M input, $10/1M output
      - Default (conservative): $1.00/1M input, $4/1M output
    """
    model = get_model(stage).lower()

    if "deepseek" in model:
        input_price, output_price = 0.28, 1.10
    elif "gpt-4o" in model or "gpt-4" in model:
        input_price, output_price = 2.50, 10.00
    elif "claude" in model:
        input_price, output_price = 3.00, 15.00
    else:
        input_price, output_price = 1.00, 4.00

    return prompt_tokens * input_price / 1_000_000 + completion_tokens * output_price / 1_000_000
