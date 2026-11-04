# Copied from the shim's worker kit (buildWorkerDistributedIndexerPy, /kits/herma-worker-kit.zip). Plain code, no model.
#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from typing import Any

DEFAULT_GATEWAY = "https://shim.teleionlabs.com"
DENSE_DIMS = 1024


def compute_client_index(text_or_obj: Any, model_id: str = 'client-feature-hash-int8-v1') -> dict[str, Any]:
    raw = text_or_obj if isinstance(text_or_obj, str) else json.dumps(text_or_obj, sort_keys=True)
    tokens = re.findall(r'[a-z0-9_]{2,}', raw.lower()) or ['empty_artifact']
    vec = [0.0] * DENSE_DIMS
    for idx, tok in enumerate(tokens):
        bg = f'{tokens[idx - 1]}_{tok}' if idx > 0 else tok
        for feat, weight in ((tok, 1.0), (bg, 0.65)):
            digest = hashlib.sha256(f'herma_v611_idx::{feat}'.encode('utf-8')).digest()
            slot = ((digest[0] << 8) | digest[1]) % DENSE_DIMS
            sign = 1.0 if (digest[2] & 1) == 0 else -1.0
            vec[slot] += sign * weight
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    unit = [v / norm for v in vec]
    peak = max((abs(u) for u in unit), default=1.0) or 1.0
    dense_int8 = [max(-128, min(127, int(round((u / peak) * 127.0)))) for u in unit]
    if not any(dense_int8):
        dense_int8[0] = 1

    def bits_to_hex(bit_list: list[int]) -> str:
        out: list[str] = []
        for b in range(0, len(bit_list), 4):
            nibble = (bit_list[b] << 3) | (bit_list[b + 1] << 2) | (bit_list[b + 2] << 1) | bit_list[b + 3]
            out.append(f'{nibble:x}')
        return ''.join(out)

    wide_bits = [1 if u >= 0.0 else 0 for u in unit]
    med_bits = [1 if sum(unit[i * 4:(i + 1) * 4]) >= 0.0 else 0 for i in range(256)]
    small_bits = [1 if sum(unit[i * 16:(i + 1) * 16]) >= 0.0 else 0 for i in range(64)]

    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', raw) if p.strip()] or [raw[:600]]
    blocks = []
    leafs = []
    for b_idx, para in enumerate(paragraphs[:16]):
        b_hash = hashlib.sha256(para.encode('utf-8')).hexdigest()[:16]
        blocks.append({
            'block_id': f'blk_{b_idx}',
            'title': para.splitlines()[0][:96],
            'text': para[:600],
            'lsh_small_64b': b_hash,
        })
        for l_idx, line in enumerate([ln.strip() for ln in para.splitlines() if ln.strip()][:6]):
            l_hash = hashlib.sha256(line.encode('utf-8')).hexdigest()[:16]
            keys = list(dict.fromkeys(re.findall(r'[a-z0-9_]{3,}', line.lower())))[:8]
            leafs.append({
                'leaf_id': f'leaf_{b_idx}_{l_idx}',
                'block_id': f'blk_{b_idx}',
                'text': line[:320],
                'search_keys': keys,
                'lsh_small_64b': l_hash,
            })
    return {
        'embedding_model_id': model_id,
        'embedding_norm': round(norm, 6),
        'dense_embedding_int8': dense_int8,
        'lsh_small_64b': bits_to_hex(small_bits),
        'lsh_medium_256b': bits_to_hex(med_bits),
        'lsh_wide_1024b': bits_to_hex(wide_bits),
        'search_blocks': blocks,
        'search_leafs': leafs,
    }

