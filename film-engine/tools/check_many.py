#!/usr/bin/env python3
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import comp_check
for a in sys.argv[1:]:
    r = comp_check.run(a, "&" + a, step=6)
    print(a, r["samples"], r["fails"], {k: v for k, v in r["worst"].items()}, flush=True)
