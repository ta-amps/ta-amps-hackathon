> Unofficial AI-assisted summary, provided "as is" with no warranty. Meta's documentation governs; read [DISCLAIMER.md](../DISCLAIMER.md). As of 2026-10-26.

# Speech to text (Muse Voice Transcribe)

Source: https://dev.meta.ai/docs/speech-to-text, checked 2026-10-26.

## Files

| Item | Value |
|---|---|
| Endpoint | `POST https://api.meta.ai/v1/asr/transcribe` (optional `?sessionId=…`) |
| Auth | `Authorization: Bearer $MODEL_API_KEY` |
| Body | `multipart/form-data` with a `request` part (JSON settings) and an `audio` part (the WAV file) |
| `request` fields | `model` (`muse-voice-transcribe-1.0`), `audioEncoding` (`WAV`), `mode` (`PUSH_TO_TALK` default, `ENDPOINTING` or `DIARIZATION`), optional `languageBias` (language names) and `keywords` |
| Audio | RIFF/WAVE, mono, 16-bit PCM, 16 or 24 kHz |
| Limits | 32 MB per request (413 if larger); 10 minutes of audio per request (400 if longer) |
| Response | `sessionId`, `transcript`, `audioDurationMs`, and `turns` (each with `turnId`, `startMs`, `endMs`, `transcript`, and `speaker` in diarization mode). In push-to-talk mode `turns` is empty |
| Accept | `application/json` (default), `text/event-stream` or `text/plain`; anything else returns 406 |
| Price | $0.18 per audio hour |

To convert other audio, the docs use ffmpeg with mono, a 24 kHz rate, 16-bit PCM and stripped metadata:

```bash
ffmpeg -i input.m4a -ac 1 -ar 24000 -c:a pcm_s16le -map_metadata -1 output.wav
```

## Realtime

A WebSocket at `wss://api.meta.ai/v1/asr/realtime`. Authentication goes in the handshake frame; the Authorization
header is ignored. Limits: 256 concurrent streams and 16,000 streams an hour per team.

## Languages (25)

Arabic, Bengali, Dutch, English, French, German, Hebrew, Hindi, Indonesian, Italian, Japanese, Kannada, Korean, Malay,
Mandarin Chinese, Marathi, Polish, Portuguese, Spanish, Tagalog, Tamil, Telugu, Thai, Turkish, Vietnamese.
Not listed, among others: Nepali, Amharic, Swahili.

## A ready-made client

[../tools/transcribe/](../tools/transcribe/README.md) splits long WAV files into chunks under both limits, sends each,
and stitches a timestamped transcript. Use it only on audio you have the right to use.
