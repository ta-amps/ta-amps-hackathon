> Unofficial AI-assisted summary, provided "as is" with no warranty. The [Official Rules](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/waiver) govern; read [DISCLAIMER.md](../DISCLAIMER.md). As of 2026-10-26.

# Models and tools

The sources name slightly different sets of Meta tools.

| Source | Meta tools it names |
|---|---|
| [Event page](https://cerebralvalley.ai/e/meta-ai-developer-hackathon) | Muse Spark series, Muse Wonder, Muse Image and SAM 3.1 through the Meta Model API; Meta open-weights models; the Muse Code coding agent |
| [Meta's event page](https://dev.meta.ai/events/global-hackathon) | The same, without Muse Wonder |
| [Official Rules](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/waiver) | Muse Spark, Glimmer and SAM 3, "and any other Meta AI products identified on the Event page" |
| [Model API docs](https://dev.meta.ai/docs/models) | Ids `muse-spark-1.3` (recommended), `-1.2`, `-1.1`; `muse-wonder-1.0` (preview); `sam-3.1`; `muse-voice-transcribe-1.0`; `muse-image-1.0` |

## What this means in practice

- The rules' "any other Meta AI products identified on the Event page" brings the event page's list in, so Muse Wonder,
  Muse Image and SAM 3.1 are fair game.
- No clause bans non-Meta models, but **Use of Meta AI Tooling** is 25% of the score.
- Confirm exact model ids with `GET https://api.meta.ai/v1/models` before you hard-code them. The product page writes
  SAM as `sam-3-1`, while the model docs write `sam-3.1`.
- Platform details, prices and limits are in [../meta-platform/](../meta-platform/README.md).

Sources: as linked, checked 2026-10-26.
