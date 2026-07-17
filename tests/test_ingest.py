from pathlib import Path

from ibase.ingest import extract
from ibase.ingest.digest import _merge_topics, digest, digest_upload
from ibase.llm.engine import LLMEngine
from ibase.store import Store


def make_store(tmp_path: Path) -> Store:
    return Store(metadata_path=tmp_path / "metadata.json",
                 files_dir=tmp_path / "files")


OFF = LLMEngine(backend="off")


def test_extract_html(tmp_path):
    f = tmp_path / "page.html"
    f.write_text("<html><head><title>Hi</title></head>"
                 "<body><script>x=1</script><p>Hello world</p></body></html>")
    ex = extract.extract_html(f)
    assert ex.title == "Hi"
    assert "Hello world" in ex.text
    assert "x=1" not in ex.text


def test_digest_local_text_file(tmp_path):
    store = make_store(tmp_path)
    doc = tmp_path / "note.txt"
    doc.write_text("Some content about databases.")
    item = digest(str(doc), store, llm=OFF, note="my note", topics=["db"])
    assert item.format == "text"
    assert item.fetch_status == "ok"
    assert item.note == "my note"
    assert item.topics == ["db"]
    assert item.content_text_path is not None
    # Stored and retrievable.
    assert store.get(item.id) is not None


def test_digest_missing_local_file(tmp_path):
    store = make_store(tmp_path)
    item = digest(str(tmp_path / "nope.pdf"), store, llm=OFF)
    assert item.fetch_status == "failed"
    assert item.local_path is None


def test_digest_upload_bytes(tmp_path):
    store = make_store(tmp_path)
    item = digest_upload(b"Content about search engines.", "doc.txt", store,
                         llm=OFF, note="dropped")
    assert item.format == "text"
    assert item.fetch_status == "ok"
    assert item.name == "doc"
    assert item.note == "dropped"
    assert item.content_text_path is not None
    assert store.get(item.id) is not None


def test_merge_topics_dedupes_and_caps():
    assert _merge_topics(["a", "b"], ["b", "c", "d"]) == ["a", "b", "c"]
    assert _merge_topics([], []) == []
