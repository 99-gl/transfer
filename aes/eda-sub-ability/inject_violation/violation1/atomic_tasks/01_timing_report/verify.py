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
    "check_type": "hold",
    "beginpoint": "text_in[23]",
    "endpoint": "_19212_/D",
    "slack_ns": -0.019,
    "path_group": "aes_clk"
}

errors = []

for key in ["check_type", "beginpoint", "endpoint", "path_group"]:
    if answer.get(key) != expected[key]:
        errors.append(
            f"{key}: expected {expected[key]!r}, got {answer.get(key)!r}"
        )

slack = answer.get("slack_ns")

if not isinstance(slack, (int, float)):
    errors.append("slack_ns must be numeric")
elif not math.isclose(slack, expected["slack_ns"], abs_tol=0.0011):
    errors.append(
        f"slack_ns: expected {expected['slack_ns']}, got {slack}"
    )

if errors:
    print("FAIL")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("PASS")