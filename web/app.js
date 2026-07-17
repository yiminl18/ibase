"use strict";

const $ = (sel) => document.querySelector(sel);

const state = {
  sort: "inserted_at",
  order: "desc",
  read: "",
  topic: "",
  q: "",
  semantic: false,
};

let searchTimer = null;

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || res.statusText);
  }
  return res.status === 204 ? null : res.json();
}

function fmtDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric", month: "short", day: "numeric",
    });
  } catch (e) { return iso; }
}

function fmtSize(bytes) {
  if (!bytes) return "";
  const units = ["B", "KB", "MB", "GB"];
  let n = bytes, i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
}

function escapeHtml(s) {
  return (s || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

async function loadStatus() {
  try {
    const h = await api("/api/health");
    const el = $("#status");
    if (h.llm_available) {
      el.textContent = `LLM: ${h.llm_backend} ✓`;
    } else {
      el.textContent = `LLM: ${h.llm_backend} (offline — local search only)`;
    }
  } catch (e) { /* ignore */ }
}

async function loadTopics() {
  try {
    const topics = await api("/api/topics");
    const sel = $("#topic");
    const current = sel.value;
    sel.innerHTML = '<option value="">All</option>' +
      topics.map((t) => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`).join("");
    sel.value = current;
  } catch (e) { /* ignore */ }
}

function buildQuery() {
  const p = new URLSearchParams();
  p.set("sort", state.sort);
  p.set("order", state.order);
  if (state.read !== "") p.set("read", state.read);
  if (state.topic) p.set("topic", state.topic);
  if (state.q) {
    p.set("q", state.q);
    p.set("q_mode", state.semantic ? "semantic" : "auto");
  }
  return p.toString();
}

function card(item) {
  const li = document.createElement("li");
  li.className = "card";
  const readBadge = item.read
    ? '<span class="badge read">read</span>'
    : '<span class="badge unread">unread</span>';
  const statusBadge = item.fetch_status !== "ok"
    ? `<span class="badge ${item.fetch_status}">${item.fetch_status}</span>` : "";
  const topics = (item.topics || [])
    .map((t) => `<span class="chip">${escapeHtml(t)}</span>`).join(" ");
  const fileLink = item.local_path
    ? `<a class="src" href="/api/file/${item.id}" target="_blank" rel="noopener">open file</a>` : "";
  const srcLink = /^https?:/i.test(item.source_link)
    ? `<a class="src" href="${escapeHtml(item.source_link)}" target="_blank" rel="noopener">source</a>` : "";

  li.innerHTML = `
    <div class="card-head">
      <h3 class="card-title">${escapeHtml(item.name)}</h3>
      <div>${readBadge} ${statusBadge}</div>
    </div>
    ${item.summary ? `<p class="summary">${escapeHtml(item.summary)}</p>` : ""}
    <div class="meta">
      <span class="fmt">${escapeHtml(item.format)}</span>
      <span>${fmtDate(item.inserted_at)}</span>
      ${item.size_bytes ? `<span>${fmtSize(item.size_bytes)}</span>` : ""}
      ${topics}
      ${srcLink} ${fileLink}
    </div>
    ${item.note ? `<div class="note">📝 ${escapeHtml(item.note)}</div>` : ""}
    <div class="actions">
      <button data-act="toggle">${item.read ? "Mark unread" : "Mark read"}</button>
      <button data-act="note">Edit note</button>
      <button data-act="topics">Edit topics</button>
      <button data-act="del" class="del">Delete</button>
    </div>`;

  li.querySelector('[data-act="toggle"]').onclick = () => toggleRead(item);
  li.querySelector('[data-act="note"]').onclick = () => editNote(item);
  li.querySelector('[data-act="topics"]').onclick = () => editTopics(item);
  li.querySelector('[data-act="del"]').onclick = () => removeItem(item);
  return li;
}

async function render() {
  try {
    const items = await api("/api/items?" + buildQuery());
    const list = $("#list");
    list.innerHTML = "";
    items.forEach((it) => list.appendChild(card(it)));
    $("#empty").hidden = items.length > 0;
    $("#count").textContent = `${items.length} item${items.length === 1 ? "" : "s"}`;
  } catch (e) {
    $("#count").textContent = "Error: " + e.message;
  }
}

async function toggleRead(item) {
  await api(`/api/items/${item.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ read: !item.read }),
  });
  render();
}

async function editNote(item) {
  const note = prompt("Note:", item.note || "");
  if (note === null) return;
  await api(`/api/items/${item.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note }),
  });
  render();
}

async function editTopics(item) {
  const raw = prompt("Topics (comma-separated, up to 3):", (item.topics || []).join(", "));
  if (raw === null) return;
  const topics = raw.split(",").map((s) => s.trim()).filter(Boolean).slice(0, 3);
  await api(`/api/items/${item.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topics }),
  });
  loadTopics();
  render();
}

async function removeItem(item) {
  if (!confirm(`Delete "${item.name}"? This removes the local files too.`)) return;
  await api(`/api/items/${item.id}`, { method: "DELETE" });
  loadTopics();
  render();
}

// ---- add dialog ------------------------------------------------------------
let pendingFile = null;

function openAdd() {
  $("#add-link").value = "";
  $("#add-note").value = "";
  pendingFile = null;
  $("#file-input").value = "";
  const df = $("#dropfile");
  df.hidden = true; df.textContent = "";
  const s = $("#add-status");
  s.hidden = true; s.textContent = "";
  $("#add-dialog").showModal();
}

function setPendingFile(file) {
  pendingFile = file || null;
  const df = $("#dropfile");
  if (pendingFile) {
    df.hidden = false;
    df.textContent = `📎 ${pendingFile.name}`;
  } else {
    df.hidden = true; df.textContent = "";
  }
}

let pendingCount = 0;

function updatePending() {
  const el = $("#pending");
  if (pendingCount > 0) {
    el.hidden = false;
    el.textContent = `⏳ Digesting ${pendingCount} item${pendingCount === 1 ? "" : "s"} in the background…`;
  } else {
    el.hidden = true;
    el.textContent = "";
  }
}

function digestInBackground(request, label) {
  pendingCount += 1;
  updatePending();
  api(request.url, request.opts)
    .then(() => { loadTopics(); render(); })
    .catch((e) => { alert(`Failed to digest ${label}: ${e.message}`); })
    .finally(() => { pendingCount -= 1; updatePending(); });
}

function submitAdd() {
  const link = $("#add-link").value.trim();
  const note = $("#add-note").value.trim();
  if (!link && !pendingFile) return;

  let request, label;
  if (pendingFile) {
    const form = new FormData();
    form.append("file", pendingFile);
    form.append("note", note);
    request = { url: "/api/upload", opts: { method: "POST", body: form } };
    label = pendingFile.name;
  } else {
    request = {
      url: "/api/items",
      opts: {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ link, note, topics: [] }),
      },
    };
    label = link;
  }

  // Close immediately; digest runs in the background so you can add more.
  $("#add-dialog").close();
  digestInBackground(request, label);
}

function wireDropzone() {
  const dz = $("#dropzone");
  const input = $("#file-input");
  dz.onclick = () => input.click();
  dz.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") input.click(); };
  input.onchange = () => setPendingFile(input.files[0]);
  ["dragenter", "dragover"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
  dz.addEventListener("drop", (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files.length) {
      setPendingFile(e.dataTransfer.files[0]);
    }
  });
}

// ---- wiring ----------------------------------------------------------------
function wire() {
  $("#sort").onchange = (e) => { state.sort = e.target.value; render(); };
  $("#order").onchange = (e) => { state.order = e.target.value; render(); };
  $("#read").onchange = (e) => { state.read = e.target.value; render(); };
  $("#topic").onchange = (e) => { state.topic = e.target.value; render(); };
  $("#semantic").onchange = (e) => { state.semantic = e.target.checked; if (state.q) render(); };
  $("#q").oninput = (e) => {
    state.q = e.target.value.trim();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(render, 350);
  };
  $("#q").onkeydown = (e) => { if (e.key === "Enter") { clearTimeout(searchTimer); render(); } };

  $("#add-btn").onclick = openAdd;
  $("#add-cancel").onclick = () => $("#add-dialog").close();
  $("#add-submit").onclick = (e) => { e.preventDefault(); submitAdd(); };
  wireDropzone();
}

wire();
loadStatus();
loadTopics();
render();
