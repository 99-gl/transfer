import argparse
import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path


NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
ANSWER_TAG_RE = re.compile(r"<answer>\s*(.*?)\s*</answer>", flags=re.DOTALL | re.I)
OPEN_ANSWER_TAG_RE = re.compile(r"<answer\b", flags=re.I)
CLOSE_ANSWER_TAG_RE = re.compile(r"</answer>", flags=re.I)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Filter and summarize GSM8K baseline errors from a jsonl result file."
    )
    parser.add_argument(
        "--input",
        default="outputs/gsm8k_vllm_server_qwen3_4b.jsonl",
        help="Result jsonl produced by baseline_gsm8k_eval*.py.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/gsm8k_error_analysis",
        help="Directory for filtered jsonl files and summary.md.",
    )
    parser.add_argument(
        "--truncation-char-threshold",
        type=int,
        default=1800,
        help="Heuristic: long responses without a closed answer tag are flagged.",
    )
    parser.add_argument(
        "--preview",
        type=int,
        default=20,
        help="Number of wrong examples to include in summary.md.",
    )
    return parser.parse_args()


def normalize_number(value):
    value = value.strip().replace(",", "")
    try:
        decimal = Decimal(value)
    except InvalidOperation:
        return None

    if decimal == decimal.to_integral_value():
        return str(decimal.to_integral_value())
    return format(decimal.normalize(), "f")


def extract_numeric_answer(text):
    if text is None:
        return None
    matches = NUMBER_RE.findall(text.replace("$", "").replace("%", ""))
    if not matches:
        return None
    return normalize_number(matches[-1])


def numbers_in_text(text):
    if text is None:
        return []
    values = []
    for match in NUMBER_RE.findall(text.replace("$", "").replace("%", "")):
        parsed = normalize_number(match)
        if parsed is not None:
            values.append(parsed)
    return values


def same_number(left, right):
    if left is None or right is None:
        return False
    try:
        return Decimal(left) == Decimal(right)
    except InvalidOperation:
        return left == right


def get_record_id(index, record):
    return record.get("id", record.get("idx", index))


def response_ends_incompletely(response):
    stripped = (response or "").strip()
    if not stripped:
        return False
    if CLOSE_ANSWER_TAG_RE.search(stripped):
        return False
    return re.search(r'[.!?。！？;；)\]\}>"\']$|\d$', stripped) is None


def classify_record(record, truncation_char_threshold):
    response = record.get("response") or ""
    pred = record.get("prediction")
    gold = record.get("gold")
    correct = bool(record.get("correct"))
    finish_reason = record.get("finish_reason")

    open_tags = len(OPEN_ANSWER_TAG_RE.findall(response))
    closed_tags = len(ANSWER_TAG_RE.findall(response))
    has_closing_answer = CLOSE_ANSWER_TAG_RE.search(response) is not None
    extracted_from_response = extract_numeric_answer(response)
    response_numbers = numbers_in_text(response)
    finish_reason_length = finish_reason == "length"
    incomplete_ending = response_ends_incompletely(response)
    long_incomplete_response = (
        len(response) >= truncation_char_threshold
        and (not has_closing_answer or incomplete_ending)
    )

    issues = []
    if not correct:
        issues.append("wrong")
    if finish_reason_length:
        issues.append("finish_reason_length")
    if pred is None:
        issues.append("prediction_parse_failed")
    if gold is None:
        issues.append("gold_parse_failed")
    if open_tags == 0:
        issues.append("missing_answer_tag")
    if open_tags > 1 or closed_tags > 1:
        issues.append("multiple_answer_tags")
    if open_tags and not has_closing_answer:
        issues.append("unclosed_answer_tag")
    if open_tags and pred is None:
        issues.append("tagged_answer_parse_failed")
    if (
        not correct
        and gold is not None
        and any(same_number(number, gold) for number in response_numbers)
    ):
        issues.append("gold_number_mentioned_but_not_final")
    if (
        not correct
        and pred is not None
        and extracted_from_response is not None
        and not same_number(pred, extracted_from_response)
    ):
        issues.append("tag_answer_differs_from_last_number")
    if (
        not correct
        and long_incomplete_response
    ):
        issues.append("suspected_truncation_or_format_drift")
    if finish_reason_length or long_incomplete_response:
        issues.append("suspected_truncated_by_max_tokens")

    return issues


def load_jsonl(path):
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
            records.append(record)
    return records


def write_jsonl(path, records):
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def make_summary(records, wrong_records, issue_counts, preview):
    total = len(records)
    correct = total - len(wrong_records)
    parsed = sum(1 for record in records if record.get("prediction") is not None)
    accuracy = correct / total if total else 0.0
    parse_rate = parsed / total if total else 0.0

    lines = [
        "# GSM8K Error Analysis",
        "",
        f"- total: {total}",
        f"- correct: {correct}",
        f"- wrong: {len(wrong_records)}",
        f"- accuracy: {accuracy:.4f}",
        f"- parsed: {parsed}",
        f"- parse_rate: {parse_rate:.4f}",
        "",
        "## Issue Counts",
        "",
    ]

    if issue_counts:
        for issue, count in issue_counts.most_common():
            lines.append(f"- {issue}: {count}")
    else:
        lines.append("- none")

    lines.extend(["", "## Wrong Preview", ""])
    for record in wrong_records[:preview]:
        response = (record.get("response") or "").replace("\r\n", "\n").strip()
        question = (record.get("question") or "").strip()
        response_chars = record.get("_analysis_response_chars")
        lines.extend(
            [
                f"### Example {record['_analysis_id']}",
                "",
                f"- gold: {record.get('gold')}",
                f"- prediction: {record.get('prediction')}",
                f"- finish_reason: {record.get('finish_reason')}",
                f"- response_chars: {response_chars}",
                f"- issues: {', '.join(record['_analysis_issues'])}",
                "",
                "Question:",
                "",
                "```text",
                question,
                "```",
                "",
                "Response:",
                "",
                "```text",
                response,
                "```",
                "",
            ]
        )

    return "\n".join(lines)


def main():
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records = load_jsonl(input_path)
    issue_counts = Counter()
    wrong_records = []
    parse_failed_records = []
    format_issue_records = []
    truncated_or_length_records = []

    for index, record in enumerate(records):
        record["_analysis_response_chars"] = len(record.get("response") or "")
        issues = classify_record(record, args.truncation_char_threshold)
        record["_analysis_id"] = get_record_id(index, record)
        record["_analysis_issues"] = issues
        issue_counts.update(issues)

        if not record.get("correct"):
            wrong_records.append(record)
        if "prediction_parse_failed" in issues:
            parse_failed_records.append(record)
        if any(
            issue in issues
            for issue in (
                "missing_answer_tag",
                "multiple_answer_tags",
                "unclosed_answer_tag",
                "tagged_answer_parse_failed",
                "tag_answer_differs_from_last_number",
                "suspected_truncation_or_format_drift",
                "suspected_truncated_by_max_tokens",
            )
        ):
            format_issue_records.append(record)
        if any(
            issue in issues
            for issue in (
                "finish_reason_length",
                "suspected_truncated_by_max_tokens",
                "suspected_truncation_or_format_drift",
            )
        ):
            truncated_or_length_records.append(record)

    write_jsonl(output_dir / "wrong.jsonl", wrong_records)
    write_jsonl(output_dir / "parse_failed.jsonl", parse_failed_records)
    write_jsonl(output_dir / "format_issues.jsonl", format_issue_records)
    write_jsonl(output_dir / "truncated_or_length.jsonl", truncated_or_length_records)
    (output_dir / "summary.md").write_text(
        make_summary(records, wrong_records, issue_counts, args.preview),
        encoding="utf-8",
    )

    summary = {
        "input": str(input_path),
        "output_dir": str(output_dir),
        "total": len(records),
        "wrong": len(wrong_records),
        "parse_failed": len(parse_failed_records),
        "format_issues": len(format_issue_records),
        "truncated_or_length": len(truncated_or_length_records),
        "issue_counts": dict(issue_counts.most_common()),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
