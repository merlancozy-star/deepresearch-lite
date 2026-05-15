"""Test RRF fusion and deduplication logic."""
from deepresearch.citation import deduplicate, rrf_fusion
from deepresearch.schemas import Citation


def make_cit(source_id, chunk_id, score=0.9, char_span=(0, 100)):
    return Citation(
        source_id=source_id,
        source_title=f"Title {source_id}",
        source_url=f"https://example.com/{source_id}",
        chunk_id=chunk_id,
        text="Sample text for testing.",
        char_span=char_span,
        score=score,
    )


class TestDeduplicate:
    def test_empty_list(self):
        assert deduplicate([]) == []

    def test_no_duplicates(self):
        c1 = make_cit("src:1", "chunk-a")
        c2 = make_cit("src:2", "chunk-b")
        result = deduplicate([c1, c2])
        assert len(result) == 2

    def test_exact_duplicate_same_source_id_and_span(self):
        c1 = make_cit("src:1", "chunk-a", score=0.5, char_span=(0, 100))
        c2 = make_cit("src:1", "chunk-a", score=0.9, char_span=(0, 100))
        result = deduplicate([c1, c2])
        assert len(result) == 1
        assert result[0].score == 0.9  # Higher score kept

    def test_same_source_different_span(self):
        c1 = make_cit("src:1", "chunk-a", char_span=(0, 100))
        c2 = make_cit("src:1", "chunk-a", char_span=(50, 150))
        result = deduplicate([c1, c2])
        assert len(result) == 2

    def test_different_source_same_span(self):
        c1 = make_cit("src:1", "chunk-a", char_span=(0, 100))
        c2 = make_cit("src:2", "chunk-a", char_span=(0, 100))
        result = deduplicate([c1, c2])
        assert len(result) == 2


class TestRRFFusion:
    def test_empty_input(self):
        assert rrf_fusion([]) == []

    def test_single_list(self):
        c1 = make_cit("src:1", "chunk-a")
        c2 = make_cit("src:2", "chunk-b")
        result = rrf_fusion([[c1, c2]])
        assert len(result) == 2
        # First citation (rank 1) should have higher RRF score
        assert result[0].source_id == "src:1"

    def test_fusion_combines_lists(self):
        c1 = make_cit("arxiv:A", "c1")
        c2 = make_cit("arxiv:B", "c2")
        c3 = make_cit("web:X", "c3")
        c4 = make_cit("web:Y", "c4")
        # c1 and c4 appear in both lists, c2 only in first, c3 only in second
        result = rrf_fusion([[c1, c2, c4], [c3, c4, c1]])
        # All unique by source_id::chunk_id should appear
        assert len(result) == 4

    def test_fusion_deduplicates_by_source_and_chunk(self):
        c1 = make_cit("arxiv:A", "chunk-1")
        c1_dup = make_cit("arxiv:A", "chunk-1")  # Same key
        result = rrf_fusion([[c1], [c1_dup]])
        assert len(result) == 1

    def test_rrf_score_ordering(self):
        """Paper ranked #1 in both lists should outrank paper ranked #2."""
        top = make_cit("top", "c1")
        mid = make_cit("mid", "c2")
        low = make_cit("low", "c3")
        result = rrf_fusion([[top, mid, low], [top, mid, low]])
        assert result[0].source_id == "top"
        assert result[1].source_id == "mid"
        assert result[2].source_id == "low"
