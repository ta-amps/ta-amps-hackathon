> Unofficial AI-assisted summary, provided "as is" with no warranty. Meta's documentation governs; read [DISCLAIMER.md](../DISCLAIMER.md). As of 2026-10-26.

# Models, prices and limits

## Model ids

From [Models](https://dev.meta.ai/docs/models). Confirm with `GET https://api.meta.ai/v1/models`.

| Model | Id | Notes |
|---|---|---|
| Muse Spark | `muse-spark-1.3` | "Recommended for new work"; audio understanding is not fully supported. Older: `-1.2`, `-1.1` |
| Muse Spark (contributor) | `muse-spark-1.3-contributor`, `muse-spark-1.2-contributor` | Cheaper; content may be used for training |
| Muse Wonder | `muse-wonder-1.0` | In preview. No contributor version on the Model API |
| SAM 3.1 | `sam-3.1` | The product page writes `sam-3-1` |
| Muse Voice Transcribe | `muse-voice-transcribe-1.0` | See [speech-to-text.md](speech-to-text.md) |
| Muse Image | `muse-image-1.0` | Image generation and editing |

## Prices

From [Pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits).

| Model | Input, per 1M tokens | Cached input | Output |
|---|---|---|---|
| Muse Wonder | $4.00 | $0.20 | $20.00 |
| Muse Spark (Standard) | $1.25 | $0.15 | $4.25 |
| Muse Spark (Contributor) | $0.10 | $0.002 | $0.20 |

| Other | Price |
|---|---|
| Web search tool | $2.50 per 1,000 queries |
| Muse Image | $0.01 per image |
| Muse Voice Transcribe | $0.18 per audio hour |
| SAM 3.1 | $2.50 per 1,000 images; $0.20 per 1,000 video frames, with at least 50 frames billed per video request |

## Rate limits (per team, not per key)

| Model | Requests a minute | Tokens a minute |
|---|---|---|
| `muse-wonder-1.0`, `muse-spark-1.3`, `-1.2`, `-1.1` | 3,000 | 4,000,000 |
| `-contributor` ids | 150 | 3,000,000 |
| `sam-3.1` | 3,000 | none |
| `muse-image-1.0` | 150 | none |

- Background responses: 600 submissions a minute per team.
- Voice Transcribe: 256 concurrent streams and 16,000 streams an hour.

## Data use

| Tier | Training on your content | Use it for |
|---|---|---|
| Standard | No ([data commitments](https://dev.meta.ai/legal/commitments)) | Anything sensitive, confidential or personal |
| Contributor ("Discounted" on the commitments page) | Yes, may be used to train | Non-sensitive work only; the Terms bar sensitive, confidential or personal information (s.6.2) |

Sources: as linked, checked 2026-10-26.
