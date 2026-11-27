"use strict";

/* Narrated Slides UI. Vanilla JS, no build step.
   Views: home (#/), script (#/deck/<id>/script), export (#/deck/<id>/export). */

// ---------- tiny helpers ----------
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(kid));
  return el;
}

const ICONS = {
  upload: '<path d="M12 16V4m0 0L7 9m5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>',
  play: '<path d="M8 5.5v13l11-6.5z"/>',
  stop: '<rect x="7" y="7" width="10" height="10" rx="1.5"/>',
  sparkles: '<path d="M11 3l1.9 5.1L18 10l-5.1 1.9L11 17l-1.9-5.1L4 10l5.1-1.9zM19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
  download: '<path d="M12 4v11m0 0l-4.5-4.5M12 15l4.5-4.5M4 20h16"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6L7 7M17 17l1.4 1.4M5.6 18.4L7 17M17 7l1.4-1.4"/>',
  moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1.1 1-1.1 1.7M12 17h.01"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-12M9 7V4h6v3"/>',
  right: '<path d="M5 12h14m-6-6l6 6-6 6"/>',
  left: '<path d="M19 12H5m6-6l-6 6 6 6"/>',
  chevL: '<path d="M15 5l-7 7 7 7"/>',
  chevR: '<path d="M9 5l7 7-7 7"/>',
  film: '<rect x="4" y="5" width="16" height="14" rx="2"/><path d="M8 5v14M16 5v14M4 9.5h4M4 14.5h4M16 9.5h4M16 14.5h4"/>',
  subtitles: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 11h4M13 11h4M7 15h2M12 15h5"/>',
  audio: '<path d="M9 18V6l10-2v12"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="16.5" cy="16" r="2.5"/>',
  deck: '<path d="M3 4h18M5 4v10h14V4M12 14v5M8 20l4-1 4 1"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
};
function icon(name, extra = "") {
  const t = document.createElement("template");
  const filled = name === "play" || name === "stop";
  t.innerHTML = `<svg class="i ${filled ? "solid" : ""} ${extra}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${ICONS[name] || ""}</svg>`;
  return t.content.firstChild;
}
function hydrateIcons(root = document) {
  $$("[data-icon]", root).forEach((el) => {
    if (el.dataset.done) return;
    el.dataset.done = "1";
    const svg = icon(el.dataset.icon);
    if (el.dataset.size) { svg.style.width = svg.style.height = el.dataset.size + "px"; }
    el.prepend(svg);
  });
}

function toast(msg, kind = "info", ms = 4500) {
  const el = h("div", { class: `toast ${kind}`, role: kind === "error" ? "alert" : "status" }, msg);
  $("#toasts").append(el);
  setTimeout(() => el.remove(), ms);
}

async function api(path, opts = {}) {
  let res;
  try { res = await fetch(path, opts); }
  catch { throw new Error("Can't reach the app. Is it still running?"); }
  if (!res.ok) {
    let msg = res.statusText || `Error ${res.status}`;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail
        : Array.isArray(body.detail) ? body.detail.map((d) => d.msg).join("; ") : JSON.stringify(body.detail);
    } catch { /* keep status text */ }
    throw new Error(msg);
  }
  return res;
}
const getJSON = async (p) => (await api(p)).json();
const sendJSON = async (p, method, body) =>
  (await api(p, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })).json();

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const fmtBytes = (n) => (n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " KB");
const fmtDur = (s) => { s = Math.max(0, Math.round(s)); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };
const words = (t) => (String(t || "").trim().match(/\S+/g) || []).length;
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
};

async function runJob(jobId, onUpdate) {
  for (;;) {
    const job = await getJSON(`/api/jobs/${jobId}`);
    onUpdate?.(job);
    if (job.status === "done") return job.result;
    if (job.status === "error") throw new Error(job.error || "The job failed.");
    await sleep(700);
  }
}

// ---------- voices ----------
const KOKORO_LANG = { a: "English (US)", b: "English (UK)", e: "Spanish", f: "French", h: "Hindi", i: "Italian", j: "Japanese", p: "Portuguese", z: "Chinese" };
const isClone = (v) => /^clone_/.test(v || "");
function voiceLang(v) {
  if (isClone(v)) return "My voices";
  if (/^sq[_-]/i.test(v)) return "Shqip (Albanian)";
  const m = /^([a-z])([fm])_/.exec(v);
  return (m && KOKORO_LANG[m[1]]) || "Other";
}
function voiceLabel(v) {
  if (isClone(v)) return (S.myVoices.find((x) => x.id === v) || {}).name || v.slice(6).replace(/_/g, " ");
  const m = /^(?:[a-z][fm]|sq)_(.+)$/i.exec(v);
  if (!m) return v;
  const name = m[1].replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  const g = /^[a-z]([fm])_/.exec(v);
  return g ? `${name} (${g[1] === "f" ? "female" : "male"})` : name;
}
const isAlbanian = (v) => /^sq[_-]/i.test(v || "");
function sampleLine(v) {
  return isAlbanian(v) ? "Përshëndetje! Kështu do të tingëllojnë sllajdet tuaja me zë." : "Hello! This is how your narrated slides will sound.";
}
function voiceSelect(id) {
  const st = S.settings;
  const list = S.voices.length ? S.voices : [st.voice || S.defaultVoice || "default"];
  const groups = new Map();
  for (const v of list) { const l = voiceLang(v); if (!groups.has(l)) groups.set(l, []); groups.get(l).push(v); }
  const rank = (l) => (l === "My voices" ? 0 : l === "Shqip (Albanian)" ? 1 : 2);
  const order = [...groups.keys()].sort((a, b) => rank(a) - rank(b));
  const sel = h("select", { id, "aria-label": "Voice" }, order.map((lang) =>
    h("optgroup", { label: lang }, groups.get(lang).map((v) => h("option", { value: v, selected: v === st.voice }, voiceLabel(v))))));
  sel.addEventListener("change", () => {
    st.voice = sel.value;
    store.set("ns-settings", S.settings);
    $$("select.voice-pick").forEach((o) => { if (o !== sel) o.value = sel.value; });
    document.dispatchEvent(new Event("ns-voice-changed"));
  });
  sel.classList.add("voice-pick");
  return sel;
}

// ---------- state ----------
const DEFAULTS = { voice: "", speed: 1, pause: 0.8, silent: 3, res: 1080, subs: [], style: "natural" };
const SUB_LANGS = [["en", "English"], ["sq", "Shqip"], ["it", "Italiano"], ["pt", "Português"], ["no", "Norsk"], ["tr", "Türkçe"]];
function voiceLangCode(v) {
  if (isAlbanian(v)) return "sq";
  if (isClone(v)) return "en";
  const m = /^([a-z])[fm]_/.exec(v || "");
  return m ? ({ a: "en", b: "en", i: "it", p: "pt" })[m[1]] || null : null;
}
const S = {
  deck: null, notes: {}, cur: 1,
  health: null, voices: [], defaultVoice: "",
  settings: { ...DEFAULTS, ...store.get("ns-settings", {}) },
  dirty: false, saveTimer: null, audio: null, aiBusy: false, myVoices: [],
};
let E = {}; // script-view element refs

// ---------- theme ----------
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  const b = $("#btn-theme");
  b.replaceChildren(icon(t === "dark" ? "sun" : "moon"));
}
$("#btn-theme").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  try { localStorage.setItem("ns-theme", next); } catch { /* ignore */ }
  applyTheme(next);
});
applyTheme(document.documentElement.dataset.theme);
$("#btn-help").replaceChildren(icon("help"));
$("#btn-help").addEventListener("click", () => $("#dlg-help").showModal());

// ---------- health + services dialog ----------
async function refreshHealth() {
  try {
    S.health = await getJSON("/api/health");
  } catch {
    S.health = null;
  }
  const hl = S.health;
  const dot = $("#status-dot"), text = $("#status-text");
  if (!hl) { dot.className = "dot bad"; text.textContent = "App offline"; return; }
  dot.className = "dot " + (hl.tts ? "ok" : "bad");
  text.textContent = hl.tts ? "Ready" : "Voice offline";
  $("#max-mb").textContent = hl.max_upload_mb;
  $("#app-version").textContent = hl.version ? "v" + hl.version : "";
  const gen = $("#gen-go");
  gen.disabled = !hl.presenton;
  const link = h("a", { href: hl.presenton_url || "http://localhost:5001", target: "_blank", rel: "noopener" }, "Open Presenton");
  $("#gen-note").replaceChildren(...(!hl.presenton
    ? ["Presenton isn't reachable, so deck generation is unavailable. Uploading a deck still works. See Services (top right)."]
    : hl.presenton_api_key
      ? ["Presenton writes the slides, then you add the narration as usual. This can take a few minutes. You can also design a deck in ", link, ", export it as PPTX and upload it here."]
      : ["Generating from here needs a Presenton API key (PRESENTON_API_KEY in .env). ", link, " to create one, or design the deck there, export PPTX and upload it here."]));
  if (hl.tts && (!S.voices.length || (hl.extra_tts && !S.voices.some(isAlbanian)))) loadVoices().then(refreshVoicePickers);
}
function refreshVoicePickers() {
  $$("select.voice-pick").forEach((old) => old.replaceWith(voiceSelect(old.id)));
  document.dispatchEvent(new Event("ns-voice-changed"));
}
function onVoiceChange(el, fn) {  // runs fn while el is on the page
  const handler = () => { if (!el.isConnected) document.removeEventListener("ns-voice-changed", handler); else fn(); };
  document.addEventListener("ns-voice-changed", handler);
}
async function loadMyVoices() {
  if (S.health?.clone == null) { S.myVoices = []; return; }
  try { S.myVoices = (await getJSON("/api/my-voices")).voices; } catch { S.myVoices = []; }
}
async function loadVoices() {
  await loadMyVoices();
  try {
    const v = await getJSON("/api/voices");
    S.voices = v.voices; S.defaultVoice = v.default;
    if (!S.settings.voice) S.settings.voice = v.default;
  } catch { /* shown by the status pill */ }
}

function serviceRow(level, name, tag, msg, cmd, link) {
  return h("div", { class: "svc" },
    h("span", { class: `dot ${level}` }),
    h("div", {},
      h("h3", {}, name, tag ? h("span", { class: "tag" }, tag) : null),
      h("p", {}, msg),
      cmd ? h("pre", {}, cmd) : null,
      link ? h("a", { class: "btn sm svc-link", href: link.href, target: "_blank", rel: "noopener" }, link.label, icon("right")) : null));
}
function presentonLink(label = "Open Presenton") {
  return { href: S.health?.presenton_url || "http://localhost:5001", label };
}
async function openStatus() {
  const dlg = $("#dlg-status");
  dlg.showModal();
  $("#status-body").replaceChildren(h("p", { class: "muted" }, "Checking…"));
  await refreshHealth();
  const hl = S.health;
  const body = $("#status-body");
  if (!hl) {
    body.replaceChildren(serviceRow("bad", "Narrated Slides app", "", "The page can't reach the app. Make sure it is still running.", "docker compose ps\ndocker compose logs narrator"));
    return;
  }
  body.replaceChildren(
    hl.tts
      ? serviceRow("ok", "Voice (Kokoro)", "required", `Ready. Default voice: ${hl.default_voice}.`)
      : serviceRow("bad", "Voice (Kokoro)", "required", "Not answering. On first start it downloads its model, so give it a minute, then check its log.", "docker compose ps\ndocker compose logs kokoro"),
    ...(hl.extra_tts === null || hl.extra_tts === undefined ? [] : [hl.extra_tts
      ? serviceRow("ok", "Albanian voice (Piper)", "optional", "Ready. Pick a Shqip voice to narrate Albanian slides.")
      : serviceRow("warn", "Albanian voice (Piper)", "optional", "Starting. On first start it downloads the Albanian voices (about 60 MB each). Give it a minute, then check its log.", "docker compose logs piper")]),
    hl.clone == null && hl.clone_native
      ? serviceRow("bad", "Voice cloning (Mac GPU)", "optional", "Your voice service on this Mac isn't running.", "./scripts/run-cloner-mac.sh start")
      : hl.clone == null
      ? serviceRow("warn", "Voice cloning", "optional", "Not started. Clone your own English voice from a short recording.", "docker compose --profile clone up -d --build")
      : hl.clone
        ? serviceRow("ok", "Voice cloning", "optional", "Ready. Add your voice under Voice & export, My voice.")
        : serviceRow("warn", "Voice cloning", "optional", "Starting. The first start downloads the model (2.5 to 4.5 GB), which takes a few minutes.", "docker compose logs cloner"),
    !hl.llm_configured
      ? serviceRow("warn", "Notes AI", "optional", "Not set up. It drafts notes for slides that have none; everything else works without it.", "docker compose --profile ollama up -d\n# then set NOTES_LLM_BASE_URL and NOTES_LLM_MODEL in .env")
      : hl.llm
        ? serviceRow("ok", "Notes AI", "optional", "Ready.")
        : serviceRow("bad", "Notes AI", "optional", "Configured but not answering. If you use Ollama, make sure it is running and the model has been pulled.", "ollama serve\nollama pull <model-name>"),
    hl.presenton
      ? serviceRow(hl.presenton_api_key ? "ok" : "warn", "Presenton", "optional", hl.presenton_api_key
        ? "Ready. You can generate decks from a prompt."
        : "Running, but PRESENTON_API_KEY isn't set, so generating from the app will be refused. Open Presenton, create an API key in its settings, add it to .env as PRESENTON_API_KEY=..., then run: docker compose up -d",
        null, presentonLink(hl.presenton_api_key ? "Open Presenton" : "Open Presenton to create a key"))
      : serviceRow("warn", "Presenton", "optional", "Not reachable. Only needed to generate decks from a prompt. Uploading your own deck works without it.", "docker compose up -d presenton", presentonLink()),
  );
}
$("#btn-status").addEventListener("click", openStatus);

// ---------- routing ----------
function showView(name, deckId) {
  for (const v of ["home", "script", "export"]) $(`#view-${v}`).hidden = v !== name;
  const steps = $("#steps");
  steps.hidden = name === "home";
  if (name !== "home") {
    $("#step-script").href = `#/deck/${deckId}/script`;
    $("#step-export").href = `#/deck/${deckId}/export`;
    for (const [id, key] of [["step-deck", "home"], ["step-script", "script"], ["step-export", "export"]]) {
      const a = $("#" + id);
      a.removeAttribute("aria-current");
      a.classList.toggle("done", ["home", "script", "export"].indexOf(key) < ["home", "script", "export"].indexOf(name));
      if (key === name) a.setAttribute("aria-current", "step");
    }
  }
  window.scrollTo({ top: 0 });
}

function parseHash() {
  const m = location.hash.match(/^#\/deck\/([0-9a-f]{32})\/(script|export)$/);
  return m ? { id: m[1], view: m[2] } : null;
}

async function loadDeck(id) {
  const d = await getJSON(`/api/decks/${id}`);
  S.deck = d;
  S.notes = Object.fromEntries(d.slides.map((s) => [String(s.n), s.notes || ""]));
  S.cur = d.slides[0]?.n ?? 1;
  S.dirty = false;
  const saved = d.settings || {};
  if (saved.voice) {
    S.settings = { ...S.settings, voice: saved.voice, speed: saved.speed ?? S.settings.speed, pause: saved.pause ?? S.settings.pause,
      silent: saved.silent_seconds ?? S.settings.silent, res: saved.resolution ?? S.settings.res };
  }
}

async function route() {
  stopAudio();
  const r = parseHash();
  if (!r) {
    S.deck = null;
    showView("home");
    loadRecent();
    return;
  }
  try {
    if (!S.deck || S.deck.id !== r.id) await loadDeck(r.id);
  } catch (e) {
    toast(e.message, "error");
    location.hash = "#/";
    return;
  }
  if (!S.voices.length) await loadVoices();
  if (r.view === "script") renderScript(); else renderExport();
}
window.addEventListener("hashchange", () => { flushSave(); route(); });

// ---------- home ----------
function setBusy(on, title = "Working…") {
  $("#drop-wrap").hidden = on;
  $("#home-busy").hidden = !on;
  $("#busy-title").textContent = title;
  $("#busy-fill").style.width = "0%";
  $("#busy-pct").textContent = "";
  $("#busy-step").textContent = "";
  if (on) showHomeError("");
}
function busyProgress(frac, step) {
  $("#busy-fill").style.width = Math.round(frac * 100) + "%";
  $("#busy-pct").textContent = Math.round(frac * 100) + "%";
  if (step) $("#busy-step").textContent = step;
}
function showHomeError(msg) {
  const e = $("#home-error");
  e.replaceChildren(msg || "");
  if (msg && /presenton/i.test(msg)) {
    e.append(" ", h("a", { href: S.health?.presenton_url || "http://localhost:5001", target: "_blank", rel: "noopener" }, "Open Presenton"));
  }
  e.hidden = !msg;
}

function uploadFile(file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/decks");
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onerror = () => reject(new Error("Upload failed. Is the app still running?"));
    xhr.onload = () => {
      let body = {};
      try { body = JSON.parse(xhr.responseText); } catch { /* not json */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body);
      else reject(new Error(typeof body.detail === "string" ? body.detail : `Upload failed (${xhr.status}).`));
    };
    const fd = new FormData();
    fd.append("file", file);
    xhr.send(fd);
  });
}

async function startDeckJob(title, start, uploadPhase = false) {
  setBusy(true, title);
  try {
    const { job_id, deck_id } = await start();
    await runJob(job_id, (j) => busyProgress(uploadPhase ? 0.1 + j.progress * 0.9 : j.progress, j.step));
    S.deck = null;
    location.hash = `#/deck/${deck_id}/script`;
  } catch (e) {
    showHomeError(e.message);
  } finally {
    setBusy(false);
  }
}

function handleFile(file) {
  if (!file) return;
  if (!/\.pptx$/i.test(file.name)) { showHomeError("Please choose a .pptx file. Save .ppt or Keynote decks as PowerPoint (.pptx) first."); return; }
  startDeckJob(`Opening ${file.name}`, () => uploadFile(file, (f) => busyProgress(f * 0.1, "Uploading…")), true);
}

const drop = $("#drop");
$("#file").addEventListener("change", (e) => { handleFile(e.target.files[0]); e.target.value = ""; });
drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("#file").click(); } });
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => handleFile(e.dataTransfer.files[0]));
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", (e) => e.preventDefault());

$("#btn-sample").addEventListener("click", () =>
  startDeckJob("Opening the sample deck", () => sendJSON("/api/decks/sample", "POST", {})));

$("#gen-go").addEventListener("click", () => {
  const prompt = $("#gen-prompt").value.trim();
  if (prompt.length < 3) { toast("Describe the presentation first.", "error"); $("#gen-prompt").focus(); return; }
  const n = parseInt($("#gen-n").value, 10);
  startDeckJob("Generating your deck", () => sendJSON("/api/decks/generate", "POST", {
    prompt, n_slides: Number.isFinite(n) ? n : null, tone: $("#gen-tone").value, template: $("#gen-template").value.trim() || "general",
  }));
});

async function loadRecent() {
  let decks = [];
  try { decks = (await getJSON("/api/decks")).decks; } catch { /* ignore */ }
  $("#recent").hidden = !decks.length;
  const grid = $("#recent-grid");
  grid.replaceChildren(...decks.slice(0, 12).map((d) => {
    const del = h("button", { class: "icon-btn del", type: "button", "aria-label": `Delete ${d.name}`, title: "Delete" }, icon("trash"));
    let armed = null;
    del.addEventListener("click", async () => {
      if (!armed) {
        del.classList.add("confirm"); del.replaceChildren("Delete?");
        armed = setTimeout(() => { armed = null; del.classList.remove("confirm"); del.replaceChildren(icon("trash")); }, 3000);
        return;
      }
      clearTimeout(armed);
      try { await api(`/api/decks/${d.id}`, { method: "DELETE" }); loadRecent(); } catch (e) { toast(e.message, "error"); }
    });
    return h("li", { class: "rcard" },
      h("a", { class: "open", href: `#/deck/${d.id}/${d.rendered ? "export" : "script"}` },
        h("img", { src: `/api/decks/${d.id}/slides/1.jpg`, alt: "", loading: "lazy" }),
        h("div", { class: "meta" },
          h("strong", {}, d.name),
          h("span", {}, `${d.slides} slide${d.slides === 1 ? "" : "s"} · ${timeAgo(d.updated)}`,
            d.rendered ? h("span", { class: "tag" }, "video ready") : null))),
      del);
  }));
}
function timeAgo(ts) {
  const s = Date.now() / 1000 - ts;
  if (s < 90) return "just now";
  if (s < 3600) return Math.round(s / 60) + " min ago";
  if (s < 86400) return Math.round(s / 3600) + " h ago";
  return Math.round(s / 86400) + " d ago";
}

// ---------- audio preview ----------
function stopAudio() {
  if (S.audio) { S.audio.pause(); URL.revokeObjectURL(S.audio.src); S.audio = null; }
  document.dispatchEvent(new Event("ns-audio-stopped"));
}
async function playPreview(text, btn, labels) {
  if (S.audio || btn.dataset.loading) { stopAudio(); return; }
  text = text.trim();
  if (!text) { toast("There's nothing to read yet. Write some notes first.", "info"); return; }
  const clone = isClone(S.settings.voice);
  let limit = 1500;
  if (clone) {  // own voices are generated on the CPU: preview just the opening sentences
    const first = text.match(/^(.+?[.!?])(\s+.+?[.!?])?(?=\s|$)/s);
    limit = Math.min(first ? first[0].length : 220, 260);
  }
  const original = text.length > limit;
  btn.dataset.loading = "1";
  btn.replaceChildren(icon("stop"), clone ? "Speaking in your voice…" : "Loading…");
  const reset = () => { delete btn.dataset.loading; btn.replaceChildren(icon("play"), labels); document.removeEventListener("ns-audio-stopped", reset); };
  document.addEventListener("ns-audio-stopped", reset);
  try {
    const res = await api("/api/tts/preview", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text.slice(0, limit), voice: S.settings.voice || null, speed: Number(S.settings.speed) || 1, style: S.settings.style || "natural" }),
    });
    const url = URL.createObjectURL(await res.blob());
    if (!btn.dataset.loading) { URL.revokeObjectURL(url); return; } // cancelled while loading
    const a = new Audio(url);
    S.audio = a;
    a.onended = stopAudio;
    a.onerror = () => { toast("Couldn't play that audio.", "error"); stopAudio(); };
    btn.replaceChildren(icon("stop"), "Stop");
    await a.play();
    if (original) toast(clone ? "Previewing the first sentences in your voice. The video uses all of them." : "Previewing the first part of a long note.", "info", 3000);
  } catch (e) {
    toast(e.message, "error");
    stopAudio();
  }
}

// ---------- script view ----------
function slideByN(n) { return S.deck.slides.find((s) => s.n === n); }
function imgUrl(n) { return `/api/decks/${S.deck.id}/slides/${n}.jpg`; }

function scheduleSave() {
  S.dirty = true;
  setSaveState("Saving…");
  clearTimeout(S.saveTimer);
  S.saveTimer = setTimeout(flushSave, 700);
}
function setSaveState(text, err = false) {
  if (!E.save) return;
  E.save.textContent = text;
  E.save.classList.toggle("err", err);
}
async function flushSave() {
  clearTimeout(S.saveTimer);
  if (!S.dirty || !S.deck) return;
  const id = S.deck.id;
  S.dirty = false;
  try {
    await sendJSON(`/api/decks/${id}/notes`, "PUT", { notes: S.notes });
    if (!S.dirty) setSaveState("All changes saved");
  } catch (e) {
    S.dirty = true;
    setSaveState("Couldn't save. Retrying…", true);
    S.saveTimer = setTimeout(flushSave, 4000);
  }
}

function updateDot(n) {
  const dot = $(`.film button[data-n="${n}"] .state`);
  if (!dot) return;
  const has = !!(S.notes[n] || "").trim();
  dot.classList.toggle("has", has);
  dot.replaceChildren(has ? icon("check") : "");
  dot.title = has ? "Has narration" : "No notes: this slide will be silent";
}

function updateStats() {
  const text = S.notes[S.cur] || "";
  const w = words(text), speed = Number(S.settings.speed) || 1;
  E.words.textContent = `${w} word${w === 1 ? "" : "s"}`;
  E.dur.textContent = w ? `≈ ${fmtDur((w / (150 * speed)) * 60)} spoken` : "silent slide";
}

function selectSlide(n, focus = false) {
  const slides = S.deck.slides;
  const idx = slides.findIndex((s) => s.n === n);
  if (idx < 0) return;
  stopAudio();
  S.cur = n;
  const s = slides[idx];
  E.img.src = imgUrl(n);
  E.img.alt = `Slide ${n}: ${s.title || "Untitled"}`;
  E.count.textContent = `${idx + 1} / ${slides.length}`;
  E.prev.disabled = idx === 0; E.next.disabled = idx === slides.length - 1;
  E.noteTitle.textContent = `Narration for slide ${n}`;
  E.noteSub.textContent = s.title || "";
  E.ta.value = S.notes[n] || "";
  E.ta.setAttribute("aria-label", `Narration for slide ${n}`);
  E.slideText.hidden = !s.text;
  E.slideTextBody.textContent = s.text || "";
  $$(".film button").forEach((b) => b.setAttribute("aria-current", String(Number(b.dataset.n) === n)));
  const active = $(`.film button[data-n="${n}"]`);
  active?.scrollIntoView({ block: "nearest", inline: "nearest" });
  updateStats();
  if (focus) E.ta.focus();
}
function step(delta) {
  const slides = S.deck.slides;
  const idx = slides.findIndex((s) => s.n === S.cur) + delta;
  if (idx >= 0 && idx < slides.length) selectSlide(slides[idx].n);
}

function aiAvailable() {
  if (S.health?.llm) return true;
  toast("Notes AI isn't set up. Opening Services…", "info", 2500);
  openStatus();
  return false;
}
async function runAi(slideNums) {
  if (S.aiBusy || !aiAvailable()) return;
  S.aiBusy = true;
  [E.aiAll, E.aiOne].forEach((b) => (b.disabled = true));
  try {
    const { job_id } = await sendJSON(`/api/decks/${S.deck.id}/suggest-notes`, "POST", { notes: S.notes, slides: slideNums, language: isAlbanian(S.settings.voice) ? "Albanian" : null });
    const res = await runJob(job_id, (j) => setSaveState(j.step));
    const written = Object.entries(res.notes || {});
    for (const [n, text] of written) { S.notes[n] = text; updateDot(n); }
    E.ta.value = S.notes[S.cur] || "";
    updateStats();
    if (written.length) { scheduleSave(); toast(`Wrote notes for ${written.length} slide${written.length === 1 ? "" : "s"}. Read them over before exporting.`, "ok"); }
    else toast("Every slide already has notes.", "info");
    const failed = Object.keys(res.errors || {}).length;
    if (failed) toast(`${failed} slide${failed === 1 ? "" : "s"} could not be written. Try again.`, "error");
    if (!written.length) setSaveState(S.dirty ? "Saving…" : "All changes saved");
  } catch (e) {
    toast(e.message, "error", 7000);
    setSaveState("");
  } finally {
    S.aiBusy = false;
    [E.aiAll, E.aiOne].forEach((b) => (b.disabled = false));
  }
}

function renderScript() {
  const d = S.deck;
  showView("script", d.id);
  const root = $("#view-script");
  E = {};

  E.title = h("input", { class: "title-input", value: d.name, "aria-label": "Deck title", maxlength: "120" });
  E.title.addEventListener("change", async () => {
    const name = E.title.value.trim();
    if (!name) { E.title.value = d.name; return; }
    try { const r = await sendJSON(`/api/decks/${d.id}`, "PATCH", { name }); d.name = r.name; E.title.value = r.name; }
    catch (e) { toast(e.message, "error"); }
  });
  E.title.addEventListener("keydown", (e) => { if (e.key === "Enter") E.title.blur(); });
  E.save = h("span", { class: "save-state", role: "status" }, "");
  E.aiAll = h("button", { class: "btn", type: "button", onclick: () => runAi(null) }, icon("sparkles"), "Write missing notes");
  const toExport = h("a", { class: "btn primary", href: `#/deck/${d.id}/export` }, "Voice & export", icon("right"));

  // filmstrip
  E.film = h("ul", { class: "film", "aria-label": "Slides" }, d.slides.map((s) => {
    const btn = h("button", { type: "button", "data-n": s.n, "aria-label": `Slide ${s.n}: ${s.title || "Untitled"}`, onclick: () => selectSlide(s.n, false) },
      h("img", { src: imgUrl(s.n), alt: "", loading: "lazy" }),
      h("div", { class: "cap" }, h("span", { class: "state" }), h("b", {}, s.n), h("span", { class: "t" }, s.title || "Untitled")));
    return h("li", {}, btn);
  }));

  // stage
  E.img = h("img", { alt: "" });
  E.prev = h("button", { type: "button", "aria-label": "Previous slide", onclick: () => step(-1) }, icon("chevL"));
  E.next = h("button", { type: "button", "aria-label": "Next slide", onclick: () => step(1) }, icon("chevR"));
  E.count = h("span", { class: "slide-count" });
  const frame = h("div", { class: "slide-frame" }, E.img, h("div", { class: "slide-nav" }, E.prev, E.next), E.count);

  E.noteTitle = h("h2", {});
  E.noteSub = h("span", { class: "muted" });
  E.ta = h("textarea", { class: "notes-input", rows: "6", placeholder: "Type what should be said over this slide. Leave empty for a silent slide." });
  E.ta.addEventListener("input", () => { S.notes[S.cur] = E.ta.value; updateStats(); updateDot(S.cur); scheduleSave(); });
  E.words = h("span"); E.dur = h("span");
  const previewLabel = "Preview voice";
  E.preview = h("button", { class: "btn", type: "button" }, icon("play"), previewLabel);
  E.preview.addEventListener("click", () => playPreview(S.notes[S.cur] || "", E.preview, previewLabel));
  E.aiOne = h("button", { class: "btn", type: "button", onclick: () => runAi([S.cur]) }, icon("sparkles"), "Write with AI");
  E.slideTextBody = h("p");
  E.slideText = h("details", { class: "slide-text" }, h("summary", {}, "Text on this slide"), E.slideTextBody);

  const notes = h("div", { class: "notes-card" },
    h("div", { class: "notes-head" }, E.noteTitle, E.noteSub),
    E.ta,
    h("div", { class: "notes-foot" }, h("div", { class: "notes-stats" }, E.words, E.dur), E.preview, E.aiOne),
    E.slideText,
    h("p", { class: "hint" }, "Tip: write the way you speak. Spell out numbers and abbreviations the way they should sound. ",
      h("kbd", {}, "Alt"), "+", h("kbd", {}, "↑"), h("kbd", {}, "↓"), " changes slide."));

  const scriptVoice = h("label", { class: "voice-inline" }, icon("mic"), h("span", { class: "sr-only" }, "Voice"), voiceSelect("script-voice"));
  root.replaceChildren(
    h("div", { class: "page-head" }, E.title, E.save, h("div", { class: "head-actions" }, scriptVoice, E.aiAll, toExport)),
    h("div", { class: "editor" }, E.film, h("div", { class: "stage" }, frame, notes)));

  d.slides.forEach((s) => updateDot(String(s.n)));
  const first = slideByN(S.cur) ? S.cur : d.slides[0].n;
  selectSlide(first);
}

// ---------- export view ----------
function narrationStats() {
  const s = S.settings, speed = Number(s.speed) || 1;
  let narrated = 0, silent = 0, seconds = 0;
  for (const slide of S.deck.slides) {
    const w = words(S.notes[slide.n]);
    if (w) { narrated++; seconds += (w / (150 * speed)) * 60 + Number(s.pause || 0); }
    else { silent++; seconds += Number(s.silent || 0); }
  }
  return { narrated, silent, seconds, total: S.deck.slides.length };
}

function renderExport() {
  const d = S.deck;
  showView("export", d.id);
  const root = $("#view-export");
  const st = S.settings;
  const persist = () => store.set("ns-settings", S.settings);

  const voiceSel = voiceSelect("voice");
  const sampleLabel = "Hear it";
  const sampleBtn = h("button", { class: "btn sm", type: "button" }, icon("play"), sampleLabel);
  sampleBtn.addEventListener("click", () => playPreview(sampleLine(st.voice), sampleBtn, sampleLabel));

  const speedVal = h("span", { class: "range-val" }, `${Number(st.speed).toFixed(2).replace(/0$/, "")}×`);
  const speed = h("input", { type: "range", min: "0.7", max: "1.4", step: "0.05", value: st.speed, id: "speed" });
  speed.addEventListener("input", () => { st.speed = Number(speed.value); speedVal.textContent = `${st.speed.toFixed(2).replace(/0$/, "")}×`; persist(); renderSummary(); });

  const pause = h("input", { type: "number", min: "0", max: "5", step: "0.1", value: st.pause, id: "pause" });
  pause.addEventListener("change", () => { st.pause = clamp(Number(pause.value), 0, 5, 0.8); pause.value = st.pause; persist(); renderSummary(); });
  const silent = h("input", { type: "number", min: "0.5", max: "30", step: "0.5", value: st.silent, id: "silent" });
  silent.addEventListener("change", () => { st.silent = clamp(Number(silent.value), 0.5, 30, 3); silent.value = st.silent; persist(); renderSummary(); });

  const resSeg = h("div", { class: "seg", role: "radiogroup", "aria-label": "Video size" }, [1080, 720].map((r) => {
    const input = h("input", { type: "radio", name: "res", value: r, checked: Number(st.res) === r });
    input.addEventListener("change", () => { st.res = r; persist(); });
    return h("label", {}, input, h("span", {}, r + "p"));
  }));

  const settings = h("div", { class: "card" },
    h("h2", {}, "Voice and timing"),
    h("div", { class: "form-grid" },
      h("div", { class: "field wide" }, h("label", { for: "voice" }, "Voice"),
        h("div", { class: "row-inline" }, voiceSel, sampleBtn,
          h("button", { class: "btn sm", type: "button", onclick: openMyVoices }, icon("mic"), "My voice"))),
      deliveryField(),
      h("div", { class: "field wide" }, h("label", { for: "speed" }, "Speaking speed ", speedVal), speed),
      h("label", { class: "field" }, "Pause after each slide (seconds)", pause),
      h("label", { class: "field" }, "Silent slide length (seconds)", silent),
      h("div", { class: "field wide" }, "Video size", resSeg),
      subsField()));


  function deliveryField() {  // own voices only: how freely the copy plays with the recording's tone
    const STYLES = [["steady", "Steady"], ["natural", "Natural"], ["expressive", "Expressive"]];
    const seg = h("div", { class: "seg", role: "radiogroup", "aria-label": "Delivery" }, STYLES.map(([val, label]) => {
      const input = h("input", { type: "radio", name: "style", value: val, checked: (st.style || "natural") === val });
      input.addEventListener("change", () => { st.style = val; persist(); });
      return h("label", {}, input, h("span", {}, label));
    }));
    const wrap = h("div", { class: "field wide" }, "Delivery", seg,
      h("p", { class: "sub-note" }, "Your voice keeps the feeling you recorded it with. Steady is even and calm; Expressive "
        + "varies more, like live speaking. For a different mood, record another voice in that mood (for example "
        + "\u201cMe \u2013 energetic\u201d). Press Hear it to compare."));
    const sync = () => { wrap.hidden = !isClone(st.voice); };
    sync();
    onVoiceChange(wrap, sync);
    return wrap;
  }

  function subsField() {
    const wrap = h("div", { class: "field wide" });
    const note = h("p", { class: "sub-note" });
    const chips = h("div", { class: "chips", role: "group", "aria-label": "Subtitle languages" });
    const draw = () => {
      const src = voiceLangCode(st.voice);
      const ai = !!S.health?.llm_configured;
      chips.replaceChildren(...SUB_LANGS.map(([code, label]) => {
        const needsAi = code !== src;
        const input = h("input", { type: "checkbox", value: code, checked: st.subs.includes(code), disabled: needsAi && !ai });
        input.addEventListener("change", () => {
          st.subs = SUB_LANGS.map(([c]) => c).filter((c) => c === code ? input.checked : st.subs.includes(c));
          persist(); draw();
        });
        return h("label", { class: "chip" }, input, h("span", {}, label, code === src ? h("small", {}, " original") : null));
      }));
      const extra = st.subs.filter((c) => c !== src).length;
      note.replaceChildren(...(!ai
        ? ["Translating subtitles uses the notes AI, which isn't set up. Only the narration's own language is available. See Services (top right)."]
        : extra
          ? [`${extra} translated subtitle track${extra === 1 ? "" : "s"} will be added to the video and as SRT files. Translation runs on your AI model, so check important wording.`]
          : ["Tick languages to add translated subtitles. You always get subtitles in the narration's own language."]));
    };
    draw();
    onVoiceChange(wrap, draw);
    wrap.append(h("span", {}, "Subtitles"), chips, note);
    return wrap;
  }

  const sum = h("div", { class: "summary" });
  const create = h("button", { class: "btn primary lg", type: "button" }, icon("film"), "Create narrated video");
  const back = h("a", { class: "btn ghost", href: `#/deck/${d.id}/script` }, icon("left"), "Back to script");
  const progress = h("div", { class: "busy", hidden: true, "aria-live": "polite" });
  const errBox = h("p", { class: "error", role: "alert", hidden: true });
  const resultBox = h("section", { class: "result", "aria-label": "Your video", hidden: true });

  function renderSummary() {
    const s = narrationStats();
    sum.replaceChildren(
      h("h2", {}, "Summary"),
      h("dl", {},
        h("dt", {}, "Slides"), h("dd", {}, s.total),
        h("dt", {}, "With narration"), h("dd", {}, s.narrated),
        h("dt", {}, "Silent"), h("dd", {}, s.silent),
        h("dt", {}, "Estimated length"), h("dd", {}, "≈ " + fmtDur(s.seconds))),
      ...(s.narrated === 0 ? [h("div", { class: "warn-box" }, "No slide has notes yet. Go back and write the script, or let AI draft it.")] : []),
      create, back);
    create.disabled = s.narrated === 0 || create.dataset.running === "1";
  }

  create.addEventListener("click", async () => {
    stopAudio();
    errBox.hidden = true;
    create.dataset.running = "1"; create.disabled = true;
    resultBox.hidden = true;
    const started = Date.now();
    const bar = h("div", { class: "fill" }), pct = h("span", { class: "pct" }, "0%"), stepEl = h("p", { class: "muted" }, "Starting…");
    const elapsed = h("span", { class: "muted" }, "0:00");
    progress.replaceChildren(h("div", { class: "busy-top" }, h("span", { class: "spinner" }), h("strong", {}, "Creating your video"), elapsed, pct), h("div", { class: "bar" }, bar), stepEl);
    progress.hidden = false;
    const tick = setInterval(() => (elapsed.textContent = fmtDur((Date.now() - started) / 1000)), 1000);
    try {
      await flushSave();
      const { job_id } = await sendJSON(`/api/decks/${d.id}/render`, "POST", {
        notes: S.notes, voice: st.voice || null, speed: Number(st.speed), pause: Number(st.pause), silent_seconds: Number(st.silent), resolution: Number(st.res), style: st.style || "natural",
        subtitle_languages: (st.subs || []).filter((c) => c === voiceLangCode(st.voice) || S.health?.llm_configured),
      });
      const res = await runJob(job_id, (j) => { bar.style.width = Math.round(j.progress * 100) + "%"; pct.textContent = Math.round(j.progress * 100) + "%"; stepEl.textContent = j.step; });
      for (const w of res?.warnings || []) toast(w, "error", 9000);
      await loadDeckKeepingNotes(d.id);
      progress.hidden = true;
      renderResults(resultBox, true);
      toast("Your video is ready.", "ok");
      resultBox.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      progress.hidden = true;
      errBox.textContent = e.message; errBox.hidden = false;
    } finally {
      clearInterval(tick);
      delete create.dataset.running;
      renderSummary();
    }
  });

  renderSummary();
  root.replaceChildren(
    h("div", { class: "page-head" }, h("h2", { style: "font-size:1.5rem" }, d.name)),
    h("div", { class: "export-grid" }, settings, h("div", { class: "card" }, sum)),
    progress, errBox, resultBox);
  if (d.outputs?.length) renderResults(resultBox, false);
}

function clamp(v, lo, hi, fallback) { return Number.isFinite(v) ? Math.min(hi, Math.max(lo, v)) : fallback; }

async function loadDeckKeepingNotes(id) {
  const keep = S.notes;
  await loadDeck(id);
  S.notes = keep;
}

function renderResults(box, fresh) {
  const d = S.deck, v = d.rendered || Date.now();
  const url = (name, extra = "") => `/api/decks/${d.id}/files/${name}?v=${v}${extra}`;
  const meta = {
    "narrated.mp4": ["film", "Narrated video", "MP4, plays anywhere"],
    "narration.srt": ["subtitles", "Subtitles", "SRT, for YouTube, VLC, PowerPoint"],
    "narration-audio.zip": ["audio", "Audio per slide", "ZIP of MP3 files"],
    "narration-subtitles.zip": ["subtitles", "Subtitles, all languages", "ZIP of SRT files"],
    "deck-with-notes.pptx": ["deck", "Deck with notes", "PPTX with your final notes inside"],
  };
  const order = ["narrated.mp4", "narration.srt", "narration-subtitles.zip", "narration-audio.zip", "deck-with-notes.pptx"];
  const outs = order.map((n) => d.outputs.find((o) => o.name === n)).filter(Boolean);
  const player = h("video", { id: "player", controls: true, preload: "metadata", crossorigin: "anonymous", poster: imgUrl(d.slides[0]?.n ?? 1), src: url("narrated.mp4", "&inline=1") });
  const names = new Set(d.outputs.map((o) => o.name));
  const tracks = SUB_LANGS.filter(([c]) => names.has(`narration.${c}.srt`)).map(([c, label]) => [`narration.${c}.srt`, c, label]);
  const srcCode = voiceLangCode(d.settings?.voice) || "en";
  if (!tracks.some(([, c]) => c === srcCode)) {
    tracks.unshift(["narration.srt", srcCode, (SUB_LANGS.find(([c]) => c === srcCode) || [, "Original"])[1]]);
  }
  tracks.forEach(([file, lang, label]) => player.append(h("track", { kind: "subtitles", src: url(file, "&vtt=1"), srclang: lang, label })));
  box.replaceChildren(
    h("div", { class: "done-banner" }, h("span", { class: "tick" }, icon("check")), fresh ? "Your video is ready" : "Your last video"),
    h("div", { class: "result-grid" },
      player,
      h("ul", { class: "dl-list" }, outs.map((o) => {
        const [ic, title, sub] = meta[o.name] || ["download", o.label, ""];
        const main = o.name === "narrated.mp4";
        return h("li", {}, h("a", { class: `dl${main ? " main" : ""}`, href: url(o.name), download: "" },
          h("span", { class: "ico" }, icon(ic)),
          h("span", { class: "txt" }, h("strong", {}, `${main ? "Download " : ""}${title}`), h("span", {}, `${sub} · ${fmtBytes(o.bytes)}`)),
          icon("download")));
      }))),
    h("p", { class: "hint" }, "Want to change something? Edit the notes or settings and create the video again. To change how a slide looks, edit the deck in PowerPoint and upload it again."));
  box.hidden = false;
}

// ---------- My voices (voice cloning) ----------
const READ_ALOUD = "Hello, and welcome. In this short recording I speak clearly and in my own style, " +
  "so the app can learn how my voice sounds. Thank you for listening, and enjoy the presentation.";

function myVoicesDialog() {
  let dlg = $("#dlg-voice");
  if (!dlg) {
    dlg = h("dialog", { id: "dlg-voice", "aria-labelledby": "dlg-voice-h" },
      h("form", { method: "dialog", class: "dlg-head" }, h("h2", { id: "dlg-voice-h" }, "My voices"),
        h("button", { class: "icon-btn", "aria-label": "Close" }, icon("x"))),
      h("div", { class: "dlg-body", id: "voice-body" }));
    dlg.addEventListener("close", () => { stopRecording(); stopAudio(); });
    document.body.append(dlg);
  }
  return dlg;
}

let rec = null; // { recorder, stream, chunks, timer }
function stopRecording() {
  if (!rec) return;
  clearInterval(rec.timer);
  if (rec.recorder.state !== "inactive") rec.recorder.stop();
  rec.stream.getTracks().forEach((t) => t.stop());
  rec = null;
}

async function openMyVoices() {
  const dlg = myVoicesDialog();
  if (!dlg.open) dlg.showModal();
  const body = $("#voice-body");
  body.replaceChildren(h("p", { class: "muted" }, "Checking…"));
  await refreshHealth();
  const hl = S.health || {};
  if (hl.clone == null && hl.clone_native) {
    body.replaceChildren(
      h("p", {}, "Your voice service on this Mac isn't running."),
      h("p", { class: "muted", style: "margin-top:10px" }, "Start it in Terminal, in the narrated-slides folder. It keeps running in the background, even after you close Terminal:"),
      h("pre", { class: "codeblock" }, "./scripts/run-cloner-mac.sh start"),
      h("p", { class: "muted" }, "Wait about 30 seconds for the model to load, then reopen this window. Check it with ./scripts/run-cloner-mac.sh status."));
    return;
  }
  if (hl.clone == null) {
    body.replaceChildren(
      h("p", {}, "Voice cloning makes narration in your own voice from about 10 seconds of English speech. It runs on this computer, and your recording never leaves it."),
      h("p", { class: "muted", style: "margin-top:10px" }, "It is an optional add-on. Start it once in Terminal, in the narrated-slides folder. The first start downloads the model (2.5 GB in Docker):"),
      h("pre", { class: "codeblock" }, "docker compose --profile clone up -d --build"),
      h("p", { class: "muted" }, "On an Apple Silicon Mac, it's much faster on the Mac's GPU: run ./scripts/run-cloner-mac.sh, and add CLONE_TTS_URL=http://host.docker.internal:8890 to .env on its own line, then docker compose up -d narrator."),
      h("p", { class: "muted" }, "Then reopen this window."));
    return;
  }
  await loadMyVoices();
  const list = h("ul", { class: "myv-list" }, S.myVoices.map((v) => {
    const del = h("button", { class: "btn sm ghost", type: "button" }, icon("trash"), "Delete");
    del.addEventListener("click", async () => {
      if (del.dataset.armed !== "1") { del.dataset.armed = "1"; del.replaceChildren("Delete for good?"); setTimeout(() => { if (del.isConnected) { delete del.dataset.armed; del.replaceChildren(icon("trash"), "Delete"); } }, 3000); return; }
      try {
        await api(`/api/my-voices/${v.id}`, { method: "DELETE" });
        if (S.settings.voice === v.id) { S.settings.voice = S.defaultVoice; store.set("ns-settings", S.settings); }
        await loadVoices(); refreshVoicePickers(); openMyVoices();
      } catch (e) { toast(e.message, "error"); }
    });
    const use = h("button", { class: "btn sm", type: "button" }, "Use");
    use.addEventListener("click", () => {
      S.settings.voice = v.id; store.set("ns-settings", S.settings); refreshVoicePickers();
      toast(`Using ${v.name}.`, "ok", 2500); dlg.close();
    });
    return h("li", {}, h("span", { class: "myv-ico" }, icon("mic")),
      h("span", { class: "myv-name" }, h("strong", {}, v.name), h("small", {}, `${v.seconds} s sample` + (v.has_transcript ? " · with transcript" : ""))), use, del);
  }));
  const status = hl.clone ? null : h("div", { class: "warn-box" }, "The cloning model is still loading (the first start downloads it). You can add your voice now; it will speak once the model is ready.");

  // --- add form ---
  let blob = null, blobName = "recording.webm";
  const name = h("input", { type: "text", maxlength: "40", placeholder: "e.g. My lecture voice", id: "myv-name" });
  const recBtn = h("button", { class: "btn", type: "button" }, icon("mic"), "Record");
  const recTime = h("span", { class: "muted rec-time" });
  const fileIn = h("input", { type: "file", accept: "audio/*,video/*,.mp4,.mov,.m4a,.mp3,.wav", hidden: true });
  const upBtn = h("button", { class: "btn ghost", type: "button", onclick: () => fileIn.click() }, icon("upload"), "Upload audio or video");
  const startIn = h("input", { type: "number", min: "0", step: "0.5", value: "0", id: "myv-start" });
  const startField = h("label", { class: "field", hidden: true, style: "margin-top:12px" },
    "Start at (seconds): skip music or an intro, then 20 seconds are used", startIn);
  let player = h("audio", { controls: true, hidden: true, class: "myv-player" });
  const transcriptIn = h("textarea", { rows: "2", maxlength: "1000", id: "myv-transcript",
    placeholder: "Type exactly what is said in the clip" });
  const transcriptField = h("label", { class: "field", style: "margin-top:12px" },
    "What is said in the clip (makes the copy of your voice much closer)", transcriptIn);
  const consent = h("input", { type: "checkbox", id: "myv-consent" });
  const save = h("button", { class: "btn primary", type: "button", disabled: true }, icon("check"), "Save voice");
  const err = h("p", { class: "error", hidden: true });
  const ready = () => { save.disabled = !(blob && name.value.trim() && consent.checked); };
  const setBlob = (b, fname) => {
    blob = b; blobName = fname;
    if (player.src) URL.revokeObjectURL(player.src);
    const isVideo = (b.type || "").startsWith("video/") || /\.(mp4|mov|m4v|webm)$/i.test(fname) && !/^recording/.test(fname);
    const next = h(isVideo ? "video" : "audio", { controls: true, class: "myv-player", playsinline: true });
    player.replaceWith(next); player = next;
    player.src = URL.createObjectURL(b); ready();
  };
  fileIn.addEventListener("change", () => {
    const f = fileIn.files[0];
    if (f) { setBlob(f, f.name); startField.hidden = false; startIn.value = "0"; transcriptIn.value = ""; }
    fileIn.value = "";
  });
  startIn.addEventListener("input", () => { if (player.src && !player.hidden) player.currentTime = Number(startIn.value) || 0; });
  name.addEventListener("input", ready); consent.addEventListener("change", ready);

  recBtn.addEventListener("click", async () => {
    if (rec) { stopRecording(); return; }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { toast("This browser can't record here. Upload a clip instead.", "error"); return; }
    let stream;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: true } }); }
    catch { toast("Microphone access was blocked. Allow it in the browser, or upload a clip.", "error"); return; }
    const recorder = new MediaRecorder(stream);
    const chunks = [];
    recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    startField.hidden = true; startIn.value = "0";
    recorder.onstop = () => {
      recBtn.replaceChildren(icon("mic"), "Record again");
      if (chunks.length) {
        setBlob(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }), "recording.webm");
        transcriptIn.value = READ_ALOUD;  // edit it if you said something different
      }
    };
    const started = Date.now();
    rec = { recorder, stream, chunks, timer: setInterval(() => {
      const sec = (Date.now() - started) / 1000;
      recTime.textContent = `${sec.toFixed(0)} s` + (sec < 8 ? " (keep going)" : " (good, stop when done)");
      if (sec >= 20) stopRecording();
    }, 250) };
    recorder.start();
    recBtn.replaceChildren(icon("stop"), "Stop");
    recTime.textContent = "0 s";
  });

  save.addEventListener("click", async () => {
    err.hidden = true; save.disabled = true; save.replaceChildren(h("span", { class: "spinner" }), "Saving…");
    const fd = new FormData();
    fd.append("name", name.value.trim()); fd.append("consent", "true"); fd.append("file", blob, blobName);
    fd.append("start", String(Math.max(0, Number(startIn.value) || 0)));
    fd.append("transcript", transcriptIn.value.trim());
    try {
      const v = await (await api("/api/my-voices", { method: "POST", body: fd })).json();
      S.settings.voice = v.id; store.set("ns-settings", S.settings);
      await loadVoices(); refreshVoicePickers();
      toast(`Saved "${v.name}". It's selected now; press Hear it to listen.`, "ok", 6000);
      dlg.close();
    } catch (e) {
      err.textContent = e.message; err.hidden = false; save.disabled = false; save.replaceChildren(icon("check"), "Save voice");
    }
  });

  body.replaceChildren(
    ...(status ? [status] : []),
    ...(S.myVoices.length ? [h("h3", {}, "Saved voices"), list] : []),
    h("h3", {}, S.myVoices.length ? "Add another voice" : "Add your voice"),
    h("ol", { class: "guide" },
      h("li", {}, "Find a quiet room and hold the microphone at a normal distance."),
      h("li", {}, "Press ", h("strong", {}, "Record"), " and read this aloud (10 to 20 seconds), with the feeling you want in "
        + "your videos: your copied voice keeps it. Calm for lectures, warm and lively for intros. You can also say your own "
        + "words; then type them in the box below.",
        h("blockquote", { class: "read-aloud" }, READ_ALOUD)),
      h("li", {}, "Listen back, give it a name, and save. You can also upload a video or audio file of you speaking English (for example a saved reel): pick a part with only your voice, no music.")),
    h("div", { class: "row-inline rec-row" }, recBtn, upBtn, recTime, fileIn),
    player,
    startField,
    transcriptField,
    h("label", { class: "field", style: "margin-top:14px" }, "Name", name),
    h("label", { class: "consent" }, consent,
      h("span", {}, "This is my own voice, or I have the speaker's permission to clone it.")),
    err,
    h("div", { class: "myv-actions" }, save),
    h("p", { class: "muted small" }, "Cloned voices speak English. Recordings stay on this computer in the cloner's voices volume; delete them here any time."));
}

$("#pill-myvoice")?.addEventListener("click", () => openMyVoices());

// ---------- keyboard ----------
document.addEventListener("keydown", (e) => {
  if ($("#view-script").hidden || !S.deck || document.querySelector("dialog[open]")) return;
  if (e.altKey && (e.key === "ArrowUp" || e.key === "ArrowLeft")) { e.preventDefault(); step(-1); }
  else if (e.altKey && (e.key === "ArrowDown" || e.key === "ArrowRight")) { e.preventDefault(); step(1); }
  else if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); E.preview?.click(); }
});
window.addEventListener("beforeunload", () => { if (S.dirty) flushSave(); });

// ---------- boot ----------
hydrateIcons();
refreshHealth();
setInterval(() => { if (!document.hidden) refreshHealth(); }, 20000);
route();
