"""Tests for transcribe.py. Stdlib only; no network calls are made."""

from __future__ import annotations

import contextlib
import email.message
import io
import json
import tempfile
import unittest
import urllib.error
import wave
from pathlib import Path
from typing import Any
from unittest import mock

import transcribe

FAKE_KEY = "test-secret-value-123"


def make_wav(path: Path, seconds: float, rate: int = 16000, channels: int = 1) -> Path:
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(b"\x00\x00" * channels * int(seconds * rate))
    return path


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def run_main(argv: list[str], env: dict[str, str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = transcribe.main(argv, env)
    return code, out.getvalue(), err.getvalue()


class ChunkPlanTests(unittest.TestCase):
    def test_one_hour_at_16k_needs_seven_chunks(self) -> None:
        chunks = transcribe.plan_chunks(3600 * 16000, 16000)
        self.assertEqual(len(chunks), 7)
        self.assertTrue(all(c.seconds <= transcribe.DEFAULT_MAX_SECONDS for c in chunks))
        self.assertEqual(sum(c.frames for c in chunks), 3600 * 16000)
        self.assertEqual(chunks[1].start_ms, 570_000)

    def test_chunks_stay_under_the_request_size(self) -> None:
        chunks = transcribe.plan_chunks(600 * 24000, 24000, max_bytes=1_000_044)
        self.assertTrue(all(c.wav_bytes <= 1_000_044 for c in chunks))
        self.assertEqual(chunks[0].frames, 500_000)

    def test_default_chunk_fits_both_api_limits(self) -> None:
        for rate in transcribe.RATES:
            chunk = transcribe.plan_chunks(3600 * rate, rate)[0]
            self.assertLessEqual(chunk.seconds, 600)
            self.assertLess(chunk.wav_bytes, 32_000_000)

    def test_small_file_dry_run_lists_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wav = make_wav(Path(tmp) / "talk.wav", 25)
            code, out, _ = run_main([str(wav), "--i-have-rights", "--dry-run", "--max-chunk-seconds", "10"], {})
        self.assertEqual(code, 0)
        self.assertIn("3 chunk(s)", out)
        self.assertIn("chunk 3: 00:00:20 to 00:00:25", out)


class MultipartTests(unittest.TestCase):
    def test_body_has_request_json_and_audio(self) -> None:
        request = transcribe.build_request("DIARIZATION", ["English"], ["Muse"])
        body, content_type = transcribe.build_multipart(request, b"RIFFdata", "chunk-0001.wav", boundary="XYZ")
        self.assertEqual(content_type, "multipart/form-data; boundary=XYZ")
        self.assertIn(b'name="request"', body)
        self.assertIn(b'name="audio"; filename="chunk-0001.wav"', body)
        json_part = body.split(b"\r\n\r\n", 1)[1].split(b"\r\n--XYZ", 1)[0]
        self.assertEqual(json.loads(json_part)["model"], "muse-voice-transcribe-1.0")
        self.assertEqual(json.loads(json_part)["languageBias"], ["English"])
        self.assertIn(b"RIFFdata\r\n--XYZ--", body)


class SafetyTests(unittest.TestCase):
    def test_dry_run_makes_no_network_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch("urllib.request.urlopen", side_effect=AssertionError("network used")) as urlopen:
            wav = make_wav(Path(tmp) / "a.wav", 2)
            code, _, _ = run_main([str(wav), "--i-have-rights", "--dry-run"], {"MODEL_API_KEY": FAKE_KEY})
        self.assertEqual(code, 0)
        urlopen.assert_not_called()

    def test_refuses_stereo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wav = make_wav(Path(tmp) / "stereo.wav", 1, channels=2)
            code, _, err = run_main([str(wav), "--i-have-rights", "--dry-run"], {})
        self.assertEqual(code, 2)
        self.assertIn("mono", err)
        self.assertIn("ffmpeg", err)

    def test_refuses_missing_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wav = make_wav(Path(tmp) / "a.wav", 1)
            code, _, err = run_main([str(wav), "--i-have-rights"], {})
        self.assertEqual(code, 2)
        self.assertIn("MODEL_API_KEY is not set", err)

    def test_requires_rights_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wav = make_wav(Path(tmp) / "a.wav", 1)
            code, _, err = run_main([str(wav), "--dry-run"], {})
        self.assertEqual(code, 2)
        self.assertIn("--i-have-rights", err)

    def test_key_never_appears_in_output(self) -> None:
        reply = {"sessionId": "s1", "transcript": "hello there", "audioDurationMs": 2000,
                 "turns": [{"turnId": 1, "startMs": 0, "endMs": 900, "transcript": "hello", "speaker": "A"},
                           {"turnId": 2, "startMs": 1000, "endMs": 1900, "transcript": "there", "speaker": "B"}]}
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch("urllib.request.urlopen", return_value=FakeResponse(reply)) as urlopen:
            wav = make_wav(Path(tmp) / "a.wav", 2)
            out_dir = Path(tmp) / "out"
            code, out, err = run_main([str(wav), "--i-have-rights", "--out", str(out_dir)],
                                      {"MODEL_API_KEY": FAKE_KEY})
            files = {p.name: p.read_text() for p in out_dir.iterdir()}
        self.assertEqual(code, 0)
        self.assertEqual(urlopen.call_count, 1)
        self.assertNotIn(FAKE_KEY, out + err)
        self.assertTrue(all(FAKE_KEY not in text for text in files.values()))
        turns = json.loads(files["transcript.json"])["turns"]
        self.assertEqual([t["text"] for t in turns], ["hello", "there"])
        self.assertIn("[00:00:01] B (chunk 1): there", files["transcript.md"])

    def test_error_messages_are_scrubbed(self) -> None:
        error = urllib.error.HTTPError(transcribe.API_URL, 401, "Unauthorized", email.message.Message(),
                                       io.BytesIO(f"bad key {FAKE_KEY}".encode()))
        with mock.patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(transcribe.TranscribeError) as caught:
                transcribe.post_chunk(b"body", "multipart/form-data; boundary=x", FAKE_KEY, retries=0)
        self.assertNotIn(FAKE_KEY, str(caught.exception))
        self.assertIn("[redacted]", str(caught.exception))

    def test_retries_busy_server_with_retry_after(self) -> None:
        headers = email.message.Message()
        headers["Retry-After"] = "7"
        busy = urllib.error.HTTPError(transcribe.API_URL, 429, "Too Many Requests", headers, io.BytesIO(b""))
        waits: list[float] = []
        with mock.patch("urllib.request.urlopen", side_effect=[busy, FakeResponse({"turns": []})]):
            result = transcribe.post_chunk(b"b", "multipart/form-data; boundary=x", FAKE_KEY, retries=2,
                                           sleep=waits.append)
        self.assertEqual(result, {"turns": []})
        self.assertEqual(waits, [7.0])


if __name__ == "__main__":
    unittest.main()
