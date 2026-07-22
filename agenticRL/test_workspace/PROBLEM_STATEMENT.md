# Fix `format_duration`

The function `format_duration` in `duration.py` should turn a non-negative
integer number of seconds into a compact, human-readable duration.

Examples:

```text
0    -> "0s"
59   -> "59s"
60   -> "1m 0s"
61   -> "1m 1s"
3600 -> "1h 0m 0s"
3661 -> "1h 1m 1s"
```

The current implementation produces incorrect results for durations of one
minute or longer. Fix the implementation without changing the public function
name or adding third-party dependencies.

Run the test suite with:

```bash
pytest -q
```
