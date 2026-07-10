#!/usr/bin/env python3
"""Write the first N rows of a parquet file to a new parquet file."""

import argparse
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Read a parquet file and save only its first N rows."
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Input parquet file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output parquet file.",
    )
    parser.add_argument(
        "-n",
        "--num-rows",
        type=int,
        required=True,
        help="Number of rows to keep from the start of the file.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    return parser.parse_args()


def write_with_pyarrow(input_path, output_path, num_rows):
    import pyarrow as pa
    import pyarrow.parquet as pq

    parquet_file = pq.ParquetFile(input_path)
    if num_rows == 0:
        table = pa.Table.from_batches([], schema=parquet_file.schema_arrow)
        pq.write_table(table, output_path)
        return 0, parquet_file.metadata.num_rows

    batches = []
    rows_left = num_rows

    for batch in parquet_file.iter_batches(batch_size=min(num_rows, 8192)):
        if rows_left <= 0:
            break
        if batch.num_rows > rows_left:
            batch = batch.slice(0, rows_left)
        batches.append(batch)
        rows_left -= batch.num_rows

    table = pa.Table.from_batches(batches, schema=parquet_file.schema_arrow)
    pq.write_table(table, output_path)
    return table.num_rows, parquet_file.metadata.num_rows


def write_with_pandas(input_path, output_path, num_rows):
    import pandas as pd

    dataframe = pd.read_parquet(input_path)
    total_rows = len(dataframe)
    output = dataframe.head(num_rows)
    output.to_parquet(output_path, index=False)
    return len(output), total_rows


def main():
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if args.num_rows < 0:
        raise ValueError("--num-rows must be non-negative")
    if not input_path.exists():
        raise FileNotFoundError(f"Input parquet does not exist: {input_path}")
    if output_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"Output already exists: {output_path}. Pass --overwrite to replace it."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        written_rows, total_rows = write_with_pyarrow(input_path, output_path, args.num_rows)
    except ImportError:
        written_rows, total_rows = write_with_pandas(input_path, output_path, args.num_rows)

    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Total rows: {total_rows}")
    print(f"Written rows: {written_rows}")


if __name__ == "__main__":
    main()
