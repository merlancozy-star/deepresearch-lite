"""Abstract base class for subagents and text chunking utilities."""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from typing import List

from deepresearch.schemas import Citation


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
    """Split text into overlapping chunks for citation extraction.

    Uses a sliding window: each chunk is chunk_size chars,
    overlapping with the previous chunk by overlap chars.
    """
    if not text.strip():
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def make_source_id(prefix: str, key: str) -> str:
    """Create a normalized source_id like 'web:<hash>' or 'arxiv:<id>'."""
    if prefix == "web":
        h = hashlib.md5(key.encode()).hexdigest()[:8]
        return f"web:{h}"
    return f"{prefix}:{key}"


class Subagent(ABC):
    """Base class for all research subagents."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def search(self, query: str) -> List[Citation]:
        """Execute a search and return ranked citations."""
        ...
