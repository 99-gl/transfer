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

if answer.get("root_cause") != "fanout":
    print(f"FAIL: expected root_cause='fanout', got {answer.get('root_cause')!r}")
    sys.exit(1)
if not answer.get("evidence"):
    print("FAIL: evidence must be non-empty")
    sys.exit(1)
print("PASS")
