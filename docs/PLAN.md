# ibase — Personal Data Management System

**Status:** Planning
**Last updated:** 2026-07-17

A local-first system to collect links/files you want to read, download and store
their content locally, track metadata (read/unread, summary, notes, topic), and
browse/search/filter them through a simple web interface.

---

## 1. Goals & scope

### In scope (v1)
1. **Ingest** — give the system a link (or local file path). It:
   - stores the original link,
   - downloads the content locally when possible (HTML→text, PDF, image),
   - records metadata in a JSON store.
2. **Metadata store** — a single JSON file describing every item:
   insert time, read/unread, name, short summary, note, topic, source link,
   local file path.
3. **Web UI** — one page that lists items (name, read status, date, summary,
   topic) with a top filter/control bar to:
   - **rank/sort** by a chosen field (no LLM),
   - **search/filter** by conditions on attributes (LLM-assisted for
     natural-language queries).
4. **Backend engine** — HTTP API backing every UI operation. Rank/filter is
   plain Python; semantic search delegates to the Claude CLI.

### Out of scope (v1)
- Multi-user / auth / cloud sync (local, single-user only).
- Full-text search index (e.g. Elasticsearch). We use in-memory scans over the
  JSON store — fine for hundreds/low-thousands of items.
- Automatic re-crawling or link-rot detection.
- Rich document viewer/annotation (we link to the local file; the OS opens it).

---

## 2. Tech stack (decided)

| Layer      | Choice                          | Why |
|------------|---------------------------------|-----|
| Backend    | Python 3.11+ / **FastAPI**      | Matches sibling Python projects; async, auto OpenAPI docs, easy LLM calls. |
| Server     | uvicorn                         | Standard ASGI server for FastAPI. |
| Frontend   | **Plain HTML + CSS + vanilla JS** | No build step; served as a static file by FastAPI. Easy to run and maintain. |
| Storage    | JSON file + local `data/` tree  | Human-readable, git-diffable, zero DB setup. |
| LLM        | **Claude Code CLI** (`claude -p … --output-format json`) | Uses your Claude *subscription* — no API key, no per-token cost. |
| Fetching   | `httpx`, `beautifulsoup4`, `pypdf` | Download + extract text from HTML/PDF. |
| OCR        | `pytesseract`, `Pillow`, `pdf2image` | Extract text from images & scanned PDFs (needs system `tesseract`). |

### Why the Claude CLI instead of the API
You have a subscription, not an API key. The backend invokes the local `claude`
binary in headless print mode:

```bash
claude -p "SYSTEM+USER PROMPT HERE" --output-format json
```

It returns JSON including the model's text, which we parse. This is wrapped in a
single `LLMEngine` class so we can swap to the real Anthropic API later by
changing one file (set `IBASE_LLM_BACKEND=api` + `ANTHROPIC_API_KEY`).

**Trade-offs to accept:** each LLM call spawns a subprocess (hundreds of ms to a
few seconds) and depends on `claude` being installed and logged in. That is why
the LLM is used **only** for natural-language search, never for ranking or
simple structured filters.

---

## 3. Architecture

```
                ┌─────────────────────────────────────────┐
                │              Browser (UI)                │
                │  index.html + app.js + styles.css        │
                │  - list view                             │
                │  - top control bar: sort + search/filter │
                └───────────────┬──────────────────────────┘
                                │ HTTP (JSON)
                ┌───────────────▼──────────────────────────┐
                │              FastAPI backend              │
                │                                           │
                │  routes  →  services  →  store            │
                │                                           │
                │  ┌─────────┐  ┌──────────┐  ┌──────────┐  │
                │  │ ingest  │  │  query   │  │  store    │ │
                │  │ service │  │ engine   │  │ (JSON IO) │ │
                │  └────┬────┘  └────┬─────┘  └────┬─────┘  │
                │       │            │             │        │
                │   fetcher      LLMEngine     metadata.json│
                │  (http/pdf)   (claude -p)                 │
                └───────────────────┬──────────────────────┘
                                    │ writes
                     ┌──────────────▼───────────────┐
                     │  data/                        │
                     │    metadata.json              │
                     │    files/<id>/<original name> │
                     └───────────────────────────────┘
```

### Directory layout (proposed)
```
ibase/
├── docs/
│   └── PLAN.md                 # this file
├── data/                       # created at runtime (gitignored)
│   ├── metadata.json
│   └── files/
│       └── <item-id>/...
├── src/ibase/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app + static mount
│   ├── config.py               # paths, env, settings
│   ├── models.py               # pydantic schemas (Item, etc.)
│   ├── store.py                # load/save metadata.json (atomic writes)
│   ├── ingest/
│   │   ├── fetcher.py          # download + content-type / format detection
│   │   ├── extract.py          # HTML→text, PDF→text
│   │   └── ocr.py              # image & scanned-PDF OCR (pytesseract)
│   ├── query/
│   │   ├── ranker.py           # sort by field (no LLM)
│   │   ├── filters.py          # structured attribute conditions (no LLM)
│   │   └── semantic.py         # NL search via LLMEngine
│   ├── llm/
│   │   └── engine.py           # LLMEngine: claude CLI + future API backend
│   ├── routes.py               # API endpoints
│   └── cli.py                  # `ibase add <url>` etc.
├── web/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── tests/
│   ├── test_store.py
│   ├── test_ranker.py
│   ├── test_filters.py
│   └── test_ingest.py
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## 4. Data model

### Item (one entry in `metadata.json`)
```jsonc
{
  "id": "a1b2c3d4",               // short uuid, also the files/ subfolder name
  "name": "Attention Is All You Need",
  "source_link": "https://arxiv.org/abs/1706.03762",
  "local_path": "data/files/a1b2c3d4/1706.03762.pdf", // null if download failed
  "content_text_path": "data/files/a1b2c3d4/content.txt", // extracted text, null if none
  "format": "pdf",                // "pdf" | "html" | "image" | "text" | "other"
  "read": false,
  "topics": ["machine-learning", "nlp"], // 1–3 tags, LLM-suggested + user-editable
  "summary": "Introduces the Transformer architecture based on self-attention.",
  "note": "Re-read section 3.2 for positional encoding.",
  "inserted_at": "2026-07-17T10:40:00Z",
  "read_at": null,
  "size_bytes": 2145678,
  "fetch_status": "ok"            // "ok" | "partial" | "failed"
}
```

`metadata.json` is a single object: `{ "items": [ ... ], "version": 1 }`.

**Concurrency:** single-user, but writes use atomic replace (write temp file →
`os.replace`) to avoid corruption. Reads load the whole file (small dataset).

---

## 5. Ingestion flow

Input can be **any format** — a URL, a local PDF, an image, a text/HTML file.
The system detects what it is and digests it accordingly; there is no separate
"import" vs "add link" path.

1. Receive input: a URL **or** a local file path, plus optional `note` / `topics`.
2. Generate `id`, create `data/files/<id>/`.
3. **Fetch** (`fetcher.py`):
   - HTTP GET with `httpx`, follow redirects, capture `Content-Type`.
   - Save the raw file under the item folder using a sanitized filename.
4. **Extract** (`extract.py`) by detected format:
   - `text/html` → strip boilerplate with BeautifulSoup → `content.txt`.
   - `application/pdf` → `pypdf` text extraction → `content.txt`. If the PDF has
     no extractable text (scanned), fall back to OCR (§5a).
   - `image/*` → **OCR** the image (§5a) → `content.txt`; keep the image too.
   - other → store raw; best-effort text.
5. **Summarize (always, on digest):** once content text exists, ask the Claude
   CLI for a 1–2 sentence summary and 1–3 suggested topics. This runs
   automatically for every ingested item — no flag. If the CLI is unavailable,
   the item is still stored with an empty summary and `fetch_status: "partial"`,
   and can be re-summarized later.
6. **Name:** from HTML `<title>`, PDF metadata title, or the filename.
7. Append the Item to `metadata.json`.

Failures are non-fatal: an item with `fetch_status: "failed"` is still recorded
(link preserved) so nothing is lost.

### 5a. OCR (images & scanned PDFs)
- Library: **`pytesseract`** (wraps the Tesseract engine) with `Pillow` for
  image loading; scanned PDFs are rasterized per page via `pdf2image`.
- Requires the system `tesseract` binary (`brew install tesseract`). Recorded in
  README prerequisites. If missing, OCR is skipped and `content.txt` is null with
  `fetch_status: "partial"` — the item and image are still stored.
- OCR text feeds the same summarize step, so images become searchable by their
  extracted text + LLM summary.

---

## 6. Backend API

Base URL `http://127.0.0.1:8000`. All responses JSON.

| Method | Path                | Purpose |
|--------|---------------------|---------|
| GET    | `/`                 | Serve the web UI (`index.html`). |
| GET    | `/api/items`        | List items. Query params: `sort`, `order`, `read`, `topic`, `q`. |
| POST   | `/api/items`        | Ingest a new link/file. Body: `{link, note?, topic?, summarize?}`. |
| GET    | `/api/items/{id}`   | Fetch one item. |
| PATCH  | `/api/items/{id}`   | Update mutable fields: `read`, `note`, `topic`, `summary`, `name`. |
| DELETE | `/api/items/{id}`   | Remove item + its local files. |
| GET    | `/api/file/{id}`    | Stream/download the stored local file. |
| GET    | `/api/topics`       | Distinct topic values (for filter dropdown). |
| GET    | `/api/health`       | Liveness + whether the `claude` CLI is available. |

### `GET /api/items` — the query engine
Query parameters (all optional, combinable):
- `sort` = field name (`inserted_at`, `name`, `read`, `topic`, `size_bytes`, …)
- `order` = `asc` | `desc`
- `read` = `true` | `false`
- `topic` = exact match
- `q` = free-text/natural-language query

**Resolution order (hybrid engine):**
1. Apply structured filters (`read`, `topic`) — pure Python.
2. If `q` is present:
   - First try a cheap local substring match over `name`/`summary`/`note`/`topic`.
   - If `q` looks like a natural-language request (heuristic: contains spaces +
     verbs/keywords, or `q_mode=semantic`), send the candidate list + query to
     the **LLMEngine**, which returns the ids that match. Local match is the
     fallback if the CLI fails.
3. Sort the result by `sort`/`order` (pure Python).

This guarantees the UI stays responsive: sorting and basic filtering never block
on the LLM; only explicit semantic search does.

---

## 7. LLM engine (`llm/engine.py`)

```python
class LLMEngine:
    def available(self) -> bool: ...        # is `claude` on PATH & usable?
    def summarize(self, text: str) -> dict: # {"summary": str, "topic": str}
    def semantic_filter(self, query: str, items: list[dict]) -> list[str]:
        # returns matching item ids
```

- Backend selected by env `IBASE_LLM_BACKEND` = `cli` (default) | `api` | `off`.
- **cli:** `subprocess.run(["claude", "-p", prompt, "--output-format", "json"], …)`,
  parse the JSON, extract the text, then parse the model's structured answer.
  Timeout + graceful degradation to non-LLM behavior.
- **api:** placeholder for future `ANTHROPIC_API_KEY` usage (same interface).
- **off:** all methods no-op / fall back to local logic. Lets the whole system
  run with zero LLM dependency.

Prompts are constrained to return strict JSON (e.g. `{"ids": [...]}`) so parsing
is deterministic; malformed output → fall back to local match.

---

## 8. Frontend (single page)

- **Top control bar:**
  - Sort dropdown (field) + asc/desc toggle.
  - Read filter: All / Read / Unread.
  - Topic dropdown (populated from `/api/topics`).
  - Search box (`q`) with a "semantic" toggle.
  - "Add link" button → small modal (link, note, topic, summarize checkbox).
- **List:** rows/cards showing name, read badge, insert date, topic, summary.
  Each row: mark read/unread, edit note, open local file, delete.
- Vanilla JS `fetch()` against the API; re-render list on any control change.
- Responsive, works in light/dark; no external CDN (fully local).

---

## 9. CLI (`ibase/cli.py`)

```
ibase add <url> [--note ...] [--topic ...] [--summarize]
ibase list [--read/--unread] [--topic ...] [--sort field]
ibase serve                # launch the web app (uvicorn)
```

Shares the exact same services as the API — no logic duplicated.

---

## 10. Milestones

| # | Milestone | Deliverable |
|---|-----------|-------------|
| 1 | Skeleton & store | `pyproject`, config, models, `store.py` + tests; empty `metadata.json`. |
| 2 | Ingestion | `fetcher` + `extract` for HTML/PDF/image; `ibase add` CLI; tests. |
| 3 | Query engine | `ranker` + `filters` + `/api/items`; tests. |
| 4 | Web UI | `index.html`/`app.js`/`styles.css` wired to the API. |
| 5 | LLM layer | `LLMEngine` (cli backend), summarize on ingest, semantic search. |
| 6 | Polish | delete, edit note/read, health check, README, `.gitignore`. |

Each milestone is independently runnable and testable.

---

## 11. Resolved decisions

1. **Topics** — multiple tags, **max 3** per item. LLM suggests them on digest;
   user can edit.
2. **Summarize** — happens **automatically during digestion** for every item
   (not opt-in). No flag/checkbox.
3. **Images** — **OCR on digest** so image text is extracted and searchable;
   scanned PDFs get the same treatment.
4. **Dataset size** — hundreds to low thousands. Flat `metadata.json` is
   sufficient; no SQLite needed for v1.
5. **Input formats** — accept **anything** (URL, PDF, image, HTML, text). Format
   is auto-detected and digested on receipt; one unified ingestion path.

All open questions are resolved — the plan is ready to implement.
```
