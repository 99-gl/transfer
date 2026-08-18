#!/usr/bin/env python3

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ANSWER = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "answer.json"
try:
    with ANSWER.open(encoding="utf-8") as f:
        answer = json.load(f)
except Exception as exc:
    print(f"FAIL: cannot read answer.json: {exc}")
    sys.exit(1)
expected = {
    "hold_timing": "unchanged",
    "setup_timing": "unchanged",
    "area": "increase",
    "power": "decrease",
    "congestion": "unchanged",
}
if any(answer.get(key) != value for key, value in expected.items()):
    print(f"FAIL: expected {expected!r}, got {answer!r}")
    sys.exit(1)
print("PASS")
