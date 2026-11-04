#!/usr/bin/env python3
"""Write a small stand-in film for the media tests when the real one isn't here. Video files aren't kept in git (MEDIA.md)."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = json.loads((ROOT / "content/site.json").read_text(encoding="utf-8"))["main_film"] + ".mp4"
FILM = ROOT / "static/media" / NAME
SIZE = 2 * 2**20

if not FILM.exists():
    FILM.parent.mkdir(parents=True, exist_ok=True)
    block = b"\x00\x00\x00\x18ftypmp42" + b"test-fixture-not-a-film" * 8
    data = bytearray()
    while len(data) < SIZE:
        block = hashlib.sha256(block).digest() * 8
        data += block
    FILM.write_bytes(bytes(data[:SIZE]))
    print(f"wrote the stand-in film: {FILM.name}, {SIZE} bytes")
