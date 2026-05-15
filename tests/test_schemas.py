"""Test Citation/Claim/ResearchReport schema constraints."""
import pytest
from pydantic import ValidationError

from deepresearch.schemas import Citation, Claim, ResearchReport


def make_citation(source_id="test:001", score=0.9):
    return Citation(
        source_id=source_id,
        source_title="Test Paper",
        source_url="https://example.com",
        chunk_id="chunk-1",
        text="This is a test paragraph.",
        char_span=(0, 27),
        score=score,
    )


class TestCitation:
    def test_valid_citation(self):
        c = make_citation()
        assert c.source_id == "test:001"
        assert c.score == 0.9

    def test_score_bounds(self):
        with pytest.raises(ValidationError):
            make_citation(score=1.5)
        with pytest.raises(ValidationError):
            make_citation(score=-0.1)


class TestClaim:
    def test_claim_requires_at_least_one_citation(self):
        with pytest.raises(ValidationError):
            Claim(text="A claim with no evidence.", citations=[])

    def test_valid_claim(self):
        c = make_citation()
        claim = Claim(text="Test claim.", citations=[c])
        assert claim.verifier_label == "unchecked"
        assert len(claim.citations) == 1

    def test_claim_defaults(self):
        c = make_citation()
        claim = Claim(text="Default test.", citations=[c])
        assert claim.verifier_label == "unchecked"
        assert claim.verifier_score == 0.0
        assert claim.verifier_reasoning == ""


class TestResearchReport:
    def test_minimal_report(self):
        c = make_citation()
        claim = Claim(text="Claim 1.", citations=[c])
        report = ResearchReport(
            query="test query",
            intent="exploration",
            claims=[claim],
            markdown="# Test Report",
        )
        assert len(report.claims) == 1
        assert report.verifier_summary == {}
        assert report.cost_usd == 0.0

    def test_report_intent_validation(self):
        c = make_citation()
        claim = Claim(text="C", citations=[c])
        with pytest.raises(ValidationError):
            ResearchReport(
                query="q",
                intent="invalid_intent",
                claims=[claim],
                markdown="md",
            )
