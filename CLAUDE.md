# DeepResearch-Lite — Design Document

> **About this file**: This `CLAUDE.md` is the project design document that Claude Code reads on each session start. It defines architecture, data structures, module contracts, and the development workflow. Treat it as the source of truth — code conflicting with this doc should be reconciled here first.

---

## 1. Project Overview

**Name**: DeepResearch-Lite
**Tagline**: A traceable deep-research agent for AI engineers — every claim backed by verifiable sources, NLI-verified.

**Problem statement**: Existing deep-research tools (OpenAI Deep Research, GPT-Researcher, OpenDeepResearch) provide citations but do not perform claim-evidence consistency verification. Users still have to manually check whether the cited evidence actually supports each claim. This is the gap DeepResearch-Lite addresses.

**MVP scope**:
- Backend pipeline runnable via CLI
- Citation enforcement at synthesis time (Pydantic strict schema)
- Independent NLI Verifier as a post-hoc check
- Two subagents: Web (Tavily) and arXiv
- Streamlit UI: input → report → expandable citations → verifier badges
- 5 tested demo queries
- Open-source repo with README and demo GIF

**Out of scope (tracked in Roadmap)**:
- Next.js frontend with rich interactions
- Full MCP Server packaging (interface reserved in graph design)
- Docker compose deployment
- GitHub / Blog / Reddit subagents
- Verifier evaluation with human-annotated ground truth

---

## 2. Design Principles

1. **Citations are first-class data, not strings**. Every claim is grounded by a `Citation` object with `source_id`, `chunk_id`, `char_span`, and a verifiable retrieval score. The frontend renders citations as expandable evidence, not opaque footnote numbers.

2. **Verification is decoupled from generation**. The Verifier runs after synthesis and only marks claims — it never edits the report. This avoids the over-correction failure mode where a feedback loop between verifier and generator destabilizes output.

3. **Strong schema enforcement at boundaries**. Pydantic `min_length=1` on `Claim.citations` means an uncited claim cannot exist as a valid object. ValidationErrors trigger retry with feedback to the LLM.

4. **Subagent independence**. Each subagent is a self-contained module with the same async interface (`search(query) -> List[Citation]`). They can be invoked individually for debugging or extended without touching orchestration logic.

5. **Composition over abstraction**. The project intentionally uses LangGraph for orchestration, Tavily for web search, the official `arxiv` library for paper retrieval, and Streamlit for UI — avoiding bespoke implementations where mature components exist.

---

## 3. Architecture

### 3.1 Data flow

```
User query
  └─> Orchestrator (LangGraph state graph)
        ├─ Intent classifier:  exploration | comparison | latest
        ├─ Query decomposer:   3-5 sub-questions
        └─ Subagent dispatch
              │
              ├─> Web Subagent     (Tavily)      ┐
              └─> arXiv Subagent   (arxiv-py)    ┘  asyncio.gather
                    │
                    └─> per-subagent loop:
                         search → fetch → chunk (with char_span) → extract
                    │
                    └─> List[Citation]
              │
        Citation pool: RRF fusion + dedup by (source_id, char_span)
              │
  └─> Synthesizer
        ├─ Pydantic-validated structured output
        ├─ Hard constraint: every claim has ≥1 evidence
        └─ On ValidationError → retry with error feedback (max 3)
              │
  └─> Verifier (independent LLM instance)
        ├─ For each claim: NLI prompt → entailed | contradicted | neutral
        └─ Annotates claim with label + score + reasoning; never edits text
              │
        └─> Output: Markdown report + Claim list + Verifier summary

# Note: graph nodes are designed to be invocable in isolation, leaving an
# interface seam for exposing them via MCP Server in a future phase.
```

### 3.2 Core data structures

```python
# deepresearch/schemas.py
from typing import Literal, List, Tuple
from pydantic import BaseModel, Field

class Citation(BaseModel):
    source_id: str = Field(..., description="Namespaced ID, e.g. arxiv:2310.06825")
    source_title: str
    source_url: str
    chunk_id: str
    text: str = Field(..., description="Original chunk text, surfaced in the UI")
    char_span: Tuple[int, int] = Field(..., description="Character offsets [start, end)")
    score: float = Field(..., ge=0, le=1)

class Claim(BaseModel):
    text: str
    citations: List[Citation] = Field(..., min_length=1)  # hard constraint
    verifier_label: Literal["entailed", "contradicted", "neutral", "unchecked"] = "unchecked"
    verifier_score: float = Field(default=0.0, ge=0, le=1)
    verifier_reasoning: str = ""

class ResearchReport(BaseModel):
    query: str
    intent: Literal["exploration", "comparison", "latest"]
    claims: List[Claim]
    markdown: str
    verifier_summary: dict = Field(default_factory=dict)
    cost_usd: float = 0.0
    elapsed_seconds: float = 0.0
```

`source_id` uses a `<source>:<id>` namespace (`arxiv:`, `web:`, future `github:`, `hn:`) to keep IDs unique and route-aware.

`char_span` lets the UI highlight the exact slice of the source rather than the whole document.

### 3.3 Citation enforcement (Layer 1)

The Synthesizer must produce a `ResearchReport` whose every `Claim` has at least one `Citation`. This is enforced by Pydantic's `min_length=1` validator, not just by prompt wording. When the LLM omits citations, Pydantic raises `ValidationError`, and the synthesizer retries (up to 3 times) by feeding the structured error back into the next prompt. Prompt-only enforcement is unreliable; schema enforcement is binding.

### 3.4 NLI Verifier (Layer 2)

For each claim, the Verifier runs an independent LLM instance with this NLI prompt structure:

```
You are a strict fact-checker. Given a Claim and its Evidence, decide whether
the Evidence entails the Claim:

Claim: {claim_text}
Evidence:
{evidence_text}

Output JSON:
{
  "label": "entailed" | "contradicted" | "neutral",
  "score": float in [0, 1],
  "reasoning": "1-2 sentences"
}

Rules: judge only whether Evidence supports Claim; do not use outside knowledge.
```

Design choices:
- **Independent client** from the synthesizer (avoids same-context bias)
- **Concurrent** via `asyncio.gather` with semaphore=5
- **Annotation only** — Verifier never edits the report; it only attaches labels
- **Full coverage in MVP** — all claims verified (~10–20 per report). Sampling is deferred to a later phase since current per-report cost is acceptable.

The verifier summary is written to the bottom of the report:

```
Verification summary: 15 claims total
├─ Entailed:      13 (87%)
├─ Neutral:        1 (7%, highlighted yellow)
└─ Contradicted:   1 (7%, highlighted red, claim #8)
Verification cost: $0.06 | Duration: 23s
```

### 3.5 Why post-hoc, not online feedback

An earlier project of mine attempted to feed Verifier signals back into a Planner during generation. Over multiple iterations this proved to over-correct: the planner would retract reasonable claims because the verifier signal was noisy at the margin. DeepResearch-Lite intentionally takes the opposite design — the Verifier sits outside the generation path. Its outputs are user-facing flags, not training signal. This trades a small amount of recall (we can't fix bad claims, only flag them) for stability and explainability.

---

## 4. Module layout

```
deepresearch-lite/
├── CLAUDE.md
├── README.md
├── LICENSE                      # MIT
├── requirements.txt
├── .env.example
├── .gitignore
│
├── deepresearch/
│   ├── __init__.py
│   ├── schemas.py               # Citation / Claim / ResearchReport
│   ├── citation.py              # RRF fusion + dedup helpers
│   ├── graph.py                 # LangGraph state graph
│   ├── orchestrator.py          # Intent classifier + query decomposer
│   ├── subagents/
│   │   ├── __init__.py
│   │   ├── base.py              # Subagent ABC + chunk/char_span helpers
│   │   ├── web.py               # Tavily
│   │   └── arxiv.py             # arxiv-py
│   ├── synthesizer.py
│   ├── verifier.py
│   ├── prompts/
│   │   ├── orchestrator.txt
│   │   ├── synthesizer.txt
│   │   └── verifier.txt
│   └── cli.py                   # python -m deepresearch.cli "your query"
│
├── app.py                       # Streamlit entry
├── tests/
│   ├── test_schemas.py
│   ├── test_citation_rrf.py
│   └── test_synthesizer_strict.py
└── docs/
    ├── architecture.png
    └── demo.gif
```

---

## 5. Development workflow

This project was built end-to-end with Claude Code using a design-document-driven workflow:

1. **Design first**: This CLAUDE.md was authored before any code. It defines schemas, module boundaries, and contracts. Claude Code reads it on every session start, so the design is part of the working context — not a separate doc that drifts.

2. **Milestone decomposition**: The work was split into small milestones (scaffold → schemas → subagents → synthesizer → verifier → graph → UI → docs). Each milestone had a written acceptance criterion before implementation started.

3. **Plan-before-code**: Each session began by asking Claude Code to produce a step-by-step plan and a list of files to be touched, before any edits. This catches misinterpretations of the design doc early.

4. **Tests at boundaries**: Schema constraints, RRF math, and synthesizer retry logic are covered by unit tests. End-to-end testing is done via the demo query suite.

5. **Composition over invention**: LangGraph for state-graph orchestration, Tavily for web retrieval, the official `arxiv` library for paper search, and Streamlit for UI. Custom code is reserved for the parts that are actually project-specific: citation data structures, RRF fusion, the synthesizer retry loop, and the NLI verifier.

---

## 6. Operational notes

| Concern | Approach |
|---|---|
| External API failure | tenacity retry with exponential backoff (3 attempts) |
| arXiv rate limiting | Sleep between requests; cache results to `reports/` |
| Synthesizer fails to produce valid output | Hard cap at 3 retries; report flags "insufficient evidence" rather than looping |
| Verifier false positives on contradiction | Tolerated in MVP; flagged in Roadmap as needing human-annotated eval set |
| Streamlit streaming hiccups | Fallback to non-streaming render |
| Total cost per query | ~$0.05–0.10 with current pipeline; profiled in `reports/` JSON output |

---

## 7. Roadmap

**Phase 2 (1–2 weeks)**
- GitHub and Blog subagents
- Verifier sampling (high-confidence 30%, low-confidence 100%)
- Add `reproduction` intent type
- Next.js frontend with citation popovers

**Phase 3 (3–4 weeks)**
- MCP Server: expose subagents and synthesizer as individual tools
- Docker compose deployment
- Verifier P/R evaluation on 30–50 human-annotated claims
- Prompt caching for shared subagent system prompts

**Phase 4**
- Long-running research with checkpoint resume
- 3-minute product demo
- Technical write-up

---

## 8. References

The post-hoc decoupled verifier design is informed by prior work on agentic RAG with online verifier feedback, where over-correction was empirically observed. See the project's own internal evaluation log; published references on the broader pattern include retrieval-augmented generation faithfulness metrics (RAGAS) and the multi-agent research system architecture published by Anthropic in 2025.
