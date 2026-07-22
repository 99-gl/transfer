#!/usr/bin/env python3
"""查看 JSONL 文件的首条记录结构或指定字段的值。

示例：
    python scripts/inspect_jsonl.py data.jsonl
    python scripts/inspect_jsonl.py data.jsonl --line 10 --field messages.0.content
"""

import argparse
import json
from pathlib import Path
from typing import Any


def read_record(path: Path, line_number: int) -> Any:
    """读取指定的非空 JSONL 记录；行号从 1 开始。"""
    if line_number < 1:
        raise ValueError("行号必须大于等于 1")

    record_number = 0
    # ``utf-8-sig`` 兼容部分 Windows 工具写入的 UTF-8 BOM，同时也可读取普通 UTF-8。
    with path.open("r", encoding="utf-8-sig") as file:
        for physical_line, raw_line in enumerate(file, start=1):
            if not raw_line.strip():
                continue
            record_number += 1
            if record_number != line_number:
                continue
            try:
                return json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"文件第 {physical_line} 行不是合法 JSON：{exc.msg}") from exc

    raise ValueError(f"文件中只有 {record_number} 条非空记录，找不到第 {line_number} 条")


def print_structure(value: Any, indent: int = 0) -> None:
    """仅打印字典的键；嵌套字典继续展开。"""
    prefix = "  " * indent
    if not isinstance(value, dict):
        print(f"{prefix}<顶层不是对象：{type(value).__name__}>")
        return

    for key, child in value.items():
        if isinstance(child, dict):
            print(f"{prefix}{key}:")
            print_structure(child, indent + 1)
        else:
            print(f"{prefix}{key}")


def get_field(record: Any, field_path: str) -> Any:
    """按点号路径取字段；列表可用数字下标，例如 messages.0.content。"""
    current = record
    for part in field_path.split("."):
        if isinstance(current, dict):
            if part not in current:
                raise KeyError(f"找不到字段 {part!r}")
            current = current[part]
        elif isinstance(current, list):
            try:
                index = int(part)
                current = current[index]
            except (ValueError, IndexError) as exc:
                raise KeyError(f"列表中无法访问下标 {part!r}") from exc
        else:
            raise KeyError(f"访问 {part!r} 前的值不是对象或列表")
    return current


def main() -> None:
    parser = argparse.ArgumentParser(description="查看 JSONL 数据结构或指定字段")
    parser.add_argument("jsonl_file", type=Path, help="JSONL 文件路径")
    parser.add_argument("--line", type=int, help="要读取的非空记录编号（从 1 开始）")
    parser.add_argument(
        "--field",
        help="要打印的字段路径，使用点号分隔；列表下标也可用点号，如 messages.0.content",
    )
    args = parser.parse_args()

    if (args.line is None) != (args.field is None):
        parser.error("--line 和 --field 必须同时使用；不传时打印第 1 条记录的结构")
    if not args.jsonl_file.is_file():
        parser.error(f"文件不存在：{args.jsonl_file}")

    try:
        if args.line is None:
            print("第 1 条非空记录的键结构：")
            print_structure(read_record(args.jsonl_file, 1))
        else:
            value = get_field(read_record(args.jsonl_file, args.line), args.field)
            print(json.dumps(value, ensure_ascii=False, indent=2, default=str))
    except (ValueError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
