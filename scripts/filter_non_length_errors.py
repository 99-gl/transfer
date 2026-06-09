import argparse
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Filter wrong GSM8K samples that were not stopped by length."
    )
    parser.add_argument(
        "--input",
        default="outputs/gsm8k_vllm_server_qwen3_4b.jsonl",
        help="Baseline result jsonl.",
    )
    parser.add_argument(
        "--output",
        default="outputs/gsm8k_error_analysis/non_length_errors.jsonl",
        help="Output jsonl for wrong samples whose finish_reason is not length.",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print filtered samples to the console.",
    )
    parser.add_argument(
        "--print-limit",
        type=int,
        default=None,
        help="Maximum number of filtered samples to print.",
    )
    return parser.parse_args()


def print_record(record, index):
    question = (record.get("question") or "").strip()
    response = (record.get("response") or "").strip()
    print("=" * 88)
    print(f"Example {index}")
    print(f"gold: {record.get('gold')}")
    print(f"prediction: {record.get('prediction')}")
    print(f"finish_reason: {record.get('finish_reason')}")
    print()
    print("Prompt:")
    print(question)
    print()
    print("Response:")
    print(response)
    print()


def main():
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    wrong = 0
    length_errors = 0
    kept = 0

    with input_path.open("r", encoding="utf-8") as src, output_path.open(
        "w", encoding="utf-8"
    ) as dst:
        for line in src:
            line = line.strip()
            if not line:
                continue

            total += 1
            record = json.loads(line)
            if record.get("correct"):
                continue

            wrong += 1
            if record.get("finish_reason") == "length":
                length_errors += 1
                continue

            kept += 1
            dst.write(json.dumps(record, ensure_ascii=False) + "\n")
            if args.print and (
                args.print_limit is None or kept <= args.print_limit
            ):
                print_record(record, kept)

    print(
        json.dumps(
            {
                "input": str(input_path),
                "output": str(output_path),
                "total": total,
                "wrong": wrong,
                "length_errors_removed": length_errors,
                "non_length_errors": kept,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
