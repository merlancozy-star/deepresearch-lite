"""Mock subagent for demo/testing when external APIs are unavailable.

Provides hardcoded citations for known demo queries.
"""
from __future__ import annotations

from typing import List

from deepresearch.schemas import Citation

from .base import Subagent

# Hardcoded demo citations for "vLLM vs SGLang" query
VLLM_VS_SGLANG_CITATIONS = [
    Citation(
        source_id="arxiv:2306.02524",
        source_title="vLLM: Easy, Fast, and Cheap LLM Serving with PagedAttention",
        source_url="https://arxiv.org/abs/2306.02524",
        chunk_id="chunk-0",
        text="vLLM proposes PagedAttention, an attention algorithm inspired by virtual memory paging in operating systems. This allows vLLM to manage KV cache memory more efficiently, achieving near-zero memory waste and enabling higher throughput.",
        char_span=(0, 230),
        score=0.95,
    ),
    Citation(
        source_id="arxiv:2306.02524",
        source_title="vLLM: Easy, Fast, and Cheap LLM Serving with PagedAttention",
        source_url="https://arxiv.org/abs/2306.02524",
        chunk_id="chunk-1",
        text="vLLM achieves 2-4x higher throughput than HuggingFace Transformers and up to 24x higher throughput than state-of-the-art systems like Orca and FasterTransformer.",
        char_span=(230, 400),
        score=0.9,
    ),
    Citation(
        source_id="arxiv:2312.07104",
        source_title="SGLang: Efficient Execution of Structured Language Model Programs",
        source_url="https://arxiv.org/abs/2312.07104",
        chunk_id="chunk-0",
        text="SGLang introduces RadixAttention for efficient prefix sharing and a structured generation language that enables complex prompting patterns like chain-of-thought, self-consistency, and tree-of-thought.",
        char_span=(0, 210),
        score=0.95,
    ),
    Citation(
        source_id="arxiv:2312.07104",
        source_title="SGLang: Efficient Execution of Structured Language Model Programs",
        source_url="https://arxiv.org/abs/2312.07104",
        chunk_id="chunk-1",
        text="SGLang achieves up to 6.4x higher throughput compared to vLLM on workloads with shared prefixes, and up to 5x higher throughput on various standard benchmarks including MMLU and HumanEval.",
        char_span=(210, 400),
        score=0.9,
    ),
    Citation(
        source_id="arxiv:2401.12345",
        source_title="A Comparative Analysis of LLM Serving Systems: vLLM, SGLang, and TensorRT-LLM",
        source_url="https://arxiv.org/abs/2401.12345",
        chunk_id="chunk-0",
        text="While vLLM focuses on memory efficiency through PagedAttention, SGLang focuses on programmability and structured generation. The two systems represent complementary approaches to LLM serving optimization.",
        char_span=(0, 200),
        score=0.85,
    ),
    Citation(
        source_id="arxiv:2401.12345",
        source_title="A Comparative Analysis of LLM Serving Systems: vLLM, SGLang, and TensorRT-LLM",
        source_url="https://arxiv.org/abs/2401.12345",
        chunk_id="chunk-1",
        text="vLLM supports a wide range of HuggingFace models out of the box and has strong community adoption. SGLang offers superior performance on structured generation tasks but has a steeper learning curve for custom model integration.",
        char_span=(200, 420),
        score=0.85,
    ),
]

# Hardcoded demo citations for "Mamba" query
MAMBA_CITATIONS = [
    Citation(
        source_id="arxiv:2312.00752",
        source_title="Mamba: Linear-Time Sequence Modeling with Selective State Spaces",
        source_url="https://arxiv.org/abs/2312.00752",
        chunk_id="chunk-0",
        text="Mamba introduces a selection mechanism into state space models, allowing them to selectively propagate or forget information along the sequence dimension based on the input content.",
        char_span=(0, 180),
        score=0.95,
    ),
    Citation(
        source_id="arxiv:2312.00752",
        source_title="Mamba: Linear-Time Sequence Modeling with Selective State Spaces",
        source_url="https://arxiv.org/abs/2312.00752",
        chunk_id="chunk-1",
        text="Mamba achieves 5x higher throughput than Transformers of similar size and matches or exceeds the performance of Transformers on language modeling, audio, and genomics tasks.",
        char_span=(180, 360),
        score=0.9,
    ),
    Citation(
        source_id="arxiv:2402.01032",
        source_title="Mamba-2: Refining Selective State Space Models",
        source_url="https://arxiv.org/abs/2402.01032",
        chunk_id="chunk-0",
        text="Mamba-2 introduces architectural improvements to the original Mamba design, including parallel scan algorithms that improve training efficiency and a more flexible gating mechanism.",
        char_span=(0, 190),
        score=0.95,
    ),
    Citation(
        source_id="arxiv:2405.04519",
        source_title="Vision Mamba: Efficient Visual Representation Learning with State Space Models",
        source_url="https://arxiv.org/abs/2405.04519",
        chunk_id="chunk-0",
        text="Vision Mamba (ViM) adapts the Mamba architecture for computer vision tasks, achieving competitive accuracy with ViT while requiring sub-quadratic computational complexity.",
        char_span=(0, 170),
        score=0.85,
    ),
]

DEMO_CITATIONS = {
    "vllm": VLLM_VS_SGLANG_CITATIONS,
    "sglang": VLLM_VS_SGLANG_CITATIONS,
    "mamba": MAMBA_CITATIONS,
    "state space": MAMBA_CITATIONS,
}


class MockSubagent(Subagent):
    """Returns hardcoded citations for known demo queries."""

    def __init__(self, namespace: str = "mock"):
        super().__init__("mock")
        self.namespace = namespace

    async def search(self, query: str) -> List[Citation]:
        query_lower = query.lower()
        for keyword, citations in DEMO_CITATIONS.items():
            if keyword in query_lower:
                # Copy and update source_id namespace
                result = []
                for c in citations:
                    new_c = c.model_copy()
                    new_c.source_id = f"{self.namespace}:{c.source_id.split(':')[-1]}"
                    result.append(new_c)
                return result
        return []
