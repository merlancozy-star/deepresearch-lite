"""Core data structures for DeepResearch-Lite.

Citation, Claim, and ResearchReport — the backbone of the traceable research pipeline.
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


class Citation(BaseModel):
    source_id: str = Field(..., description="Normalized source ID, e.g. arxiv:2310.06825")
    source_title: str
    source_url: str
    chunk_id: str
    text: str = Field(..., description="Original text paragraph for frontend expand display")
    char_span: Tuple[int, int] = Field(..., description="Character offset [start, end)")
    score: float = Field(..., ge=0, le=1)


class Claim(BaseModel):
    text: str
    citations: List[Citation] = Field(..., min_length=1)
    verifier_label: Literal["entailed", "contradicted", "neutral", "unchecked"] = "unchecked"
    verifier_score: float = Field(default=0.0, ge=0, le=1)
    verifier_reasoning: str = ""


class ResearchReport(BaseModel):
    query: str
    intent: Literal["exploration", "comparison", "latest"]
    claims: List[Claim]
    markdown: str
    verifier_summary: Dict = Field(default_factory=dict)
    cost_usd: float = 0.0
    elapsed_seconds: float = 0.0
