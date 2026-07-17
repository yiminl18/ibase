from ibase.llm.engine import LLMEngine, _extract_json


def test_extract_plain_json():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_fenced_json():
    text = 'Here you go:\n```json\n{"summary": "hi", "topics": ["x"]}\n```'
    assert _extract_json(text) == {"summary": "hi", "topics": ["x"]}


def test_extract_embedded_json():
    assert _extract_json('blah {"ids": ["a", "b"]} trailing') == {"ids": ["a", "b"]}


def test_extract_junk_returns_none():
    assert _extract_json("no json here") is None


def test_off_backend_is_unavailable():
    eng = LLMEngine(backend="off")
    assert eng.available() is False
    assert eng.summarize("some text") == {"summary": "", "topics": []}
    assert eng.semantic_filter("q", [{"id": "1"}]) is None


def test_summarize_empty_text_short_circuits():
    eng = LLMEngine(backend="cli")
    assert eng.summarize("") == {"summary": "", "topics": []}
