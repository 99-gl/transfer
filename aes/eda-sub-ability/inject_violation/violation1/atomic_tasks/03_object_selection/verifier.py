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

if answer.get("object_type") != "net":
    print(
        f"FAIL: expected object_type='net', "
        f"got {answer.get('object_type')!r}"
    )
    sys.exit(1)

if answer.get("object_name") != "_00140_":
    print(
        f"FAIL: expected object_name='_00140_', "
        f"got {answer.get('object_name')!r}"
    )
    sys.exit(1)

print("PASS")
sys.exit(0)