import argparse
import json
import multiprocessing as mp
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import torch
from datasets import load_dataset
from tqdm import tqdm
from transformers import AutoTokenizer


NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Zero-shot GSM8K baseline evaluation for Qwen-style instruct models."
    )
    parser.add_argument("--model", default="Qwen/Qwen3-4B-Instruct")
    parser.add_argument("--dataset", default="gsm8k")
    parser.add_argument("--dataset-config", default="main")
    parser.add_argument("--split", default="test")
    parser.add_argument("--output", default="outputs/gsm8k_baseline_qwen3_4b.jsonl")
    parser.add_argument(
        "--backend",
        choices=["transformers", "vllm"],
        default="transformers",
        help="Inference backend. vLLM is faster for large batched evaluation.",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help="Only used by the transformers backend. vLLM batches internally.",
    )
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--dtype",
        default="bfloat16",
        help="vLLM dtype, for example auto, float16, bfloat16, or float32.",
    )
    parser.add_argument("--tensor-parallel-size", type=int, default=1)
    parser.add_argument("--data-parallel-size", type=int, default=1)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.9)
    parser.add_argument("--max-model-len", type=int, default=None)
    parser.add_argument("--max-num-seqs", type=int, default=None)
    parser.add_argument("--max-num-batched-tokens", type=int, default=None)
    parser.add_argument(
        "--system-prompt",
        default=(
            "You are a careful math solver. Solve the problem step by step. "
            "Put only the final numeric answer inside <answer></answer>."
        ),
    )
    parser.add_argument(
        "--enable-thinking",
        action="store_true",
        help="Pass enable_thinking=True to chat templates that support it.",
    )
    parser.add_argument(
        "--trust-remote-code",
        action="store_true",
        help="Enable if the selected model requires custom modeling code.",
    )
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


def generate_with_transformers(args, tokenizer, prompts):
    from transformers import AutoModelForCausalLM

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        device_map="auto",
        trust_remote_code=args.trust_remote_code,
    )
    model.eval()

    do_sample = args.temperature > 0
    responses = []
    for batch_prompts in tqdm(
        batched(prompts, args.batch_size),
        total=(len(prompts) + args.batch_size - 1) // args.batch_size,
    ):
        encoded = tokenizer(
            batch_prompts,
            return_tensors="pt",
            padding=True,
            truncation=True,
        ).to(model.device)

        with torch.inference_mode():
            generated = model.generate(
                **encoded,
                max_new_tokens=args.max_new_tokens,
                do_sample=do_sample,
                temperature=args.temperature if do_sample else None,
                top_p=args.top_p if do_sample else None,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )

        new_tokens = generated[:, encoded.input_ids.shape[1] :]
        responses.extend(tokenizer.batch_decode(new_tokens, skip_special_tokens=True))

    return responses


def generate_with_vllm(args, prompts):
    if args.data_parallel_size > 1:
        return generate_with_vllm_data_parallel(args, prompts)

    try:
        from vllm import LLM, SamplingParams
    except ImportError as exc:
        raise ImportError(
            "vLLM is not installed. Install it with `pip install vllm`, "
            "preferably in a fresh Linux CUDA environment."
        ) from exc

    llm_kwargs = {
        "model": args.model,
        "tokenizer": args.model,
        "trust_remote_code": args.trust_remote_code,
        "dtype": args.dtype,
        "tensor_parallel_size": args.tensor_parallel_size,
        "gpu_memory_utilization": args.gpu_memory_utilization,
        "seed": args.seed,
    }
    if args.max_model_len is not None:
        llm_kwargs["max_model_len"] = args.max_model_len
    if args.max_num_seqs is not None:
        llm_kwargs["max_num_seqs"] = args.max_num_seqs
    if args.max_num_batched_tokens is not None:
        llm_kwargs["max_num_batched_tokens"] = args.max_num_batched_tokens

    llm = LLM(**llm_kwargs)
    sampling_params = SamplingParams(
        temperature=args.temperature,
        top_p=args.top_p,
        max_tokens=args.max_new_tokens,
    )
    outputs = llm.generate(prompts, sampling_params, use_tqdm=True)
    return [output.outputs[0].text for output in outputs]


def generate_with_vllm_data_parallel(args, prompts):
    indexed_prompts = list(enumerate(prompts))
    result_queue = mp.Queue()
    processes = []

    for rank in range(args.data_parallel_size):
        shard = indexed_prompts[rank:: args.data_parallel_size]
        process = mp.Process(
            target=vllm_data_parallel_worker,
            args=(rank, args, shard, result_queue),
        )
        process.start()
        processes.append(process)

    responses = [None] * len(prompts)
    errors = []
    for _ in processes:
        rank, local_responses, error = result_queue.get()
        if error:
            errors.append(f"rank {rank}: {error}")
        else:
            for original_index, response in local_responses:
                responses[original_index] = response

    for process in processes:
        process.join()

    failed_exits = [
        f"rank {rank}: exit code {process.exitcode}"
        for rank, process in enumerate(processes)
        if process.exitcode
    ]
    if errors or failed_exits:
        raise RuntimeError(
            "vLLM data-parallel generation failed:\n"
            + "\n".join(errors + failed_exits)
        )
    return responses


def vllm_data_parallel_worker(rank, args, indexed_prompts, result_queue):
    os.environ["VLLM_DP_RANK"] = str(rank)
    os.environ["VLLM_DP_RANK_LOCAL"] = str(rank)
    os.environ["VLLM_DP_SIZE"] = str(args.data_parallel_size)
    os.environ["VLLM_DP_MASTER_IP"] = "127.0.0.1"
    os.environ["VLLM_DP_MASTER_PORT"] = "29500"

    try:
        from vllm import LLM, SamplingParams

        llm_kwargs = {
            "model": args.model,
            "tokenizer": args.model,
            "trust_remote_code": args.trust_remote_code,
            "dtype": args.dtype,
            "tensor_parallel_size": args.tensor_parallel_size,
            "gpu_memory_utilization": args.gpu_memory_utilization,
            "seed": args.seed,
        }
        if args.max_model_len is not None:
            llm_kwargs["max_model_len"] = args.max_model_len
        if args.max_num_seqs is not None:
            llm_kwargs["max_num_seqs"] = args.max_num_seqs
        if args.max_num_batched_tokens is not None:
            llm_kwargs["max_num_batched_tokens"] = args.max_num_batched_tokens

        llm = LLM(**llm_kwargs)
        sampling_params = SamplingParams(
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.max_new_tokens,
        )
        local_prompts = [prompt for _, prompt in indexed_prompts]
        outputs = llm.generate(local_prompts, sampling_params, use_tqdm=(rank == 0))
        local_responses = [
            (original_index, output.outputs[0].text)
            for (original_index, _), output in zip(indexed_prompts, outputs)
        ]
        result_queue.put((rank, local_responses, None))
    except Exception as exc:
        result_queue.put((rank, [], repr(exc)))


def write_results(args, examples, responses, output_path):
    correct = 0
    parsed = 0
    total = 0

    with output_path.open("w", encoding="utf-8") as f:
        for example, response in zip(examples, responses):
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
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {
        "model": args.model,
        "backend": args.backend,
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
    torch.manual_seed(args.seed)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        trust_remote_code=args.trust_remote_code,
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"

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

    if args.backend == "vllm":
        responses = generate_with_vllm(args, prompts)
    else:
        responses = generate_with_transformers(args, tokenizer, prompts)

    metrics = write_results(args, examples, responses, output_path)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
