> Unofficial AI-assisted summary, provided "as is" with no warranty. The [Official Rules](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/waiver) govern; read [DISCLAIMER.md](../DISCLAIMER.md). As of 2026-10-26.

# Acceptable use, data use and geography

Anything you run on the Meta Model API falls under Meta's own terms, on top of the hackathon rules. The Credit Terms
bring them into the event too. This page picks out the clauses that matter most for projects that touch safety,
fraud, privacy or people's rights. A checklist that also covers other platforms' terms and data about people is in
[../guides/compliance-checklist.md](../guides/compliance-checklist.md).

## Acceptable Use Policy, the clauses that bite most often

[AUP](https://dev.meta.ai/legal/acceptable-use-policy), in our words:

| Clause | What it means for a project |
|---|---|
| No furthering illegal activity, naming human trafficking and exploitation among the examples | Detecting risk is the opposite of furthering it, but never generate material that works as a how-to or as a usable fake |
| No generating, promoting or furthering fraud | Invented example job ads, contracts or receipts must be visibly marked so nobody could use them as real |
| No collecting, processing, generating or inferring private or sensitive information about individuals without the right to | Use invented people; never seed with real names, ID numbers or cases |
| No classifying individuals by social behaviour or personal traits in a way that leads to unfavourable treatment | Assess documents and terms, not people |
| No relying on outputs for decisions that affect someone's fundamental rights, health or safety without a qualified person reviewing them | Serious outcomes go to a person |
| No defamatory content | Never name a real person or business as doing wrong |
| Don't present outputs as human-made | Label AI-generated text, images and audio |

Exceptions can be requested at aup_exceptions@meta.com.

## Model API Terms (updated Oct 9, 2026)

[Terms of Service](https://dev.meta.ai/legal/terms-of-service), in our words:

| Section | Point |
|---|---|
| 5.1 | Content sent to Standard services is not used to train Meta's models |
| 6.1 | Content sent to Contributor services may be used for training |
| 3.3 | Coding-harness subscriptions count as Contributor by default. Muse Code subscriptions default to Contributor mode; turn it off for anything sensitive |
| 6.2 | Don't send sensitive, confidential or personal information to Contributor services |
| 10.1(ix) | Don't use outputs to train, fine-tune or distil a model that competes with Meta's. Check this before any tuning experiment that learns from model outputs |
| 1 | You are responsible for AI labelling and provenance marking of what you publish |
| 7 | No trademark licence: don't use Meta's marks in your product or company name |

## Data-use tiers

| Tier | Training | Notes |
|---|---|---|
| Standard | Not used to train Meta models | Default for API keys |
| Contributor (Meta's data commitments page calls it "Discounted") | May be used to train | Cheaper; never for sensitive, confidential or personal data |

Source: [data commitments](https://dev.meta.ai/legal/commitments). Zero data retention exists but must be arranged
with Meta's sales team, and it switches off background requests, file uploads and web search.

## Geography

Meta's [Geographic Use Policy](https://dev.meta.ai/legal/geographic-use-policy) (updated Oct 12, 2026) lists
restricted territories. It names the People's Republic of China "including Hong Kong SAR and Macau SAR". You may not
offer an integrated product to end users located there, or knowingly let them use it.

- Writing made-up test scenarios set under Hong Kong law is a different thing from serving users in Hong Kong. The
  restriction is about end users and access.
- To claim the $150 credit you must live in a country on the policy's list.

## Other Meta terms worth knowing

- [Automated Data Collection Terms](https://www.facebook.com/apps/site_scraping_tos_terms.php): no automated collection
  from Meta's products without Meta's written permission. Don't scrape Facebook or Instagram.
- [Meta Content Library](https://transparency.meta.com/researchtools/meta-content-library): the lawful route to public
  Facebook and Instagram content for research. It needs an academic or non-profit research affiliation and an
  application review, and it can't be arranged within ten days.

Sources: as linked, checked 2026-10-26.
