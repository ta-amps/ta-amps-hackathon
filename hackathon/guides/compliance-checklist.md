> Unofficial AI-assisted summary, provided "as is" with no warranty. Not legal advice. Rules and terms change; check every source before relying on it. Read [DISCLAIMER.md](../DISCLAIMER.md). As of 2026-10-26.

# Compliance checklist

Three sets of rules apply to almost every entry: the hackathon's Official Rules, the terms of each platform
you touch, and the law of whatever your project handles. Walk this list on day one and again before you
submit. Each item links its source; read the source, not just this line.

## 1. The Official Rules

The Official Rules are the event's waiver page, dated Oct 25, 2026. Section-by-section summary:
[event/07-official-rules-summary.md](../event/07-official-rules-summary.md).

- [ ] **Original work.** The Submission is your original work product and solely owned by you. Third-party
      help and open source are allowed when the components stay your own work and licences are followed.
      Disclose earlier work you build on.
- [ ] **Licence to the organizers.** They get a broad, non-exclusive licence to the Submission, and anything
      else you share "will not be considered confidential". Put nothing secret in the Submission or the Discord.
- [ ] **Recordings belong to the organizers.** No ripped video and no full transcripts of sessions in public.
      Summarize in your own words and link the source ([events/](../events/README.md)).
- [ ] **Eligibility and team size** for your track: [event/06-eligibility.md](../event/06-eligibility.md),
      [event/03-tracks.md](../event/03-tracks.md).
- [ ] **Submission contents and deadline:** [event/11-submission.md](../event/11-submission.md),
      [event/02-key-dates.md](../event/02-key-dates.md).

## 2. Meta's terms

- [ ] **Standard, not Contributor.** Under the [Model API Terms of Service](https://dev.meta.ai/legal/terms-of-service)
      (updated Oct 9, 2026), Standard content isn't used to train Meta models and Contributor content may be.
      Coding subscriptions count as Contributor by default. Keep personal, confidential or sensitive data out
      of Contributor services, and run coding agents with Contributor mode off
      ([meta-platform/muse-code.md](../meta-platform/muse-code.md)).
- [ ] **Outputs.** No using outputs to train, fine-tune or distil a competing model. You handle any labelling,
      disclosure or provenance marking of AI-generated content.
- [ ] **Acceptable Use Policy** ([dev.meta.ai/legal/acceptable-use-policy](https://dev.meta.ai/legal/acceptable-use-policy)):
      nothing that furthers illegal activity, fraud or defamation; no collecting or inferring sensitive
      information about people without the right to; a qualified person reviews outputs used for decisions
      about someone's fundamental rights; never present outputs as human-made.
- [ ] **Geographic Use Policy** ([dev.meta.ai/legal/geographic-use-policy](https://dev.meta.ai/legal/geographic-use-policy),
      updated Oct 12, 2026): integrated products may not be offered to, or knowingly used by, end users in
      restricted territories, which include the People's Republic of China "including Hong Kong SAR and Macau SAR".
      Check your audience and any hosted demo against the current list.
- [ ] **No scraping Meta products** without Meta's express written permission
      ([Automated Data Collection Terms](https://www.facebook.com/apps/site_scraping_tos_terms.php), Oct 7, 2024).
- [ ] **Brand.** No Meta trademark in a product, company, username or domain name
      ([Meta brand resources](https://www.meta.com/brand/resources/meta/our-trademarks/)).

## 3. Code and hosting platforms

- [ ] **GitHub** ([Acceptable Use Policies](https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies)):
      no defamatory or fraudulent content, no misuse of personal information, and label synthetic media that
      could mislead.
- [ ] **Cloudflare** ([terms](https://www.cloudflare.com/terms/)) and **Fly.io**
      ([acceptable use](https://fly.io/legal/acceptable-use-policy/)): no illegal use; on Fly.io, no security
      testing such as scanning or penetration testing. Load-test only services you own.

## 4. Data and people

- [ ] **Synthetic data by default.** Invented people, companies and numbers; phone numbers from ranges your
      country's regulator reserves for fiction (for example 555-0100 to 555-0199 in North America; unverified
      here, so check the regulator's page); example domains ([RFC 2606](https://www.rfc-editor.org/rfc/rfc2606)).
      Adults only.
- [ ] **Real personal data** brings in privacy law (GDPR, CCPA, PDPA, PDPO and others). If you must use it, do a
      privacy review first and keep it out of Contributor services.
- [ ] **Label what a model made.** Mark generated documents and images as synthetic in their text and pixels.

## 5. If your project judges people, companies or content

- [ ] **Indicators, not verdicts.** Show risk indicators tied to evidence, never accusations. UNODC: indicators
      "are not themselves proof" ([UNODC module](https://unodc.org/e4j/en/tip-and-som/module-6/key-issues/indicators-of-trafficking-in-persons.html)).
- [ ] **No real targets.** Never name real people or businesses as wrongdoers in outputs, demos or data. AI
      summaries that describe a business falsely have led to lawsuits.
- [ ] **A person decides.** Route anything that affects someone's rights to a qualified reviewer.
- [ ] **Safe referrals.** If you point people to help, re-verify every helpline before the demo, and never
      contact anyone automatically.

## 6. Before you submit

- [ ] Every repo passes a secret scan (`scripts/check_public.py`) and has no `.env` in history.
- [ ] Licences of every dependency are kept; your own licence file is present.
- [ ] The README says what is real, what is simulated and what is planned.
- [ ] The demo video shows only synthetic data and your own accounts.
