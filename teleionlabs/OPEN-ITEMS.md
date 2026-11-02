# Open items for teleionlabs.com

Things the pages leave out or word as "fair use" until the infrastructure or the owner provides them. Checked
2026-11-02 UTC.

## Infrastructure changes (Tessera)

1. **Per-address daily limits aren't enforced in code.** The master prompt's defaults (60 requests a minute and 5,000
   a day per address, 25 MiB written a day, 10 model-backed Tasks a day) don't exist in
   `deploy/cloudflare/cloud_access.js` yet. The free page states only the limits in `DEMO_QUOTAS` and their checks, and
   says "fair use" for the rest.
2. **The model shim's preview has no rate limit.** `POST /api/preview` checks only the prompt length (16,000
   characters). The page says "fair use".
3. **No free-use endpoint.** `GET https://tessera.teleionlabs.com/v1/free-use` answers 404, so the pages can't render
   the free-use state, `ends_at` or today's capacity from Tessera. The end date is copy for now.
4. **The automatic end isn't in code.** Nothing returns 402 `free_use_ended` after 2027-01-01T05:00:00Z yet. The free
   page states the end as policy (the owner's words), not as a running behaviour.
5. **No public status for the dedicated workers.** No public endpoint reports whether the dedicated workers are
   running (`worker.policy` answers 401; the Tessera health check shows queue counts, not workers). The live strip
   shows Tessera, the model shim and Eranos only. Wanted: an aggregated, cached GET in Tessera (for example active
   dedicated workers by model and the age of the last claim, no keys or labels).
6. **Tessera's connection file still advertises the workers.dev host,** and its anonymous-session text uses the
   banned word for made-up data. The site doesn't quote either; master prompt §6.5 covers the sweep.

## The owner

1. **Contact delivery.** MX for teleionlabs.com answers `route1`, `route2` and `route3.mx.cloudflare.net`, SPF includes
   `_spf.mx.cloudflare.net` and DMARC is `p=reject`, so routing looks on. The company page shows
   `hello@teleionlabs.com`. The owner's test message (OPEN-QUESTIONS.md item 4, step 3) isn't confirmed yet; the lead
   may hold the address until it is.
2. **Company details.** Only "Teleion Labs Incorporated" appears (OPEN-QUESTIONS.md item 3).
3. **No payments** (owner, Nov 2): no plans, prices or checkout anywhere; `/plans/` is removed.
4. **Free model capacity** (item 5.1). Workers on Meta's Muse models are outside free use while the cap is $0.00.

## Site

1. **Left out of v0.2:** `/connect.json` and `/.well-known/agent-card.json` for this site (llms.txt points agents at
   Tessera's own connection file instead), privacy and terms pages (owner-confirmed facts only, OPEN-QUESTIONS.md
   item 3), and the 429, 402 and 503 pages, which need the free-use enforcement above.
2. **security.txt** lists `mailto:hello@teleionlabs.com` and the security page as contacts, and expires on
   2027-05-01. If the owner picks support@ for security reports, change `content/security.json`.
3. **Content source.** The copy is Task Objects in `content/*.json`, built at deploy time. Moving them into Tessera
   (`teleion.instructions/*`) needs a keyed write by the operator.
4. **`www.teleionlabs.com` stays on the `www-canonical-redirect` Worker,** which answers 301 to the apex with
   path and query kept. This Worker takes the apex only (DEPLOY.md).

## Shared tooling (found while building this site)

1. **The hashed private-name scan can miss a name written as a regex literal.** `hackathon/scripts/check_public.py`
   splits text on non-alphanumerics, so a pattern such as a word wrapped in `\b` escapes becomes one token with a
   leading `b` and its hash doesn't match. This site's v0.1 test file had exactly that, and it was replaced before
   any push. `tests/check_words.py` strips escapes before hashing; the shared script (copied unchanged into every
   repo) needs the same fix from its owner.

## Privacy page

1. **Log retention follows the Workers plan.** `/privacy/` says Cloudflare keeps request logs for 3 days, which is the
   Workers Free plan (the owner's choice, Oct 29). A move to Workers Paid makes it 7 days, and the page must change then.
2. **Contact:** one address everywhere, hello@teleionlabs.com, because only hello@ has its own routing rule.
