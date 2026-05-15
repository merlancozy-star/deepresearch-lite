"""Citation pooling: Reciprocal Rank Fusion (RRF) + deduplication."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from .schemas import Citation


def deduplicate(citations: List[Citation]) -> List[Citation]:
    """Remove duplicate citations by source_id + char_span.

    When two citations share the same source_id and overlapping char_span,
    keep the one with the higher score.
    """
    if not citations:
        return []

    groups: Dict[str, Dict[str, Citation]] = defaultdict(dict)
    for c in citations:
        span_key = f"{c.char_span[0]}-{c.char_span[1]}"
        existing = groups[c.source_id].get(span_key)
        if existing is None or c.score > existing.score:
            groups[c.source_id][span_key] = c

    result = []
    for source_groups in groups.values():
        result.extend(source_groups.values())

    result.sort(key=lambda c: c.score, reverse=True)
    return result


def rrf_fusion(citations_lists: List[List[Citation]], k: int = 60) -> List[Citation]:
    """Reciprocal Rank Fusion over multiple citation lists.

    For each subagent's ranked list, every citation gets RRF_score = 1 / (k + rank).
    Scores are summed across lists and the fused list is returned sorted by total score.

    Args:
        citations_lists: One list of ranked citations per subagent.
        k: RRF constant (default 60, standard value).

    Returns:
        Fused and deduplicated citation list, sorted by RRF score descending.
    """
    if not citations_lists:
        return []

    # Track the best score each citation gets from any list
    rrf_scores: Dict[str, float] = {}
    citation_map: Dict[str, Citation] = {}

    for ranked_list in citations_lists:
        for rank, citation in enumerate(ranked_list, start=1):
            rrf_score = 1.0 / (k + rank)
            # Key by source_id + chunk_id for fusion
            key = f"{citation.source_id}::{citation.chunk_id}"
            if key not in rrf_scores or rrf_score > rrf_scores[key]:
                rrf_scores[key] = rrf_score
                citation_map[key] = citation

    # Sort by RRF score descending, assign the score back to citation
    fused = []
    for key, score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
        cit = citation_map[key]
        fused.append(cit)

    return fused
