// The page a person sees when an agent sends them a link: plain text, one answer. Tessera keeps the state; this Worker
// only renders it. The token travels to Tessera in a header, never in a URL Tessera would log.
import { LINK_COPY as T, TEXT_CSS, TEXT_CSS_HASH } from "./text.generated.js";

const TOKEN = /^[A-Za-z0-9_-]{32,128}$/;
const API = "https://tessera.teleionlabs.com/v1/human-links/public";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const HEADERS = {
  "Content-Type": "text/html; charset=utf-8",
  "Cache-Control": "no-store, no-transform",
  "Referrer-Policy": "no-referrer",
  "X-Robots-Tag": "noindex, nofollow",
  "Strict-Transport-Security": "max-age=31536000",
  "X-Content-Type-Options": "nosniff",
  "Content-Security-Policy": `default-src 'none'; style-src '${TEXT_CSS_HASH}'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'`,
};

function page(body, status = 200) {
  const html = `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">` +
    `<meta name="color-scheme" content="only light"><meta name="robots" content="noindex"><title>${esc(T.title)}</title><style>${TEXT_CSS}</style>` +
    `<body><p>${esc(T.brand)}</p><main>${body}</main></body></html>`;
  return new Response(html, { status, headers: HEADERS });
}

const para = (s) => `<p>${esc(s)}</p>`;
// What the person is deciding on is shown exactly as written, line breaks kept. Never masked: changing a word here
// could change what they agree to. These pages are private and not indexed, so the public word filter doesn't apply.
const quote = (s) => `<blockquote>${esc(s)}</blockquote>`;
const ended = () => page(`<h1>${esc(T.ended_heading)}</h1>${para(T.ended)}`);
const unavailable = () => page(para(T.unavailable), 503);

function left(expires, now) {
  const ms = Date.parse(expires) - now;
  const n = Math.floor(ms / 60000);
  const text = n < 1 ? T.under_minute : n === 1 ? T.minute : T.minutes.replace("{n}", n);
  return T.ends.replace("{minutes}", text);
}

function form(link, now, message = "") {
  const from = link.agent_label ? para(`${T.from} ${link.agent_label}`) : "";
  const note = link.agent_note ? para(`${T.note} ${link.agent_note}`) : "";
  const no = `<button type="submit" name="answer" value="decline">${esc(T.decline)}</button>`;
  const ask = link.kind === "ask";
  const controls = ask
    ? `<p><label for="value">${esc(T.answer_label)}</label><br><input id="value" name="value" maxlength="2000" autocomplete="off"></p><p><button type="submit" name="answer" value="send">${esc(T.send)}</button> ${no}</p>`
    : `<p><button type="submit" name="answer" value="confirm">${esc(T.confirm)}</button> ${no}</p>`;
  return page(`<h1>${esc(ask ? T.ask_heading : T.confirm_heading)}</h1>${from}${quote(link.text)}${note}${message ? para(message) : ""}` +
    `${para(left(link.expires_at, now))}<form method="post">${controls}</form>${para(ask ? T.private : T.unexpected)}`);
}

async function call(env, init) {
  const req = new Request(API, { ...init, signal: AbortSignal.timeout(8000) });
  return env.TESSERA && typeof env.TESSERA.fetch === "function" ? env.TESSERA.fetch(req) : fetch(req);
}

export async function linkResponse(request, env, token, now = Date.now()) {
  if (!TOKEN.test(token)) return ended();
  const headers = { "X-Human-Link-Token": token, Accept: "application/json" };
  try {
    if (request.method === "POST") {
      const data = await request.formData();
      const answer = String(data.get("answer") || "");
      if (!["confirm", "decline", "send"].includes(answer)) return ended();
      const body = answer === "send" ? { answer, value: String(data.get("value") || "").slice(0, 2000) } : { answer };
      const res = await call(env, { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (res.status >= 500) return unavailable();
      const out = await res.json().catch(() => ({}));
      if (res.status === 400 && out.state === "open") return form(out, now, T.need_answer);
      const done = { confirmed: T.done_confirmed, declined: T.done_declined, answered: T.done_answered }[out.state];
      return done && res.ok ? page(para(done)) : ended();
    }
    const res = await call(env, { method: "GET", headers });
    if (res.status >= 500) return unavailable();
    const link = await res.json().catch(() => null);
    return link && link.state === "open" ? form(link, now) : ended();
  } catch {
    return unavailable();
  }
}
