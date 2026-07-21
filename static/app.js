const $ = (id) => document.getElementById(id);
const KEY_NAMES = ["C", "C#/Db", "D", "D#/Eb", "E", "F", "F#/Gb", "G", "G#/Ab", "A", "A#/Bb", "B"];
const NOTE_PC = { C: 0, "C#": 1, Db: 1, D: 2, "D#": 3, Eb: 3, E: 4, F: 5,
  "F#": 6, Gb: 6, G: 7, "G#": 8, Ab: 8, A: 9, "A#": 10, Bb: 10, B: 11 };

const state = { meta: null };

async function api(path, body) {
  const resp = await fetch(path, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data = null;
  try { data = await resp.json(); } catch { /* non-JSON */ }
  if (!resp.ok) throw (data && data.error) ||
    { message: `Server error (HTTP ${resp.status})`, hint: "" };
  return data;
}

function status(el, text, isError) {
  el.textContent = text || "";
  el.className = isError ? "error" : "muted";
}

function pcOf(key) {
  const m = /^([A-G][#b]?)/.exec(key || "");
  return m ? (NOTE_PC[m[1]] ?? 0) : 0;
}
function shortest(from, to) {
  const d = ((to - from) % 12 + 12) % 12;
  return d > 6 ? d - 12 : d;
}

async function analyze() {
  const btn = $("analyze");
  if (btn.disabled) return;
  const url = $("url").value.trim();
  if (!url) return;
  btn.disabled = true;
  status($("status"), "Downloading & analyzing the audio… (can take up to a minute)");
  $("status").classList.add("spin");
  try {
    const meta = await api("/api/audio/analyze", { url });
    state.meta = meta;
    $("track-title").textContent = meta.title || "Track";
    $("detected-key").textContent = meta.key;
    $("detected-conf").textContent = meta.confidence + " confidence";
    buildTargets(meta);
    $("keys").classList.remove("hidden");
    $("result").classList.add("hidden");
    status($("status"), "");
  } catch (err) {
    status($("status"), `${err.message}${err.hint ? " — " + err.hint : ""}`, true);
  } finally {
    btn.disabled = false;
    $("status").classList.remove("spin");
  }
}

function buildTargets(meta) {
  const sel = $("target");
  sel.innerHTML = "";
  const suffix = meta.minor ? "m" : "";
  KEY_NAMES.forEach((name, pc) => {
    const opt = document.createElement("option");
    opt.value = pc;
    opt.textContent = name.replace(/\//g, suffix + " / ") + suffix;
    if (pc === meta.pitch_class) opt.textContent += "  (original)";
    sel.appendChild(opt);
  });
  sel.value = meta.pitch_class;
  updateShift();
}

function updateShift() {
  const n = shortest(state.meta.pitch_class, parseInt($("target").value, 10));
  $("shift-readout").textContent =
    n === 0 ? "no change" : `${n > 0 ? "+" : ""}${n} semitone${Math.abs(n) === 1 ? "" : "s"}`;
}

async function make() {
  const btn = $("make");
  if (btn.disabled) return;
  btn.disabled = true;
  status($("make-status"), "Shifting the audio…");
  $("make-status").classList.add("spin");
  try {
    const targetName = KEY_NAMES[parseInt($("target").value, 10)].split("/")[0];
    const r = await api("/api/audio/transpose", { id: state.meta.id, target: targetName });
    $("result-meta").textContent =
      `${r.from_key} → ${r.to_key}  (${r.semitones > 0 ? "+" : ""}${r.semitones} semitones)`;
    $("player").src = r.audio_url;
    $("dl").href = r.audio_url;
    $("result").classList.remove("hidden");
    $("player").play().catch(() => {});
    status($("make-status"), "");
  } catch (err) {
    status($("make-status"), `${err.message}${err.hint ? " — " + err.hint : ""}`, true);
  } finally {
    btn.disabled = false;
    $("make-status").classList.remove("spin");
  }
}

$("analyze").onclick = analyze;
$("url").addEventListener("keydown", (e) => { if (e.key === "Enter") analyze(); });
$("target").onchange = updateShift;
$("make").onclick = make;
