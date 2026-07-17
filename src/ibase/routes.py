"""FastAPI routes backing every UI and CLI operation."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from . import config
from .ingest.digest import digest, digest_upload
from .llm.engine import LLMEngine
from .models import Item, ItemCreate, ItemUpdate
from .query.pipeline import run_query
from .store import Store

router = APIRouter(prefix="/api")

# Shared singletons for the running server.
store = Store()
llm = LLMEngine()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "llm_backend": llm.backend,
        "llm_available": llm.available(),
        "item_count": len(store.list_items()),
    }


@router.get("/items", response_model=List[Item])
def list_items(
    sort: str = "inserted_at",
    order: str = "desc",
    read: Optional[bool] = None,
    topic: Optional[str] = None,
    q: str = "",
    q_mode: str = Query("auto", pattern="^(auto|local|semantic)$"),
):
    return run_query(
        store.list_items(),
        read=read,
        topic=topic,
        q=q,
        q_mode=q_mode,
        sort=sort,
        order=order,
        llm=llm,
    )


@router.post("/items", response_model=Item)
def create_item(payload: ItemCreate):
    if not payload.link.strip():
        raise HTTPException(status_code=400, detail="link is required")
    return digest(
        payload.link.strip(),
        store,
        llm=llm,
        note=payload.note,
        topics=payload.topics,
    )


@router.post("/upload", response_model=Item)
async def upload_item(file: UploadFile = File(...), note: str = Form("")):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    return digest_upload(
        data,
        file.filename or "upload",
        store,
        llm=llm,
        note=note,
    )


@router.get("/items/{item_id}", response_model=Item)
def get_item(item_id: str):
    item = store.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    return item


@router.patch("/items/{item_id}", response_model=Item)
def update_item(item_id: str, payload: ItemUpdate):
    fields = payload.model_dump(exclude_unset=True)
    # When marking as read, stamp read_at.
    if fields.get("read") is True:
        current = store.get(item_id)
        if current is not None and not current.read:
            from .models import utcnow_iso
            fields["read_at"] = utcnow_iso()
    if fields.get("read") is False:
        fields["read_at"] = None
    updated = store.update(item_id, **fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="item not found")
    return updated


@router.delete("/items/{item_id}")
def delete_item(item_id: str):
    if not store.delete(item_id):
        raise HTTPException(status_code=404, detail="item not found")
    return {"deleted": item_id}


@router.get("/topics", response_model=List[str])
def list_topics():
    seen = []
    for it in store.list_items():
        for t in it.topics:
            if t not in seen:
                seen.append(t)
    return sorted(seen)


@router.get("/file/{item_id}")
def get_file(item_id: str):
    item = store.get(item_id)
    if item is None or not item.local_path:
        raise HTTPException(status_code=404, detail="file not found")
    path = (config.PROJECT_ROOT / item.local_path).resolve()
    # Guard against path traversal: file must stay under the files dir.
    if not str(path).startswith(str(config.FILES_DIR.resolve())):
        raise HTTPException(status_code=403, detail="forbidden")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="file missing on disk")
    return FileResponse(str(path), filename=path.name)
