#!/usr/bin/env python3
# Usage:
#   python serve.py --model /path/to/model --sglang-url http://127.0.0.1:30000 --output-dir data

"""Run the standalone adapter service."""

from __future__ import annotations

import argparse
import logging

from aiohttp import web
from transformers import AutoTokenizer

from adapter_service import AdapterServer
from adapter_service.models import OutputParserConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenAI/Anthropic to SGLang adapter with JSONL trajectory recording")
    parser.add_argument("--model", required=True, help="Hugging Face tokenizer/model path used by SGLang")
    parser.add_argument("--sglang-url", required=True, help="Base URL of the SGLang server or router")
    parser.add_argument("--output-dir", required=True, help="Directory that will contain trajectories/<trajectory-id>.jsonl files")
    parser.add_argument(
        "--tool-call-parser",
        help="SGLang tool-call parser for this model; must match the model server's --tool-call-parser setting",
    )
    parser.add_argument(
        "--reasoning-parser",
        help="SGLang reasoning parser for this model; must match the model server's --reasoning-parser setting",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=18001, help="Bind port")
    parser.add_argument("--trust-remote-code", action="store_true", help="Pass trust_remote_code=True to AutoTokenizer")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=args.trust_remote_code)
    server = AdapterServer(
        tokenizer=tokenizer,
        sglang_url=args.sglang_url,
        output_dir=args.output_dir,
        parser_config=OutputParserConfig(
            tool_call_parser=args.tool_call_parser,
            reasoning_parser=args.reasoning_parser,
        ),
    )
    web.run_app(server.app, host=args.host, port=args.port, handler_cancellation=True)


if __name__ == "__main__":
    main()
