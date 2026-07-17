"""JSON-backed persistence for items.

The whole database is a single ``metadata.json`` file. It is small (hundreds to
low thousands of items) so we load it wholesale and rewrite atomically on every
mutation. A process-wide lock serializes writes.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import List, Optional

from . import config
from .models import Database, Item


class Store:
    """Load/save the metadata database and manage per-item file folders."""

    def __init__(self, metadata_path: Optional[Path] = None,
                 files_dir: Optional[Path] = None) -> None:
        self.metadata_path = metadata_path or config.METADATA_PATH
        self.files_dir = files_dir or config.FILES_DIR
        self._lock = threading.RLock()
        self.files_dir.mkdir(parents=True, exist_ok=True)

    # ---- low-level load/save -------------------------------------------------
    def _load(self) -> Database:
        if not self.metadata_path.exists():
            return Database()
        raw = self.metadata_path.read_text(encoding="utf-8")
        if not raw.strip():
            return Database()
        return Database.model_validate_json(raw)

    def _save(self, db: Database) -> None:
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        payload = db.model_dump_json(indent=2)
        # Atomic replace: write to a temp file in the same dir, then os.replace.
        fd, tmp = tempfile.mkstemp(
            dir=str(self.metadata_path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, self.metadata_path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    # ---- public API ----------------------------------------------------------
    def list_items(self) -> List[Item]:
        with self._lock:
            return list(self._load().items)

    def get(self, item_id: str) -> Optional[Item]:
        with self._lock:
            for item in self._load().items:
                if item.id == item_id:
                    return item
        return None

    def add(self, item: Item) -> Item:
        with self._lock:
            db = self._load()
            db.items.append(item)
            self._save(db)
        return item

    def update(self, item_id: str, **fields) -> Optional[Item]:
        """Update the named fields on an item; returns the new item or None."""
        with self._lock:
            db = self._load()
            for idx, item in enumerate(db.items):
                if item.id == item_id:
                    data = item.model_dump()
                    for key, value in fields.items():
                        if value is not None:
                            data[key] = value
                    updated = Item.model_validate(data)
                    db.items[idx] = updated
                    self._save(db)
                    return updated
        return None

    def delete(self, item_id: str) -> bool:
        """Remove an item and its on-disk file folder."""
        with self._lock:
            db = self._load()
            remaining = [it for it in db.items if it.id != item_id]
            if len(remaining) == len(db.items):
                return False
            db.items = remaining
            self._save(db)
        folder = self.files_dir / item_id
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
        return True

    def item_folder(self, item_id: str) -> Path:
        folder = self.files_dir / item_id
        folder.mkdir(parents=True, exist_ok=True)
        return folder
