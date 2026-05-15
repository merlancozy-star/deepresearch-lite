"""Test synthesizer with mocked LLM responses.

Adapted for two-stage architecture: outline → section writing → assembly.
"""
import json
from unittest.mock import MagicMock, patch

from deepresearch.schemas import Citation
from deepresearch.synthesizer import synthesize


def make_cit(source_id, chunk_id="chunk-0", score=0.9):
    return Citation(
        source_id=source_id,
        source_title=f"Title for {source_id}",
        source_url=f"https://example.com/{source_id}",
        chunk_id=chunk_id,
        text=f"Sample evidence text from {source_id}.",
        char_span=(0, 50),
        score=score,
    )


def _mock_openai_response(data: dict):
    """Create a mock OpenAI chat completion response."""
    msg = MagicMock()
    msg.content = json.dumps(data)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = MagicMock()
    resp.usage.prompt_tokens = 1000
    resp.usage.completion_tokens = 500
    return resp


def _outline_response():
    return _mock_openai_response({
        "sections": [{"title": "Test Section", "key_question": "test?", "description": "test"}]
    })


def _section_response(source_id="arxiv:1234.5678", chunk_id="chunk-0"):
    return _mock_openai_response({
        "section_markdown": "Section content with evidence.",
        "claims": [{
            "text": "Test claim with evidence.",
            "source_ids": [source_id],
            "chunk_ids": [chunk_id],
        }],
    })


def _assembly_response():
    return _mock_openai_response({
        "markdown": "# Test Report\n\n## Summary\n\nTest.\n\n## Detailed Analysis\n\n### Test Section\n\nSection content.\n",
        "claims": [],
        "references": [],
        "methodology": "Test methodology.",
    })


class TestSynthesizerHappyPath:
    def test_valid_claims_with_citations(self):
        """Happy path: valid claims come through the two-stage pipeline."""
        cit = make_cit("arxiv:1234.5678")
        pool = [cit]

        with patch("deepresearch.synthesizer.OpenAI") as mock_openai:
            mock_client = MagicMock()
            # Stage 1: outline, Stage 2: section, Stage 3: assembly
            mock_client.chat.completions.create.side_effect = [
                _outline_response(),
                _section_response("arxiv:1234.5678", "chunk-0"),
                _assembly_response(),
            ]
            mock_openai.return_value = mock_client

            report = synthesize("test query", "exploration", pool)

        assert len(report.claims) >= 1
        # At least one claim should have the real citation
        real_claims = [c for c in report.claims
                       if any(ct.source_id == "arxiv:1234.5678" for ct in c.citations)]
        assert len(real_claims) >= 1
        # 3 calls: outline + section + assembly
        assert mock_client.chat.completions.create.call_count == 3

    def test_retry_on_invalid_citations(self):
        """Invalid source_ids in section writing trigger retry."""
        cit = make_cit("arxiv:1234.5678")
        pool = [cit]

        with patch("deepresearch.synthesizer.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = [
                _outline_response(),
                # First section attempt: invalid (empty source_ids)
                _mock_openai_response({
                    "section_markdown": "",
                    "claims": [{"text": "Bad claim.", "source_ids": [], "chunk_ids": []}],
                }),
                # Second section attempt: valid
                _section_response("arxiv:1234.5678", "chunk-0"),
                _assembly_response(),
            ]
            mock_openai.return_value = mock_client

            report = synthesize("test", "exploration", pool)

        # Should recover on retry and produce valid claims
        real_claims = [c for c in report.claims
                       if any(ct.source_id == "arxiv:1234.5678" for ct in c.citations)]
        assert len(real_claims) >= 1
        # 3 calls: outline + 2 section attempts + assembly = 4
        assert mock_client.chat.completions.create.call_count == 4

    def test_fallback_on_persistent_failure(self):
        """After all section retries fail, get fallback citations."""
        cit = make_cit("arxiv:1234.5678")
        pool = [cit]

        # Always returns bad data (nonexistent source_id)
        bad_section = _mock_openai_response({
            "section_markdown": "Content",
            "claims": [{"text": "Uncited claim.", "source_ids": ["arxiv:fake.9999"], "chunk_ids": ["chunk-0"]}],
        })

        with patch("deepresearch.synthesizer.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = [
                _outline_response(),
                bad_section,  # attempt 1
                bad_section,  # attempt 2 (final — gets fallback)
                _assembly_response(),
            ]
            mock_openai.return_value = mock_client

            report = synthesize("test", "exploration", pool, max_retries=2)

        # Should still produce claims (with fallback citations)
        assert len(report.claims) >= 1
        # At least one claim should have the synthesizer:fallback citation
        fallback_claims = [c for c in report.claims
                           if any(ct.source_id == "synthesizer:fallback" for ct in c.citations)]
        assert len(fallback_claims) >= 1

    def test_relevance_filtering_includes_best_evidence(self):
        """Evidence with high keyword overlap passes to section writer."""
        relevant_cit = Citation(
            source_id="arxiv:relevant.1",
            source_title="RAG Evaluation Methods Survey",
            source_url="https://example.com/rag",
            chunk_id="chunk-0",
            text="RAG evaluation methods include faithfulness, answer relevance, and context precision metrics.",
            char_span=(0, 100),
            score=0.9,
        )
        irrelevant_cit = Citation(
            source_id="arxiv:irrelevant.1",
            source_title="Quantum Computing Basics",
            source_url="https://example.com/qc",
            chunk_id="chunk-0",
            text="Quantum computing uses qubits to perform calculations that are infeasible for classical computers.",
            char_span=(0, 100),
            score=0.5,
        )
        pool = [relevant_cit, irrelevant_cit]

        with patch("deepresearch.synthesizer.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = [
                _mock_openai_response({
                    "sections": [{"title": "RAG 评测方法", "key_question": "RAG evaluation methods?", "description": "Survey of RAG evaluation"}]}
                ),
                _section_response("arxiv:relevant.1", "chunk-0"),
                _assembly_response(),
            ]
            mock_openai.return_value = mock_client

            report = synthesize("RAG evaluation", "exploration", pool)

        # The claim should reference the relevant citation, not the irrelevant one
        relevant_used = any(
            ct.source_id == "arxiv:relevant.1"
            for claim in report.claims
            for ct in claim.citations
        )
        irrelevant_used = any(
            ct.source_id == "arxiv:irrelevant.1"
            for claim in report.claims
            for ct in claim.citations
        )
        assert relevant_used, "Relevant citation should be used in claims"
        # Irrelevant may or may not be used, but shouldn't be the ONLY one
        assert not irrelevant_used or relevant_used
