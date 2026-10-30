> Unofficial AI-assisted summary, provided "as is" with no warranty. Meta's documentation governs; read [DISCLAIMER.md](../DISCLAIMER.md). As of 2026-10-26.

# Meta Model API

## Basics

| Item | Value | Source |
|---|---|---|
| Base URL | `https://api.meta.ai/v1` | [API reference](https://dev.meta.ai/docs/api-reference) |
| Auth | `Authorization: Bearer $MODEL_API_KEY` | [Authentication](https://dev.meta.ai/docs/authentication) |
| Key format | Keys start with `LLM_` | [Authentication](https://dev.meta.ai/docs/authentication) |
| SDK | No SDK of its own; the docs say to use the OpenAI SDK with `base_url` (the Anthropic SDK also works) | [SDKs](https://dev.meta.ai/docs/sdks) |

The OpenAI Python SDK doesn't read `MODEL_API_KEY` itself, so pass the key explicitly:

```python
import os
from openai import OpenAI

client = OpenAI(api_key=os.environ["MODEL_API_KEY"], base_url="https://api.meta.ai/v1")
```

## Responses API

`POST /v1/responses` ([guide](https://dev.meta.ai/docs/protocols/responses),
[schemas](https://dev.meta.ai/docs/api-reference/responses/schemas)).

| Field | Notes |
|---|---|
| `model` | For example `muse-spark-1.3`; see [models-and-pricing.md](models-and-pricing.md) |
| `input` | Text or structured input |
| `background` | `true` queues the job and returns right away with status `queued` |
| `store` | Responses are stored by default (`true`) |
| `metadata` | Free-form object; useful for queue, task, lease and attempt ids |
| `text.format` | Structured output: `json_schema` with `name`, `schema` and `strict`. The docs use `text.format`, not `response_format` |
| `max_output_tokens` | Minimum 16 |
| `max_tool_calls` | Caps tool calls |
| `reasoning.effort` | `none` returns 400 on Spark and Wonder; `max` is listed for `muse-wonder-1.0` and `muse-spark-1.3` but not the contributor id ([reasoning](https://dev.meta.ai/docs/reasoning)). The Responses guide's list leaves out `max`, so test before relying on it |

## Background jobs

| Action | Call |
|---|---|
| Create | `POST /v1/responses` with `"background": true` returns `status: "queued"` |
| Poll | `GET /v1/responses/{id}`: queued, in_progress, completed, failed, cancelled, incomplete |
| Stream events | `GET /v1/responses/{id}?stream=true` (lifecycle events; resume with `starting_after`) |
| Cancel | `POST /v1/responses/{id}/cancel` |

- `background` together with `stream` on the create call returns 400.
- Background request bodies are capped at 1 MiB (1,048,576 bytes), and anything larger returns 413. Send big inputs as files.

## Files

`POST /v1/files` with `purpose=user_data`: up to 1 GiB per file and 100 GiB per team. Files don't expire unless you set
`expires_after` (3,600 to 2,592,000 seconds).

## Retention

The Terms say content is kept "as needed", with no period stated, and the docs don't say how long stored responses
last. Persist anything you need on your side. Zero data retention needs Meta's sales team and switches off background
requests, server-side history, file uploads, web search and Contributor mode
([ZDR](https://dev.meta.ai/help/policies-and-privacy/zero-data-retention)).

Sources: as linked, checked 2026-10-26.
