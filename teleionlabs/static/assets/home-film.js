// The home film: starts with the sound off, as browsers require. The Sound button turns it on; the player's own controls show on hover.
// With no script, the video keeps its native controls.
(() => {
  const v = document.getElementById("film");
  const b = document.querySelector('[data-film="sound"]');
  if (!v || !b) return;
  const wrap = v.parentElement;
  let keep = !matchMedia("(hover:hover)").matches; // No hover on a phone: the player's controls stay, and hide themselves as it plays.
  const show = (on) => { v.controls = keep || on; };
  const stay = () => { keep = true; show(true); };
  const label = () => { b.textContent = v.muted ? b.dataset.on : b.dataset.off; b.setAttribute("aria-pressed", String(!v.muted)); };
  b.addEventListener("click", () => { v.muted = !v.muted; if (v.paused) v.play().catch(stay); });
  v.addEventListener("volumechange", label);
  v.addEventListener("ended", stay);
  wrap.addEventListener("mouseenter", () => show(true));
  wrap.addEventListener("mouseleave", () => show(false));
  addEventListener("keydown", (e) => { if (e.key === "Tab") stay(); });
  b.hidden = false;
  label();
  show(false);
  if (matchMedia("(prefers-reduced-motion:reduce)").matches) { v.pause(); stay(); return; }
  if (v.paused) v.play().catch(stay);
})();
