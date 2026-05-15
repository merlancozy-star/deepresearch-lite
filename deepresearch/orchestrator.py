"""Orchestrator: intent classification + query decomposition."""
from __future__ import annotations

import json
import os
from typing import List, Literal

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

Intent = Literal["exploration", "comparison", "latest"]

INTENT_CLASSIFY_PROMPT = """你是一个查询意图分类器。给定一个研究问题，将其分类为以下之一：

- "exploration"：对某个主题的开放式探索，如"X 是什么"或"X 如何工作"
- "comparison"：比较两个或多个事物（框架、方法、模型等）
- "latest"：询问最新进展、近期新闻或当前最佳方案

输出 JSON：{"intent": "<上述之一>", "reasoning": "一句话理由"}
"""

DECOMPOSE_PROMPT = """你是一个研究查询拆解器。给定一个研究问题和其意图，将其拆解为 3-5 个具体的子问题，当这些问题共同回答时，能全面覆盖原始查询。

每个子问题要具体、可通过网络/学术搜索回答。用中文输出 JSON：

{"sub_questions": ["子问题1", "子问题2", ...]}
"""


def _llm_call(system_prompt: str, user_msg: str) -> dict:
    """Make a single LLM call and return parsed JSON."""
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        timeout=60.0,
    )
    model = os.getenv("OPENAI_MODEL", "gpt-4o")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    return json.loads(response.choices[0].message.content or "{}")


def classify_intent(query: str) -> Intent:
    """Classify the research intent of a query."""
    try:
        result = _llm_call(INTENT_CLASSIFY_PROMPT, query)
        intent = result.get("intent", "exploration")
    except Exception:
        intent = "exploration"

    valid_intents = {"exploration", "comparison", "latest"}
    return intent if intent in valid_intents else "exploration"  # type: ignore


def decompose_query(query: str, intent: str) -> List[str]:
    """Decompose a research query into sub-questions."""
    try:
        result = _llm_call(
            DECOMPOSE_PROMPT,
            f"Query: {query}\nIntent: {intent}",
        )
        sub_qs = result.get("sub_questions", [query])
    except Exception:
        sub_qs = [query]

    if not sub_qs:
        sub_qs = [query]
    return sub_qs[:5]  # Cap at 5
