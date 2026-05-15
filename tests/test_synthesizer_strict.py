"""Test synthesizer with mocked LLM responses."""
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


class TestSynthesizerHappyPath:
    def test_valid_claims_with_citations(self):
        cit = make_cit("arxiv:1234.5678")
        pool = [cit]
        valid_data = {
            "markdown": "# Test Report\n\nThis is a test [^arxiv:1234.5678].",
            "claims": [
                {
                    "text": "Test claim with evidence.",
                    "source_ids": ["arxiv:1234.5678"],
                    "chunk_ids": ["chunk-0"],
                }
            ],
        }

        with patch("deepresearch.synthesizer.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _mock_openai_response(valid_data)
            mock_openai.return_value = mock_client

            report = synthesize("test query", "exploration", pool)

        assert len(report.claims) == 1
        assert len(report.claims[0].citations) == 1
        assert report.claims[0].citations[0].source_id == "arxiv:1234.5678"

    def test_no_citations_triggers_retry(self):
        cit = make_cit("arxiv:1234.5678")
        pool = [cit]

        # First response: claims without source_ids — should trigger retry
        bad_data = {
            "markdown": "Bad report",
            "claims": [{"text": "Claim with no evidence.", "source_ids": [], "chunk_ids": []}],
        }

        # Second response: valid claims
        good_data = {
            "markdown": "Good report",
            "claims": [
                {
                    "text": "Claim with evidence.",
                    "source_ids": ["arxiv:1234.5678"],
                    "chunk_ids": ["chunk-0"],
                }
            ],
        }

        with patch("deepresearch.synthesizer.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = [
                _mock_openai_response(bad_data),
                _mock_openai_response(good_data),
            ]
            mock_openai.return_value = mock_client

            report = synthesize("test", "exploration", pool)

        # Should have recovered on second attempt
        assert len(report.claims) == 1
        assert len(report.claims[0].citations) == 1
        # Should have been called twice (first failed, retry succeeded)
        assert mock_client.chat.completions.create.call_count == 2

    def test_max_retries_marks_uncited(self):
        cit = make_cit("arxiv:1234.5678")
        pool = [cit]

        bad_data = {
            "markdown": "Bad report",
            "claims": [{"text": "Uncited claim.", "source_ids": ["arxiv:9999.9999"], "chunk_ids": ["chunk-0"]}],
        }

        with patch("deepresearch.synthesizer.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _mock_openai_response(bad_data)
            mock_openai.return_value = mock_client

            report = synthesize("test", "exploration", pool, max_retries=3)

        # After max retries, claims are marked [UNCITED]
        assert report.claims[0].text.startswith("[UNCITED]")

    def test_unknown_source_id_marks_invalid(self):
        cit = make_cit("arxiv:real.5678")
        pool = [cit]

        data = {
            "markdown": "Report",
            "claims": [
                {
                    "text": "Claim referencing nonexistent source.",
                    "source_ids": ["arxiv:fake.9999"],
                    "chunk_ids": ["chunk-0"],
                }
            ],
        }

        with patch("deepresearch.synthesizer.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _mock_openai_response(data)
            mock_openai.return_value = mock_client

            report = synthesize("test", "exploration", pool)

        # Should trigger retry since the source_id doesn't exist in the pool
        # On max retries, marks as uncited
        assert "[UNCITED]" in report.claims[0].text
