#!/usr/bin/env python3
"""Parse Search-R1/verl console logs and draw PPO training curves.

The ``console`` logger writes lines such as::

    step:42 - critic/rewards/mean:0.625 - actor/ppo_kl:0.012

This script reads those lines directly.  A CSV copy is emitted for convenient
post-processing, but neither JSON nor Parquet is required before plotting.

Examples
--------
    # First edit LOG_FILE below, then run:
    python plot_training_log.py

Command-line arguments are optional overrides; the script is designed to be
configured by editing the constants below when it is copied to a server.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from collections import defaultdict
from pathlib import Path


# ============================ Server-side configuration ====================
# Change this to the log created by `tee`, `nohup`, or Slurm on your server.
LOG_FILE = Path("/path/to/your/experiment.log")

# None means: create `<log-file-stem>_curves` next to LOG_FILE.
OUTPUT_DIR: Path | None = None

# Empty list uses the curated PPO metrics in PPO_METRICS below.  Add exact
# names from `--list-metrics` here to plot only those metrics.
METRICS_TO_PLOT: list[str] = []
PLOT_ALL_METRICS = False       # True also plots timing_* and every other metric
EXPORT_PARSED_CSV = True       # CSV is optional; JSON/Parquet are unnecessary
SHOW_PLOT_WINDOWS = False      # Normally False on a headless server
# ============================================================================


# Metrics that are most useful for a PPO run.  Missing metrics are simply
# skipped: e.g. a run without a critic will not have critic/vf_* values.
PPO_METRICS = [
    "val/test_score",
    "critic/rewards/mean",
    "critic/score/mean",
    "actor/pg_loss",
    "actor/ppo_kl",
    "actor/pg_clipfrac",
    "actor/entropy_loss",
    "actor/kl_loss",
    "actor/lr",
    "critic/vf_loss",
    "critic/vf_explained_var",
    "critic/lr",
    "env/finish_ratio",
    "env/ratio_of_valid_action",
    "env/number_of_valid_search",
    "response_length/mean",
    "response_length/clip_ratio",
]

NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?|[-+]?(?:nan|inf)"
STEP_RE = re.compile(r"(?<!\w)step\s*:\s*(\d+)")
PAIR_RE = re.compile(rf"(?:^|\s-\s)([^:\s]+)\s*:\s*({NUMBER})(?=\s|$)", re.IGNORECASE)


def parse_log(path: Path) -> dict[str, dict[int, float]]:
    """Return metric -> {global_step: value}; later duplicate values win."""
    metrics: dict[str, dict[int, float]] = defaultdict(dict)
    matched_lines = 0

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            step_match = STEP_RE.search(line)
            if not step_match:
                continue
            step = int(step_match.group(1))
            pairs = PAIR_RE.findall(line)
            if not pairs:
                continue
            matched_lines += 1
            for name, raw_value in pairs:
                # The pair pattern can also see the leading ``step:42``.
                # It is the x-axis, never a metric series.
                if name == "step":
                    continue
                try:
                    metrics[name][step] = float(raw_value)
                except ValueError:
                    pass

    if not matched_lines:
        raise ValueError(
            "No Search-R1 console metric lines were found. Expected lines like "
            "`step:42 - actor/ppo_kl:0.012`."
        )
    return dict(metrics)


def choose_metrics(data: dict[str, dict[int, float]], requested: list[str], use_all: bool) -> list[str]:
    available = sorted(data)
    if requested:
        missing = [name for name in requested if name not in data]
        if missing:
            print("Warning: metric not found: " + ", ".join(missing), file=sys.stderr)
        return [name for name in requested if name in data]
    if use_all:
        return available

    selected: list[str] = []
    for wanted in PPO_METRICS:
        # val/test_score is a prefix because its final component is the data source.
        if wanted == "val/test_score":
            selected.extend(name for name in available if name.startswith("val/test_score/"))
        elif wanted in data:
            selected.append(wanted)
    return selected


def write_csv(data: dict[str, dict[int, float]], destination: Path) -> None:
    steps = sorted({step for series in data.values() for step in series})
    fields = ["step", *sorted(data)]
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for step in steps:
            writer.writerow({"step": step, **{name: data[name].get(step, "") for name in data}})


def safe_filename(metric: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", metric).strip("_")


def plot(data: dict[str, dict[int, float]], metrics: list[str], output_dir: Path, show: bool) -> list[Path]:
    try:
        import matplotlib
        if not show:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("matplotlib is required for plotting. Install it with: pip install matplotlib") from exc

    # A separate PNG per metric keeps scales interpretable (reward, KL and time
    # should not share an axis) and works well even when there are many metrics.
    images: list[Path] = []
    for metric in metrics:
        points = sorted((step, value) for step, value in data[metric].items() if math.isfinite(value))
        if not points:
            print(f"Skipping {metric}: it contains no finite values.", file=sys.stderr)
            continue
        steps, values = zip(*points)
        fig, axis = plt.subplots(figsize=(9, 4.8), constrained_layout=True)
        axis.plot(steps, values, linewidth=1.5, marker=".", markersize=3)
        axis.set(title=metric, xlabel="global step", ylabel=metric)
        axis.grid(True, alpha=0.3)
        image_path = output_dir / f"{safe_filename(metric)}.png"
        fig.savefig(image_path, dpi=160)
        images.append(image_path)
        if show:
            plt.show()
        plt.close(fig)
    return images


def main() -> int:
    parser = argparse.ArgumentParser(description="Draw PPO curves directly from a Search-R1 console log.")
    parser.add_argument(
        "log_file",
        nargs="?",
        type=Path,
        default=LOG_FILE,
        help="optional override for LOG_FILE configured at the top of this file",
    )
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR, help="optional override for OUTPUT_DIR")
    parser.add_argument("--metrics", nargs="+", default=METRICS_TO_PLOT, help="optional exact metric-name overrides")
    parser.add_argument("--all", action="store_true", default=PLOT_ALL_METRICS, help="plot every metric parsed from the log")
    parser.add_argument("--list-metrics", action="store_true", help="print available metric names and exit")
    parser.add_argument("--no-csv", action="store_true", default=not EXPORT_PARSED_CSV, help="do not export parsed_metrics.csv")
    parser.add_argument("--show", action="store_true", default=SHOW_PLOT_WINDOWS, help="also open each plot window (for a desktop environment)")
    args = parser.parse_args()

    if not args.log_file.is_file():
        parser.error(f"log file does not exist: {args.log_file}")
    try:
        data = parse_log(args.log_file)
    except ValueError as exc:
        parser.error(str(exc))

    if args.list_metrics:
        for name in sorted(data):
            print(f"{name}\t({len(data[name])} points)")
        return 0

    output_dir = args.output_dir or args.log_file.with_name(f"{args.log_file.stem}_curves")
    output_dir.mkdir(parents=True, exist_ok=True)
    if not args.no_csv:
        csv_path = output_dir / "parsed_metrics.csv"
        write_csv(data, csv_path)
        print(f"Saved parsed metrics: {csv_path}")

    metrics = choose_metrics(data, args.metrics, args.all)
    if not metrics:
        print("No requested/default PPO metrics were found. Use --list-metrics or --all.", file=sys.stderr)
        return 1
    try:
        images = plot(data, metrics, output_dir, args.show)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"Parsed {len(data)} metrics; saved {len(images)} curves to: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
