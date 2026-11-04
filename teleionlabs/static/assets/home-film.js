// The home film: starts with the sound off, as browsers require. The Sound button turns it on; the player's own controls show on hover.
// With no script, the video keeps its native controls.
(() => {
  const still = matchMedia("(prefers-reduced-motion:reduce)").matches;
  if (still) document.querySelectorAll("video").forEach((x) => { x.autoplay = false; x.pause(); });
  const v = document.getElementById("film");
  const b = document.querySelector('[data-film="sound"]');
  if (!v || !b) return;
  const wrap = v.parentElement;
  let keep = !matchMedia("(hover:hover)").matches; // No hover on a phone: the player's controls stay, and hide themselves as it plays.
  let started = false; // Until the film moves, the controls stay: on a slow first load they carry the spinner and a way to press play.
  const show = (on) => { v.controls = keep || !started || on; };
  const stay = () => { keep = true; show(true); };
  const label = () => { b.textContent = v.muted ? b.dataset.on : b.dataset.off; b.setAttribute("aria-pressed", String(!v.muted)); };
  b.addEventListener("click", () => { v.muted = !v.muted; if (v.paused) v.play().catch(stay); });
  v.addEventListener("volumechange", label);
  v.addEventListener("ended", stay);
  v.addEventListener("playing", () => { if (!started) { started = true; show(wrap.matches(":hover")); } });
  // A failed load gets two more tries, then the controls and the download link stay.
  const src = v.querySelector("source");
  let tries = 0;
  if (src) src.addEventListener("error", () => { if (tries++ < 2) setTimeout(() => { v.load(); if (!still) v.play().catch(stay); }, 1500); else stay(); });
  wrap.addEventListener("mouseenter", () => show(true));
  wrap.addEventListener("mouseleave", () => show(false));
  addEventListener("keydown", (e) => { if (e.key === "Tab") stay(); });
  const c = document.querySelector('[data-film="captions"]');
  if (c && v.textTracks[0]) {
    const t = v.textTracks[0];
    const cap = () => { const on = t.mode === "showing"; c.textContent = on ? c.dataset.off : c.dataset.on; c.setAttribute("aria-pressed", String(on)); };
    c.addEventListener("click", () => { t.mode = t.mode === "showing" ? "hidden" : "showing"; cap(); });
    v.textTracks.addEventListener("change", cap);
    c.hidden = false;
    cap();
  }
  b.hidden = false;
  label();
  show(false);
  if (still) { stay(); return; }
  if (v.paused) v.play().catch(stay);
})();
