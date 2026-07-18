const $ = (id) => document.getElementById(id);

async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
  const resp = await fetch(path, opts);
  let data = null;
  try { data = await resp.json(); } catch { /* non-JSON body, e.g. plain-text 500 */ }
  if (!resp.ok) {
    throw (data && data.error) || {
      message: `Server error (HTTP ${resp.status})`,
      hint: "Check the server console for details.",
    };
  }
  return data;
}

function setStatus(text, isError) {
  const el = $("status");
  el.textContent = text;
  el.className = isError ? "error" : "muted";
}

async function checkHealth() {
  try {
    const h = await api("/api/health");
    $("health").textContent = h.ok
      ? `Audio toolchain ready — ${h.fluidsynth}${h.ffmpeg ? ", ffmpeg present" : ""}`
      : "Audio toolchain incomplete — run scripts/check_env.py for setup steps.";
  } catch {
    $("health").textContent = "Could not reach the server.";
  }
}

async function generate() {
  const button = $("generate");
  if (button.disabled) return; // Enter key / auto-repeat must respect busy state
  button.disabled = true;
  try {
    setStatus("Fetching and parsing chords…");
    const song = await api("/api/songs", { url: $("url").value.trim() });

    setStatus(`Rendering “${song.title}” — this takes a few seconds…`);
    const r = await api(`/api/songs/${song.id}/render`, {});

    $("song-title").textContent = `${song.title} — ${song.artist}`;
    $("song-meta").textContent =
      `Key ${r.sounding_key}` +
      (song.capo ? ` (chart in ${song.key}, capo ${song.capo})` : "") +
      ` · ${Math.round(r.bpm)} BPM`;
    $("player").src = r.wav_url;
    $("dl-midi").href = r.midi_url;
    $("dl-wav").href = r.wav_url;
    $("dl-mp3").classList.toggle("hidden", !r.mp3_url);
    if (r.mp3_url) $("dl-mp3").href = r.mp3_url;
    $("sheet").textContent = song.sheet_text;
    $("song-card").classList.remove("hidden");
    $("sheet-card").classList.remove("hidden");
    $("player").play().catch(() => {});
    setStatus(r.cached ? "Ready (cached render)." : `Ready — rendered in ${r.render_seconds}s.`);
  } catch (err) {
    setStatus(`${err.message}${err.hint ? " — " + err.hint : ""}`, true);
  } finally {
    button.disabled = false;
  }
}

$("generate").addEventListener("click", generate);
$("url").addEventListener("keydown", (e) => { if (e.key === "Enter") generate(); });
checkHealth();
