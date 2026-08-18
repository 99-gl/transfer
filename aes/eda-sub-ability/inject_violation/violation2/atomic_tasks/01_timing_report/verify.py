#!/usr/bin/env python3

import json
import math
import sys

if len(sys.argv) != 2:
    print("Usage: verify.py answer.json")
    sys.exit(2)

with open(sys.argv[1], encoding="utf-8") as f:
    answer = json.load(f)

expected = {
    "check_type": "max_fanout",
    "net": "done",
    "driver": "_19478_/Q",
    "max_fanout": 16,
    "actual_fanout": 25,
    "fanout_slack": -9,
}
errors = []
for key in ["check_type", "net", "driver", "max_fanout", "actual_fanout"]:
    if answer.get(key) != expected[key]:
        errors.append(f"{key}: expected {expected[key]!r}, got {answer.get(key)!r}")
slack = answer.get("fanout_slack")
if not isinstance(slack, (int, float)) or not math.isclose(slack, expected["fanout_slack"], abs_tol=0.001):
    errors.append(f"fanout_slack: expected {expected['fanout_slack']}, got {slack!r}")
if errors:
    print("FAIL")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)
print("PASS")
