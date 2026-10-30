# transcribe: Muse Voice Transcribe for long WAV files

A stdlib-only Python script that sends a WAV file to Meta's Muse Voice Transcribe in chunks and stitches a
timestamped transcript.

**Use it only on audio you have the right to use**, for example an official download the organizers let you use, or
your own recording. Event recordings belong to the organizers: keep transcripts private and share summaries, not copies.
The tool asks you to confirm this with `--i-have-rights`.

## What it does

1. Checks the WAV is mono, 16-bit PCM, at 16 or 24 kHz, and prints the ffmpeg command if it isn't.
2. Splits it into chunks of at most 9.5 minutes, each under the 32 MB request limit (the API allows 10 minutes and 32 MB).
3. Sends each chunk to `POST https://api.meta.ai/v1/asr/transcribe` as `multipart/form-data`, with a `request` JSON part
   (`muse-voice-transcribe-1.0`, `WAV`, diarization by default) and an `audio` part.
4. Retries HTTP 429 and 503, waiting as long as `Retry-After` says.
5. Shifts every turn onto the whole file's timeline and writes `transcript.json` and `transcript.md`.

Speaker labels restart in each chunk, so the Markdown shows the chunk number next to each speaker.

## Use

```bash
# Convert first if needed (mono, 24 kHz, 16-bit PCM):
ffmpeg -i talk.m4a -ac 1 -ar 24000 -c:a pcm_s16le -map_metadata -1 talk.wav

# See the chunks and the cost; nothing is sent:
python3 transcribe.py talk.wav --i-have-rights --dry-run

# Transcribe (your key stays in the environment):
export MODEL_API_KEY=...        # set it in your shell; never paste a key into a file or chat
python3 transcribe.py talk.wav --i-have-rights --out ~/notes/talk --language English --keyword "Muse Spark"
```

| Option | Default | Meaning |
|---|---|---|
| `--mode` | `DIARIZATION` | Or `PUSH_TO_TALK` or `ENDPOINTING` |
| `--language` | none | Language name to bias towards; repeatable |
| `--keyword` | none | Term to bias towards; repeatable |
| `--max-chunk-seconds` | 570 | Chunk length, at most 600 |
| `--retries` | 5 | Retries for 429 and 503 |
| `--out` | `transcripts/<file name>` | Output folder; `transcripts/` is git-ignored |

The cost is $0.18 per audio hour, so an hour-long talk costs about $0.18 ([pricing](https://dev.meta.ai/docs/pricing-rate-limits)).

## Safety

- The key is read from `MODEL_API_KEY`, sent only to `api.meta.ai`, and never printed or written. Error messages are scrubbed.
- No audio or transcript is committed: `*.wav`, `transcripts/` and `out/` are in `.gitignore`.

## Tests

```bash
python3 -m unittest discover -s tools/transcribe -p 'test_*.py'
```

The tests make no network calls. They cover chunk math, the multipart body, dry runs, format and key refusals,
retries, and that the key never reaches output.

API facts from https://dev.meta.ai/docs/speech-to-text, checked 2026-10-26. See also
[../../meta-platform/speech-to-text.md](../../meta-platform/speech-to-text.md).
