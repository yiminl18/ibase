"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .routes import router

config.ensure_dirs()

app = FastAPI(title="ibase", version="0.1.0")
app.include_router(router)


@app.get("/", response_class=HTMLResponse)
def index():
    index_file = config.WEB_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>ibase</h1><p>Web UI not found.</p>")


# Serve static assets (app.js, styles.css) if the web dir exists.
if config.WEB_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(config.WEB_DIR)), name="static")
