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

if answer.get("target_net") != "_00140_":
    print(
        f"FAIL: expected target_net='_00140_', "
        f"got {answer.get('target_net')!r}"
    )
    sys.exit(1)

expected_sinks = {"FE_PHC963_00140/A"}
actual_sinks = answer.get("target_sinks")

if not isinstance(actual_sinks, list):
    print("FAIL: target_sinks must be a JSON list")
    sys.exit(1)

if set(actual_sinks) != expected_sinks:
    print(
        f"FAIL: expected target_sinks={sorted(expected_sinks)!r}, "
        f"got {actual_sinks!r}"
    )
    sys.exit(1)

print("PASS")
sys.exit(0)