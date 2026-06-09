import argparse
import json
import re
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path

from datasets import load_dataset
from tqdm import tqdm
from transformers import AutoTokenizer


NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Zero-shot GSM8K evaluation through a running vLLM OpenAI server."
    )
    parser.add_argument("--model", default="Qwen/Qwen3-4B-Instruct")
    parser.add_argument("--served-model-name", default=None)
    parser.add_argument("--api-base", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--dataset", default="gsm8k")
    parser.add_argument("--dataset-config", default="main")
    parser.add_argument("--split", default="test")
    parser.add_argument("--output", default="outputs/gsm8k_vllm_server_qwen3_4b.jsonl")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument(
        "--system-prompt",
        default=(
            "You are a careful math solver. Solve the problem step by step. "
            "Put only the final numeric answer inside <answer></answer>."
        ),
    )
    parser.add_argument("--enable-thinking", action="store_true")
    parser.add_argument("--trust-remote-code", action="store_true")
    return parser.parse_args()


def build_prompt(tokenizer, question, system_prompt, enable_thinking):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Problem:\n{question}"},
    ]

    if getattr(tokenizer, "chat_template", None):
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=enable_thinking,
        )

    return (
        f"{system_prompt}\n\n"
        f"Problem:\n{question}\n\n"
        "Solution:\n"
    )


def extract_gold_answer(answer_text):
    if "####" in answer_text:
        answer_text = answer_text.split("####")[-1]
    return extract_numeric_answer(answer_text)


def extract_pred_answer(text):
    tagged = re.search(r"<answer>\s*(.*?)\s*</answer>", text, flags=re.DOTALL | re.I)
    if tagged:
        parsed = extract_numeric_answer(tagged.group(1))
        if parsed is not None:
            return parsed
    return extract_numeric_answer(text)


def extract_numeric_answer(text):
    matches = NUMBER_RE.findall(text.replace("$", "").replace("%", ""))
    if not matches:
        return None
    return normalize_number(matches[-1])


def normalize_number(value):
    value = value.strip().replace(",", "")
    try:
        decimal = Decimal(value)
    except InvalidOperation:
        return None

    if decimal == decimal.to_integral_value():
        return str(decimal.to_integral_value())
    return format(decimal.normalize(), "f")


def answers_match(pred, gold):
    if pred is None or gold is None:
        return False
    try:
        return Decimal(pred) == Decimal(gold)
    except InvalidOperation:
        return pred == gold


def batched(items, batch_size):
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def post_json(url, payload, timeout):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def generate_with_vllm_server(args, prompts):
    url = args.api_base.rstrip("/") + "/completions"
    request_model = args.served_model_name or args.model
    completions = []

    for batch_prompts in tqdm(
        batched(prompts, args.batch_size),
        total=(len(prompts) + args.batch_size - 1) // args.batch_size,
    ):
        data = post_json(
            url,
            {
                "model": request_model,
                "prompt": batch_prompts,
                "temperature": args.temperature,
                "top_p": args.top_p,
                "max_tokens": args.max_new_tokens,
            },
            args.timeout,
        )
        choices = sorted(data["choices"], key=lambda choice: choice["index"])
        completions.extend(
            {
                "text": choice.get("text", ""),
                "finish_reason": choice.get("finish_reason"),
                "stop_reason": choice.get("stop_reason"),
            }
            for choice in choices
        )

    return completions


def write_results(args, examples, completions, output_path):
    correct = 0
    parsed = 0
    total = 0

    with output_path.open("w", encoding="utf-8") as f:
        for example, completion in zip(examples, completions):
            if isinstance(completion, dict):
                response = completion.get("text", "")
                finish_reason = completion.get("finish_reason")
                stop_reason = completion.get("stop_reason")
            else:
                response = completion
                finish_reason = None
                stop_reason = None

            gold = extract_gold_answer(example["answer"])
            pred = extract_pred_answer(response)
            is_correct = answers_match(pred, gold)

            total += 1
            correct += int(is_correct)
            parsed += int(pred is not None)

            record = {
                "question": example["question"],
                "gold_answer_text": example["answer"],
                "gold": gold,
                "prediction": pred,
                "correct": is_correct,
                "response": response,
                "finish_reason": finish_reason,
                "stop_reason": stop_reason,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {
        "model": args.model,
        "api_base": args.api_base,
        "dataset": args.dataset,
        "dataset_config": args.dataset_config,
        "split": args.split,
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else 0.0,
        "parsed": parsed,
        "parse_rate": parsed / total if total else 0.0,
        "output": str(output_path),
    }


def main():
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        trust_remote_code=args.trust_remote_code,
    )

    dataset = load_dataset(args.dataset, args.dataset_config, split=args.split)
    if args.limit is not None:
        dataset = dataset.select(range(min(args.limit, len(dataset))))

    examples = list(dataset)
    prompts = [
        build_prompt(
            tokenizer,
            example["question"],
            args.system_prompt,
            args.enable_thinking,
        )
        for example in examples
    ]

    completions = generate_with_vllm_server(args, prompts)
    metrics = write_results(args, examples, completions, output_path)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
