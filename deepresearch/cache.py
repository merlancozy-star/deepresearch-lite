"""SQLite-based query cache for the research pipeline.

Two-level caching:
  Level 1: query + intent → sub_questions
  Level 2: sub_question → citations (serialized as JSON)
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

from .schemas import Citation

CACHE_DIR = Path(__file__).parent.parent / ".cache"
CACHE_DB = CACHE_DIR / "research_cache.db"

# TTL defaults (seconds): 1 hour for sub_questions, 30 min for citations
TTL_SUB_QUESTIONS = int(os.getenv("CACHE_TTL_QUESTIONS", "3600"))
TTL_CITATIONS = int(os.getenv("CACHE_TTL_CITATIONS", "1800"))


def _ensure_db() -> sqlite3.Connection:
    """Create cache directory and tables if they don't exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CACHE_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache_entries (
            cache_key TEXT PRIMARY KEY,
            cache_type TEXT NOT NULL,
            data_json TEXT NOT NULL,
            created_at REAL NOT NULL,
            ttl_seconds INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_cache_type
        ON cache_entries(cache_type)
    """)
    conn.commit()
    return conn


def _make_key(prefix: str, text: str) -> str:
    """Hash a text into a cache key."""
    h = hashlib.md5(text.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}:{h}"


def _cleanup_expired(conn: sqlite3.Connection) -> None:
    """Remove expired cache entries."""
    now = time.time()
    conn.execute("DELETE FROM cache_entries WHERE created_at + ttl_seconds < ?", (now,))
    conn.commit()


# ── Level 1: Sub-questions cache ──────────────────────────────────────────

def get_cached_sub_questions(query: str, intent: str) -> Optional[List[str]]:
    """Retrieve cached sub_questions for a query+intent combination."""
    key = _make_key("sq", f"{query}|{intent}")
    conn = _ensure_db()
    try:
        row = conn.execute(
            "SELECT data_json, created_at, ttl_seconds FROM cache_entries WHERE cache_key = ?",
            (key,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    data_json, created_at, ttl = row
    if time.time() - created_at > ttl:
        return None

    return json.loads(data_json)


def cache_sub_questions(query: str, intent: str, sub_questions: List[str]) -> None:
    """Store sub_questions in cache."""
    key = _make_key("sq", f"{query}|{intent}")
    conn = _ensure_db()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO cache_entries VALUES (?, ?, ?, ?, ?)",
            (key, "sub_questions", json.dumps(sub_questions, ensure_ascii=False),
             time.time(), TTL_SUB_QUESTIONS),
        )
        conn.commit()
    finally:
        conn.close()


# ── Level 2: Citations cache ──────────────────────────────────────────────

def get_cached_citations(sub_question: str) -> Optional[List[Citation]]:
    """Retrieve cached citations for a sub-question."""
    key = _make_key("cit", sub_question)
    conn = _ensure_db()
    try:
        row = conn.execute(
            "SELECT data_json, created_at, ttl_seconds FROM cache_entries WHERE cache_key = ?",
            (key,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    data_json, created_at, ttl = row
    if time.time() - created_at > ttl:
        return None

    raw_list = json.loads(data_json)
    return [Citation(**data) for data in raw_list]


def cache_citations(sub_question: str, citations: List[Citation]) -> None:
    """Store citations in cache."""
    key = _make_key("cit", sub_question)
    raw_list = [c.model_dump() for c in citations]
    conn = _ensure_db()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO cache_entries VALUES (?, ?, ?, ?, ?)",
            (key, "citations", json.dumps(raw_list, ensure_ascii=False),
             time.time(), TTL_CITATIONS),
        )
        conn.commit()
    finally:
        conn.close()


# ── Maintenance ───────────────────────────────────────────────────────────

def clear_expired() -> int:
    """Remove all expired cache entries. Returns count of remaining entries."""
    conn = _ensure_db()
    try:
        _cleanup_expired(conn)
        row = conn.execute("SELECT COUNT(*) FROM cache_entries").fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def clear_all() -> None:
    """Wipe the entire cache."""
    conn = _ensure_db()
    try:
        conn.execute("DELETE FROM cache_entries")
        conn.commit()
    finally:
        conn.close()


def cache_stats() -> Dict[str, int]:
    """Return (total_entries, expired_entries) counts."""
    conn = _ensure_db()
    try:
        now = time.time()
        total = conn.execute("SELECT COUNT(*) FROM cache_entries").fetchone()[0]
        expired = conn.execute(
            "SELECT COUNT(*) FROM cache_entries WHERE created_at + ttl_seconds < ?",
            (now,),
        ).fetchone()[0]
        return {"total": total, "expired": expired}
    finally:
        conn.close()
