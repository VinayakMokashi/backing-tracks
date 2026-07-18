const $ = (id) => document.getElementById(id);

const NOTE_PC = { C: 0, "C#": 1, Db: 1, D: 2, "D#": 3, Eb: 3, E: 4, F: 5,
  "F#": 6, Gb: 6, G: 7, "G#": 8, Ab: 8, A: 9, "A#": 10, Bb: 10, B: 11 };
const KEY_NAMES = ["C", "C#/Db", "D", "Eb", "E", "F", "F#/Gb", "G", "Ab", "A", "Bb", "B"];

const state = { song: null, transpose: 0, baseSoundingPc: 0 };

async function api(path, { method = "GET", body } = {}) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch(path, opts);
  let data = null;
  try { data = await resp.json(); } catch { /* non-JSON error body */ }
  if (!resp.ok) {
    throw (data && data.error) || {
      message: `Server error (HTTP ${resp.status})`,
      hint: "Check the server console for details.",
    };
  }
  return data;
}

function status(el, text, isError) {
  el.textContent = text || "";
  el.className = isError ? "error" : "muted";
}

function pcOf(keySymbol) {
  const m = /^([A-G][#b]?)/.exec(keySymbol || "");
  return m ? (NOTE_PC[m[1]] ?? 0) : 0;
}

function wrap12(n) {
  let t = ((n % 12) + 12) % 12;
  return t > 6 ? t - 12 : t;
}

// ---- Health ----
async function checkHealth() {
  try {
    const h = await api("/api/health");
    $("health").textContent = h.ok
      ? `Audio ready — ${h.fluidsynth}${h.ffmpeg ? " · ffmpeg" : " · WAV only"}`
      : "Audio toolchain incomplete — run scripts/check_env.py.";
  } catch { $("health").textContent = "Could not reach the server."; }
}

// ---- Find / search / paste ----
async function find() {
  const q = $("find").value.trim();
  if (!q) return;
  $("results").classList.add("hidden");
  try {
    if (/^https?:\/\//i.test(q)) {
      status($("status"), "Fetching chords…");
      await loadSong(await api("/api/songs", { method: "POST", body: { url: q } }));
    } else {
      status($("status"), "Searching…");
      const { results } = await api(`/api/search?q=${encodeURIComponent(q)}`);
      renderResults(results);
    }
  } catch (err) { showError($("status"), err); }
}

function renderResults(results) {
  const box = $("results");
  box.innerHTML = "";
  if (!results.length) { status($("status"), "No chord charts found — try paste.", true); return; }
  status($("status"), "");
  for (const r of results) {
    const div = document.createElement("div");
    div.className = "result";
    div.innerHTML = `<span class="title">${r.title} — ${r.artist}</span>` +
      `<span class="meta">★ ${r.rating} · ${r.votes} votes · v${r.version}</span>`;
    div.onclick = async () => {
      box.classList.add("hidden");
      status($("status"), "Fetching chords…");
      try { await loadSong(await api("/api/songs", { method: "POST", body: { url: r.url } })); }
      catch (err) { showError($("status"), err); }
    };
    box.appendChild(div);
  }
  box.classList.remove("hidden");
}

async function usePaste() {
  const text = $("paste-text").value.trim();
  if (!text) return;
  status($("status"), "Parsing…");
  try {
    await loadSong(await api("/api/songs", { method: "POST", body: {
      paste: text, title: $("paste-title").value.trim(),
      artist: $("paste-artist").value.trim() } }));
    $("paste-box").classList.add("hidden");
  } catch (err) { showError($("status"), err); }
}

function showError(el, err) {
  status(el, `${err.message}${err.hint ? " — " + err.hint : ""}`, true);
  if (err.code === "source_unreachable" || err.code === "unsupported_source" ||
      err.code === "parse_failed") {
    $("paste-box").classList.remove("hidden");
  }
}

// ---- Song loaded ----
async function loadSong(song) {
  state.song = song;
  status($("status"), "");
  $("song-title").textContent = `${song.title}${song.artist ? " — " + song.artist : ""}`;
  $("style").value = song.style;
  $("timesig").value = song.time_signature.join("/");
  $("capo").value = song.capo;
  updateBpmField();
  $("guitar-program").value = "25";
  buildKeySelect();
  await resetBaseline();
  $("workspace").classList.remove("hidden");
  $("player-card").classList.add("hidden");
  await refreshLibrary();
}

function updateBpmField() {
  const sixEight = $("timesig").value === "6/8";
  $("bpm-label").firstChild.textContent = sixEight ? "Tempo (dotted-¼)" : "Tempo (BPM)";
  $("bpm").value = Math.round(sixEight ? state.song.bpm / 1.5 : state.song.bpm);
}

function buildKeySelect() {
  const sel = $("key");
  sel.innerHTML = "";
  KEY_NAMES.forEach((name, pc) => {
    const opt = document.createElement("option");
    opt.value = pc; opt.textContent = name;
    sel.appendChild(opt);
  });
}

// Re-anchor transpose baseline to the song's original sounding key.
async function resetBaseline() {
  state.transpose = 0;
  const sheet = await api(`/api/songs/${state.song.id}/sheet?transpose=0&capo_mode=${$("capo-mode").value}`);
  state.baseSoundingPc = pcOf(sheet.sounding_key);
  applySheet(sheet);
  syncKeyControls();
}

function syncKeyControls() {
  $("tr-value").textContent = (state.transpose > 0 ? "+" : "") + state.transpose;
  $("key").value = ((state.baseSoundingPc + state.transpose) % 12 + 12) % 12;
}

async function updateSheet() {
  try {
    const sheet = await api(`/api/songs/${state.song.id}/sheet?transpose=${state.transpose}&capo_mode=${$("capo-mode").value}`);
    applySheet(sheet);
  } catch (err) { showError($("gen-status"), err); }
}

function applySheet(sheet) {
  $("sheet").innerHTML = sheet.sheet_html;
  const badge = sheet.capo ? `Play in ${sheet.shape_key} · Capo ${sheet.capo} · sounds in ${sheet.sounding_key}`
                           : `Key of ${sheet.sounding_key}`;
  $("sheet-badge").textContent = badge;
}

// ---- Editing (PATCH) ----
async function patchSong(fields) {
  try {
    state.song = await api(`/api/songs/${state.song.id}`, { method: "PATCH", body: fields });
    markStale();
    await resetBaseline();
  } catch (err) { showError($("gen-status"), err); }
}

function markStale() {
  $("player-card").classList.add("hidden");
  status($("gen-status"), "Settings changed — press Generate.");
}

// ---- Generate ----
async function generate() {
  const btn = $("generate");
  if (btn.disabled) return;
  if (!$("guitar").checked && !$("piano").checked) {
    status($("gen-status"), "Enable at least Guitar or Piano.", true);
    return;
  }
  btn.disabled = true;
  status($("gen-status"), "Rendering…");
  $("gen-status").classList.add("spin");
  try {
    const r = await api(`/api/songs/${state.song.id}/render`, { method: "POST", body: {
      transpose: state.transpose,
      guitar: $("guitar").checked, piano: $("piano").checked,
      drums: $("drums").checked, count_in: $("count-in").checked,
      guitar_program: parseInt($("guitar-program").value, 10),
      capo_mode: $("capo-mode").value,
    } });
    $("player-meta").textContent =
      `Key ${r.sounding_key} · ${Math.round(r.bpm)} BPM` +
      (r.cached ? " · cached" : ` · rendered in ${r.render_seconds}s`);
    $("player").src = r.wav_url;
    $("dl-midi").href = r.midi_url;
    $("dl-wav").href = r.wav_url;
    $("dl-mp3").classList.toggle("hidden", !r.mp3_url);
    if (r.mp3_url) $("dl-mp3").href = r.mp3_url;
    $("player-card").classList.remove("hidden");
    $("player").play().catch(() => {});
    status($("gen-status"), "");
  } catch (err) { showError($("gen-status"), err); }
  finally { btn.disabled = false; $("gen-status").classList.remove("spin"); }
}

// ---- Library ----
async function refreshLibrary() {
  try {
    const { songs } = await api("/api/songs");
    const sel = $("library");
    sel.innerHTML = '<option value="">Saved songs…</option>';
    for (const s of songs) {
      const opt = document.createElement("option");
      opt.value = s.id; opt.textContent = `${s.title}${s.artist ? " — " + s.artist : ""}`;
      sel.appendChild(opt);
    }
  } catch { /* library is best-effort */ }
}

// ---- Wire up ----
$("find-btn").onclick = find;
$("find").addEventListener("keydown", (e) => { if (e.key === "Enter") find(); });
$("paste-toggle").onclick = () => $("paste-box").classList.toggle("hidden");
$("paste-btn").onclick = usePaste;
$("generate").onclick = generate;
$("library").onchange = async (e) => {
  if (!e.target.value) return;
  try { await loadSong(await api(`/api/songs/${e.target.value}`)); }
  catch (err) { showError($("status"), err); }
};

$("style").onchange = () => patchSong({ style: $("style").value });
$("capo").onchange = () => patchSong({ capo: parseInt($("capo").value, 10) || 0 });
$("bpm").onchange = () => {
  const raw = parseFloat($("bpm").value);
  if (!raw) return;
  patchSong({ bpm: $("timesig").value === "6/8" ? raw * 1.5 : raw });
};
$("timesig").onchange = () => {
  const [n, d] = $("timesig").value.split("/").map(Number);
  patchSong({ time_signature: [n, d] });
};

$("capo-mode").onchange = () => updateSheet().then(syncKeyControls);
$("tr-up").onclick = () => { if (state.transpose < 6) { state.transpose++; syncKeyControls(); updateSheet(); } };
$("tr-down").onclick = () => { if (state.transpose > -6) { state.transpose--; syncKeyControls(); updateSheet(); } };
$("key").onchange = () => {
  state.transpose = wrap12(parseInt($("key").value, 10) - state.baseSoundingPc);
  syncKeyControls();
  updateSheet();
};

checkHealth();
refreshLibrary();
