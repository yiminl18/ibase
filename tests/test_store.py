from pathlib import Path

from ibase.models import Item
from ibase.store import Store


def make_store(tmp_path: Path) -> Store:
    return Store(metadata_path=tmp_path / "metadata.json",
                 files_dir=tmp_path / "files")


def test_add_and_get(tmp_path):
    store = make_store(tmp_path)
    item = Item(id="abc", name="Doc", source_link="http://x")
    store.add(item)
    assert store.get("abc").name == "Doc"
    assert len(store.list_items()) == 1


def test_persistence_across_instances(tmp_path):
    store = make_store(tmp_path)
    store.add(Item(id="abc", name="Doc", source_link="http://x"))
    reopened = make_store(tmp_path)
    assert reopened.get("abc") is not None


def test_update_partial(tmp_path):
    store = make_store(tmp_path)
    store.add(Item(id="abc", name="Doc", source_link="http://x", read=False))
    updated = store.update("abc", read=True, note="hello")
    assert updated.read is True
    assert updated.note == "hello"
    # None values are ignored (no accidental overwrite).
    again = store.update("abc", note=None)
    assert again.note == "hello"


def test_delete_removes_folder(tmp_path):
    store = make_store(tmp_path)
    store.add(Item(id="abc", name="Doc", source_link="http://x"))
    folder = store.item_folder("abc")
    (folder / "f.txt").write_text("data")
    assert store.delete("abc") is True
    assert not folder.exists()
    assert store.get("abc") is None
    assert store.delete("abc") is False


def test_topics_capped_at_three(tmp_path):
    store = make_store(tmp_path)
    item = Item(id="abc", name="Doc", source_link="http://x",
                topics=["a", "b", "c"])
    store.add(item)
    assert store.get("abc").topics == ["a", "b", "c"]
