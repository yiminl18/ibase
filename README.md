# ibase

A local-first **personal data management system**. Give it a link or a file in
any format — a URL, PDF, image, or HTML page — and it will:

1. **Store** the original link and download the content locally.
2. **Digest** it: extract text (or OCR images / scanned PDFs) and auto-generate
   a short summary and topic tags with an LLM.
3. **Track** metadata in a single JSON file: insert time, read/unread, name,
   summary, note, topics, and the local file path.
4. **Browse** everything in a simple web UI with sorting, filtering, and
   natural-language search.

Everything runs on your machine. The LLM features use your **Claude
subscription** via the `claude` CLI — no API key required.

---

## Install

```bash
cd ibase
pip install -r requirements.txt      # or: pip install -e .
```

**Prerequisites**

- Python 3.9+
- [`claude`](https://claude.com/claude-code) CLI, logged in (for summaries &
  semantic search). Optional — the app works without it (local search only).
- `tesseract` for OCR of images / scanned PDFs (optional):
  `brew install tesseract`. `pdf2image` also needs `poppler`
  (`brew install poppler`).

## Run

```bash
# Web app
ibase serve                      # http://127.0.0.1:8000
# or without installing:
PYTHONPATH=src python3 -m ibase.cli serve

# CLI
ibase add https://arxiv.org/abs/1706.03762 --topic ml
ibase add ./paper.pdf --note "read section 3"
ibase list --unread
ibase list --q "papers about attention"
```

## How it works

```
Browser (web/) ──HTTP──▶ FastAPI (src/ibase) ──▶ data/metadata.json
                                │                 data/files/<id>/...
                    ┌───────────┼───────────┐
                 ingest       query        llm
              (fetch/OCR)  (rank/filter/  (claude CLI:
                            search)        summarize +
                                           semantic search)
```

**Hybrid query engine** — sorting and structured filters (read/unread, topic)
are pure Python and never call the LLM. Only natural-language *semantic* search
delegates to Claude, and it always falls back to local substring matching if the
CLI is unavailable.

## Configuration (environment variables)

| Variable              | Default    | Purpose |
|-----------------------|------------|---------|
| `IBASE_DATA_DIR`      | `./data`   | Where files + metadata are stored. |
| `IBASE_LLM_BACKEND`   | `cli`      | `cli` (Claude subscription), `api` (future), or `off`. |
| `IBASE_LLM_MODEL`     | `haiku`    | Model used for summaries / semantic search. |
| `IBASE_CLAUDE_BIN`    | `claude`   | Path to the `claude` binary. |
| `IBASE_LLM_TIMEOUT`   | `60`       | Seconds before an LLM call falls back to local logic. |
| `IBASE_HTTP_TIMEOUT`  | `30`       | Download timeout. |

## Project layout

```
docs/PLAN.md          Design document
src/ibase/
  config.py           Paths & settings
  models.py           Pydantic schemas
  store.py            JSON persistence (atomic writes)
  ingest/             fetcher, extract, ocr, digest pipeline
  query/              ranker, filters, semantic, pipeline
  llm/engine.py       Claude CLI wrapper (swappable backend)
  routes.py, main.py  FastAPI app
  cli.py              Command-line interface
web/                  index.html, app.js, styles.css
tests/                pytest suite
```

## Tests

```bash
PYTHONPATH=src python3 -m pytest -q
```
