from ibase.models import Item
from ibase.query import filters, ranker
from ibase.query.pipeline import run_query


def items():
    return [
        Item(id="1", name="Alpha DB paper", source_link="x", read=False,
             topics=["db"], summary="about databases", inserted_at="2026-01-01T00:00:00Z",
             size_bytes=10),
        Item(id="2", name="Beta ML notes", source_link="x", read=True,
             topics=["ml"], summary="about models", inserted_at="2026-02-01T00:00:00Z",
             size_bytes=30),
        Item(id="3", name="Gamma", source_link="x", read=False,
             topics=["db", "ml"], summary="mixed", inserted_at="2026-03-01T00:00:00Z",
             size_bytes=20),
    ]


def test_rank_by_date_desc():
    ranked = ranker.rank(items(), sort="inserted_at", order="desc")
    assert [i.id for i in ranked] == ["3", "2", "1"]


def test_rank_by_size_asc():
    ranked = ranker.rank(items(), sort="size_bytes", order="asc")
    assert [i.id for i in ranked] == ["1", "3", "2"]


def test_rank_invalid_field_falls_back():
    ranked = ranker.rank(items(), sort="bogus", order="desc")
    assert [i.id for i in ranked] == ["3", "2", "1"]


def test_filter_read_and_topic():
    assert [i.id for i in filters.filter_structured(items(), read=False)] == ["1", "3"]
    assert [i.id for i in filters.filter_structured(items(), topic="ml")] == ["2", "3"]


def test_local_text_match():
    assert [i.id for i in filters.local_text_match(items(), "databases")] == ["1"]


def test_pipeline_local_query_no_llm():
    # 2-word query stays local under "auto"; no LLM needed.
    result = run_query(items(), q="ML notes", q_mode="local", sort="inserted_at",
                       order="asc")
    assert [i.id for i in result] == ["2"]


def test_natural_language_heuristic():
    assert filters.looks_natural_language("papers about vector databases") is True
    assert filters.looks_natural_language("db") is False
