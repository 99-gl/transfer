"""End-to-end checks for the standalone adapter without slime imports."""

from __future__ import annotations

import json
import hashlib
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from adapter_service import AdapterServer
from adapter_service.models import OutputParserConfig, ParsedOutput
from adapter_service.parsing import parse_model_output
from adapter_service.recording import JsonlRecorder


class FakeTokenizer:
    def apply_chat_template(self, messages, *, tools, tokenize, add_generation_prompt):
        self.messages = messages
        self.tools = tools
        return [10, 11, 12]

    def decode(self, token_ids, *, skip_special_tokens):
        return {101: "hello", 201: "world"}.get(token_ids[0], "") if token_ids else ""


class AdapterServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests = []

        async def generate(request):
            self.requests.append(await request.json())
            return web.json_response(
                {
                    "meta_info": {
                        "output_token_logprobs": [[-0.25, 101]],
                        "finish_reason": {"type": "stop"},
                    }
                }
            )

        self.upstream = TestServer(web.Application())
        self.upstream.app.router.add_post("/generate", generate)
        await self.upstream.start_server()
        self.output_dir = Path(__file__).parent / "_test_trajectory_output"
        shutil.rmtree(self.output_dir, ignore_errors=True)
        self.adapter = AdapterServer(tokenizer=FakeTokenizer(), sglang_url=str(self.upstream.make_url("")), output_dir=self.output_dir)
        self.client = TestClient(TestServer(self.adapter.app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        await self.upstream.close()
        shutil.rmtree(self.output_dir, ignore_errors=True)

    async def test_openai_response_and_jsonl_record(self):
        response = await self.client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer session-1"},
            json={"model": "test", "max_tokens": 7, "messages": [{"role": "user", "content": "hi"}]},
        )
        payload = await response.json()

        self.assertEqual(response.status, 200)
        self.assertEqual(payload["choices"][0]["message"]["content"], "hello")
        self.assertEqual(self.requests[0]["input_ids"], [10, 11, 12])
        self.assertEqual(self.requests[0]["sampling_params"]["max_new_tokens"], 7)

        trajectory_id = hashlib.sha256(b"session-1").hexdigest()
        log_path = self.adapter.recorder.path_for_trajectory(trajectory_id)
        record = json.loads(log_path.read_text(encoding="utf-8"))
        self.assertEqual(record["protocol"], "openai")
        self.assertEqual(record["trajectory_id"], trajectory_id)
        self.assertEqual(record["prompt_token_ids"], [10, 11, 12])
        self.assertEqual(record["output_token_ids"], [101])
        self.assertEqual(record["output_logprobs"], [-0.25])
        self.assertEqual(record["parser_config"], {"tool_call_parser": None, "reasoning_parser": None})
        self.assertEqual(record["request"]["messages"][0]["content"], "hi")
        self.assertEqual(record["turn_index"], 1)

        second = await self.client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer session-1"},
            json={"model": "test", "max_tokens": 7, "messages": [{"role": "user", "content": "again"}]},
        )
        self.assertEqual(second.status, 200)
        records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([item["turn_index"] for item in records], [1, 2])

        self.assertNotEqual(log_path, self.adapter.recorder.path_for_trajectory("other-trajectory"))

        restarted_recorder = JsonlRecorder(self.output_dir)
        self.assertEqual(await restarted_recorder.write(trajectory_id, {"schema_version": 1}), 3)
        records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([item["turn_index"] for item in records], [1, 2, 3])

    async def test_anthropic_request_is_converted(self):
        response = await self.client.post(
            "/v1/messages",
            headers={"Authorization": "Bearer session-2", "X-Api-Key": "fallback-key"},
            json={"model": "test", "max_tokens": 9, "system": "rules", "messages": [{"role": "user", "content": "hello"}]},
        )
        payload = await response.json()

        self.assertEqual(response.status, 200)
        self.assertEqual(payload["content"], [{"type": "text", "text": "hello"}])
        self.assertEqual(self.adapter.tokenizer.messages[0], {"role": "system", "content": "rules"})
        self.assertEqual(self.adapter.tokenizer.messages[1], {"role": "user", "content": "hello"})
        trajectory_id = hashlib.sha256(b"session-2").hexdigest()
        record = json.loads(self.adapter.recorder.path_for_trajectory(trajectory_id).read_text(encoding="utf-8"))
        self.assertEqual(record["trajectory_id"], trajectory_id)

    def test_xml_fallback_parses_tool_call_without_sglang_parser(self):
        parsed = parse_model_output(
            "before <tool_call><function=lookup><parameter=q>adapter</parameter></function></tool_call> after",
            [{"type": "function", "function": {"name": "lookup"}}],
            OutputParserConfig(),
        )
        self.assertEqual(parsed.text, "before  after")
        self.assertEqual(parsed.tool_uses, [{"name": "lookup", "input": {"q": "adapter"}}])

    async def test_configured_parsers_are_passed_to_parsing_and_recorded(self):
        config = OutputParserConfig(tool_call_parser="model-tool-parser", reasoning_parser="model-reasoning-parser")
        self.adapter.parser_config = config
        with patch("adapter_service.server.parse_model_output", return_value=ParsedOutput("reasoning", "hello", [])) as parser:
            response = await self.client.post(
                "/v1/chat/completions",
                headers={"Authorization": "Bearer parser-session"},
                json={"model": "test", "messages": [{"role": "user", "content": "hi"}]},
            )

        self.assertEqual(response.status, 200)
        self.assertEqual(parser.call_args.args[2], config)
        trajectory_id = hashlib.sha256(b"parser-session").hexdigest()
        record = json.loads(self.adapter.recorder.path_for_trajectory(trajectory_id).read_text(encoding="utf-8"))
        self.assertEqual(record["parser_config"], {"tool_call_parser": "model-tool-parser", "reasoning_parser": "model-reasoning-parser"})


if __name__ == "__main__":
    unittest.main()
