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
expected_sinks = {f"AES_FANOUT_T0003_LOAD_{index:02d}/A" for index in range(25)}
if answer.get("target_net") != "done":
    print("FAIL: expected target_net='done'")
    sys.exit(1)
if set(answer.get("target_sinks", [])) != expected_sinks:
    print("FAIL: target_sinks do not match the 25 injected load pins")
    sys.exit(1)
print("PASS")
