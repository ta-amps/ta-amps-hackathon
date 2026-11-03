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
2. **security.txt** lists `mailto:security@teleionlabs.com` and the security page as contacts, and expires on
   2027-05-01. security@ has its own forwarding rule now (5a5b9ba3, added by Antigravity; read enabled on Nov 2).
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
2. **Contact:** hello@teleionlabs.com for everything, and security@teleionlabs.com for security problems (the Security
   and Privacy pages and security.txt). Both have their own Email Routing rules; the owner's delivery test for
   security@ is still worth sending.
3. **What Tessera and the shim keep changes with their deploys.** On Nov 2 at 17:10 UTC Tessera kept invocation logs
   (3 days on Workers Free) and persisted traces (7 days); the shim had invocation logs and traces off. The Privacy page
   says exactly that, dated. A change to either Worker's `observability` needs the same change here.
4. **The live v0.2.1 page overstates logging.** After the 10:31 UTC rollback, the live `teleionlabs` Worker's
   script-settings read `observability: null` (no logs), while its Privacy page still says logs are kept for 3 days.
   v0.4 sets logs off explicitly and says so.

## v0.4 (Nov 2): what the onboarding spec had that the pages leave out

The start page follows Antigravity's onboarding spec (`notes/coordination-2026-11-02/teleion_onboarding_and_video_walkthrough/`)
in shape. These parts of it aren't true of live code, so the pages leave them out or say otherwise:

1. **`acct.<tenant>` spaces and share grants.** No such namespace or grant exists. Free sessions get `demo.<id>`;
   keys get the namespaces named on them. The page says sharing a space "isn't available yet".
2. **"120 s default lease, 60 to 900 s".** Practice queues use a 300 s lease with a 30 s heartbeat and a miss limit of
   3 (a claim runs out 90 s after the last check-in); created queues default to 600 s and 60 s, within 1 to 3,600 s.
3. **"Public activity map: off by default".** It is on by default (`show_on_map` defaults to true); a session or key
   opened with `show_on_map: false` stays in the totals only. Private Tasks, including every practice Task, never
   appear. The start page offers the switch and says this.
4. **Counts** ("40+ AI agents", "596 Tasks", "22 vetted kits") and **"Muse Glimmer 45% to 98%"**. No counts on the
   pages; they link to the live network page, which separates workers run by us from volunteers' AIs. Eranos's 22
   kits are marked as examples. Muse Glimmer is described as measured and not taking live work, with no figures.
5. **OmniNode and "always free feeds".** Not Tessera's words; `GET /v1/feeds` needs a key. Left out.
6. **Submitting Tasks through the shim.** The shim's `/q/*` gateway keeps a priority ledger of its own beside Tessera's
   queues. The start page sticks to Tessera's queues and says the shim adds Task Objects to model calls.

