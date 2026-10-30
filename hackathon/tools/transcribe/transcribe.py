#!/usr/bin/env python3
"""Transcribe a WAV file you have the right to use with Meta's Muse Voice Transcribe.

Stdlib only. The audio must be mono, 16-bit PCM, 16 or 24 kHz (the API's format). Long files are split into chunks
under the API's limits (10 minutes and 32 MB per request), each chunk is sent as multipart/form-data to
https://api.meta.ai/v1/asr/transcribe, and the turns are stitched back together on one timeline.

Your key comes from the MODEL_API_KEY environment variable. It is sent only to api.meta.ai and is never printed
or written to disk.

Examples:
  python3 transcribe.py talk.wav --i-have-rights --dry-run
  MODEL_API_KEY=... python3 transcribe.py talk.wav --i-have-rights --out transcripts/talk --language English
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
import wave
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

API_URL = "https://api.meta.ai/v1/asr/transcribe"
MODEL = "muse-voice-transcribe-1.0"
PRICE_PER_AUDIO_HOUR_USD = 0.18
API_MAX_SECONDS = 600
DEFAULT_MAX_SECONDS = 570.0
MAX_REQUEST_BYTES = 32_000_000 - 256_000
WAV_HEADER_BYTES = 44
RATES = (16000, 24000)
MODES = ("DIARIZATION", "PUSH_TO_TALK", "ENDPOINTING")
FFMPEG_HINT = "ffmpeg -i INPUT -ac 1 -ar 24000 -c:a pcm_s16le -map_metadata -1 OUTPUT.wav"
RIGHTS_NOTE = (
    "Transcribe only audio you have the right to use, such as an official download you may use or your own recording. "
    "Event recordings usually belong to the organizers: keep transcripts private and share summaries, not copies."
)


class TranscribeError(Exception):
    """A problem the user can fix; printed without a traceback."""


@dataclass(frozen=True)
class Chunk:
    index: int
    start_frame: int
    frames: int
    rate: int

    @property
    def start_ms(self) -> int:
        return round(self.start_frame * 1000 / self.rate)

    @property
    def end_ms(self) -> int:
        return round((self.start_frame + self.frames) * 1000 / self.rate)

    @property
    def seconds(self) -> float:
        return self.frames / self.rate

    @property
    def wav_bytes(self) -> int:
        return WAV_HEADER_BYTES + self.frames * 2


def check_format(path: Path) -> tuple[int, int]:
    """Return (sample rate, frame count), or raise with the conversion command."""
    try:
        with wave.open(str(path), "rb") as audio:
            channels, width = audio.getnchannels(), audio.getsampwidth()
            rate, frames, compression = audio.getframerate(), audio.getnframes(), audio.getcomptype()
    except (wave.Error, EOFError, OSError) as exc:
        raise TranscribeError(f"{path} is not a readable WAV file ({exc}). Convert it first:\n  {FFMPEG_HINT}") from None
    problems = []
    if channels != 1:
        problems.append(f"{channels} channels (needs mono)")
    if width != 2:
        problems.append(f"{width * 8}-bit samples (needs 16-bit)")
    if rate not in RATES:
        problems.append(f"{rate} Hz (needs 16000 or 24000)")
    if compression != "NONE":
        problems.append(f"compression {compression} (needs PCM)")
    if problems:
        raise TranscribeError(f"{path} has {', '.join(problems)}. Convert it first:\n  {FFMPEG_HINT}")
    if frames == 0:
        raise TranscribeError(f"{path} contains no audio")
    return rate, frames


def plan_chunks(total_frames: int, rate: int, max_seconds: float = DEFAULT_MAX_SECONDS,
                max_bytes: int = MAX_REQUEST_BYTES) -> list[Chunk]:
    """Split the audio into chunks that respect both the duration and the request-size limits."""
    by_time = int(max_seconds * rate)
    by_size = (max_bytes - WAV_HEADER_BYTES) // 2
    per_chunk = max(1, min(by_time, by_size))
    chunks: list[Chunk] = []
    start = 0
    while start < total_frames:
        count = min(per_chunk, total_frames - start)
        chunks.append(Chunk(len(chunks) + 1, start, count, rate))
        start += count
    return chunks


def read_chunk(path: Path, chunk: Chunk) -> bytes:
    """The chunk as a standalone mono 16-bit WAV file."""
    with wave.open(str(path), "rb") as source:
        source.setpos(chunk.start_frame)
        frames = source.readframes(chunk.frames)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(chunk.rate)
        target.writeframes(frames)
    return buffer.getvalue()


def build_request(mode: str, languages: list[str], keywords: list[str]) -> dict[str, Any]:
    request: dict[str, Any] = {"model": MODEL, "audioEncoding": "WAV", "mode": mode}
    if languages:
        request["languageBias"] = languages
    if keywords:
        request["keywords"] = keywords
    return request


def build_multipart(request: dict[str, Any], wav: bytes, filename: str,
                    boundary: str | None = None) -> tuple[bytes, str]:
    """A multipart/form-data body with a JSON `request` part and a WAV `audio` part."""
    boundary = boundary or uuid.uuid4().hex
    lines = [
        f"--{boundary}".encode(),
        b'Content-Disposition: form-data; name="request"',
        b"Content-Type: application/json",
        b"",
        json.dumps(request).encode(),
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="audio"; filename="{filename}"'.encode(),
        b"Content-Type: audio/wav",
        b"",
        wav,
        f"--{boundary}--".encode(),
        b"",
    ]
    return b"\r\n".join(lines), f"multipart/form-data; boundary={boundary}"


def scrub(text: str, key: str) -> str:
    return text.replace(key, "[redacted]") if key else text


def retry_after(value: str | None, attempt: int) -> float:
    try:
        return max(1.0, min(300.0, float(value))) if value else min(60.0, 2.0 * 2**attempt)
    except ValueError:
        return min(60.0, 2.0 * 2**attempt)


def post_chunk(body: bytes, content_type: str, key: str, *, retries: int = 5,
               opener: Callable[..., Any] | None = None,
               sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    """POST one chunk, retrying 429 and 503 with Retry-After. Errors never contain the key."""
    open_url = opener or urllib.request.urlopen
    headers = {"Authorization": f"Bearer {key}", "Content-Type": content_type, "Accept": "application/json"}
    for attempt in range(retries + 1):
        request = urllib.request.Request(API_URL, data=body, method="POST", headers=headers)
        try:
            with open_url(request, timeout=300) as response:
                payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
                return payload
        except urllib.error.HTTPError as err:
            try:
                detail = err.read().decode("utf-8", "replace")[:300]
            except Exception:  # noqa: BLE001 - the body is optional
                detail = ""
            if err.code in (429, 503) and attempt < retries:
                wait = retry_after(err.headers.get("Retry-After") if err.headers else None, attempt)
                print(f"  server busy (HTTP {err.code}); retrying in {wait:.0f}s", file=sys.stderr)
                sleep(wait)
                continue
            raise TranscribeError(f"request failed with HTTP {err.code}: {scrub(detail, key)}") from None
        except urllib.error.URLError as err:
            raise TranscribeError(f"network error: {scrub(str(err.reason), key)}") from None
    raise TranscribeError("gave up after repeated retries")


def stamp(ms: int) -> str:
    seconds = ms // 1000
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def chunk_turns(chunk: Chunk, response: dict[str, Any]) -> list[dict[str, Any]]:
    """The chunk's turns on the whole file's timeline."""
    turns = response.get("turns") or []
    if not turns and response.get("transcript"):
        turns = [{"startMs": 0, "endMs": chunk.end_ms - chunk.start_ms, "transcript": response["transcript"]}]
    return [{
        "chunk": chunk.index,
        "start_ms": chunk.start_ms + int(turn.get("startMs", 0)),
        "end_ms": chunk.start_ms + int(turn.get("endMs", 0)),
        "speaker": turn.get("speaker"),
        "text": str(turn.get("transcript", "")).strip(),
    } for turn in turns]


def write_outputs(out: Path, source: Path, mode: str, chunks: list[dict[str, Any]],
                  turns: list[dict[str, Any]]) -> tuple[Path, Path]:
    out.mkdir(parents=True, exist_ok=True)
    json_path, md_path = out / "transcript.json", out / "transcript.md"
    record = {"source": source.name, "model": MODEL, "mode": mode, "chunks": chunks, "turns": turns,
              "note": "Speaker labels restart in each chunk. " + RIGHTS_NOTE}
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [f"# Transcript: {source.name}", "", f"> {RIGHTS_NOTE}",
             "> Machine transcription by Muse Voice Transcribe; check anything you quote against the audio.", ""]
    for turn in turns:
        speaker = f" {turn['speaker']} (chunk {turn['chunk']})" if turn["speaker"] is not None else ""
        lines.append(f"- [{stamp(turn['start_ms'])}]{speaker}: {turn['text']}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe a WAV file with Muse Voice Transcribe.",
                                     epilog=RIGHTS_NOTE)
    parser.add_argument("audio", type=Path, help="mono 16-bit PCM WAV at 16 or 24 kHz")
    parser.add_argument("--out", type=Path, help="output folder (default: transcripts/<file name>)")
    parser.add_argument("--mode", choices=MODES, default="DIARIZATION")
    parser.add_argument("--language", action="append", default=[], help="language name to bias towards; repeatable")
    parser.add_argument("--keyword", action="append", default=[], help="term to bias towards; repeatable")
    parser.add_argument("--max-chunk-seconds", type=float, default=DEFAULT_MAX_SECONDS,
                        help=f"chunk length in seconds (at most {API_MAX_SECONDS}; default {DEFAULT_MAX_SECONDS:g})")
    parser.add_argument("--retries", type=int, default=5, help="retries for HTTP 429 and 503")
    parser.add_argument("--dry-run", action="store_true", help="show the chunks and cost; send nothing")
    parser.add_argument("--i-have-rights", action="store_true",
                        help="confirm you have the right to transcribe this audio")
    return parser.parse_args(argv)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    if not args.i_have_rights:
        raise TranscribeError("add --i-have-rights to confirm you may transcribe this audio. " + RIGHTS_NOTE)
    if not 0 < args.max_chunk_seconds <= API_MAX_SECONDS:
        raise TranscribeError(f"--max-chunk-seconds must be between 0 and {API_MAX_SECONDS}")
    rate, total_frames = check_format(args.audio)
    chunks = plan_chunks(total_frames, rate, args.max_chunk_seconds)
    total_seconds = total_frames / rate
    print(f"{args.audio.name}: {total_seconds:.1f} s at {rate} Hz, {len(chunks)} chunk(s), "
          f"estimated cost ${total_seconds / 3600 * PRICE_PER_AUDIO_HOUR_USD:.4f}")
    for chunk in chunks:
        print(f"  chunk {chunk.index}: {stamp(chunk.start_ms)} to {stamp(chunk.end_ms)}, "
              f"{chunk.seconds:.1f} s, {chunk.wav_bytes:,} bytes")
    if args.dry_run:
        print("dry run: no request sent")
        return 0
    key = env.get("MODEL_API_KEY", "")
    if not key:
        raise TranscribeError("MODEL_API_KEY is not set. Export it in your shell; never paste it into a file or chat.")
    request = build_request(args.mode, args.language, args.keyword)
    chunk_records: list[dict[str, Any]] = []
    turns: list[dict[str, Any]] = []
    for chunk in chunks:
        body, content_type = build_multipart(request, read_chunk(args.audio, chunk), f"chunk-{chunk.index:04d}.wav")
        print(f"sending chunk {chunk.index}/{len(chunks)}")
        response = post_chunk(body, content_type, key, retries=args.retries)
        chunk_records.append({"index": chunk.index, "start_ms": chunk.start_ms, "end_ms": chunk.end_ms,
                              "session_id": response.get("sessionId"),
                              "audio_duration_ms": response.get("audioDurationMs")})
        turns.extend(chunk_turns(chunk, response))
    out = args.out or Path("transcripts") / args.audio.stem
    json_path, md_path = write_outputs(out, args.audio, args.mode, chunk_records, turns)
    print(f"wrote {json_path} and {md_path}")
    return 0


def main(argv: list[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run(args, os.environ if env is None else env)
    except TranscribeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
