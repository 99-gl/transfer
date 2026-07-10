#!/usr/bin/env python3
"""Print the first rows of a parquet file."""

import argparse
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Read a parquet file and print its first rows."
    )
    parser.add_argument(
        "input",
        help="Input parquet file.",
    )
    parser.add_argument(
        "-n",
        "--num-rows",
        type=int,
        default=10,
        help="Number of rows to print. Defaults to 10.",
    )
    return parser.parse_args()


def json_safe(value):
    try:
        import numpy as np

        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
    except ImportError:
        pass
    return value


def main():
    args = parse_args()
    input_path = Path(args.input)

    if args.num_rows < 0:
        raise ValueError("--num-rows must be non-negative")
    if not input_path.exists():
        raise FileNotFoundError(f"Input parquet does not exist: {input_path}")

    try:
        import pyarrow.parquet as pq

        table = pq.read_table(input_path).slice(0, args.num_rows)
        rows = table.to_pylist()
        total_rows = pq.ParquetFile(input_path).metadata.num_rows
    except ImportError:
        import pandas as pd

        dataframe = pd.read_parquet(input_path)
        total_rows = len(dataframe)
        rows = dataframe.head(args.num_rows).to_dict(orient="records")

    print(f"Input: {input_path}")
    print(f"Total rows: {total_rows}")
    print(f"Printed rows: {len(rows)}")
    for idx, row in enumerate(rows):
        print(f"\n[{idx}]")
        print(json.dumps(row, ensure_ascii=False, indent=2, default=json_safe))


if __name__ == "__main__":
    main()
