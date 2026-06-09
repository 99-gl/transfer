import argparse
import json

from datasets import load_dataset


def parse_args():
    parser = argparse.ArgumentParser(description="Summarize GSM8K answer lengths.")
    parser.add_argument("--dataset", default="gsm8k")
    parser.add_argument("--dataset-config", default="main")
    parser.add_argument("--split", default="test")
    parser.add_argument("--output", default=None, help="Optional json output path.")
    return parser.parse_args()


def percentile(sorted_values, pct):
    if not sorted_values:
        return None
    index = round((len(sorted_values) - 1) * pct / 100)
    return sorted_values[index]


def summarize(values):
    values = sorted(values)
    if not values:
        return {}
    return {
        "count": len(values),
        "min": values[0],
        "p50": percentile(values, 50),
        "p75": percentile(values, 75),
        "p90": percentile(values, 90),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
        "max": values[-1],
        "mean": round(sum(values) / len(values), 2),
    }


def split_answer(answer):
    if "####" not in answer:
        return answer, ""
    reasoning, final = answer.rsplit("####", 1)
    return reasoning.strip(), final.strip()


def main():
    args = parse_args()
    dataset = load_dataset(args.dataset, args.dataset_config, split=args.split)

    question_chars = []
    answer_chars = []
    reasoning_chars = []
    final_answer_chars = []

    for example in dataset:
        question = example["question"]
        answer = example["answer"]
        reasoning, final = split_answer(answer)

        question_chars.append(len(question))
        answer_chars.append(len(answer))
        reasoning_chars.append(len(reasoning))
        final_answer_chars.append(len(final))

    result = {
        "dataset": args.dataset,
        "dataset_config": args.dataset_config,
        "split": args.split,
        "question_chars": summarize(question_chars),
        "answer_chars": summarize(answer_chars),
        "reasoning_chars": summarize(reasoning_chars),
        "final_answer_chars": summarize(final_answer_chars),
    }

    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
