#!/usr/bin/env python3
"""Minimal stdio MCP server exposing YAI Scout freshness_check as a tool.

This intentionally uses only the standard library so it works without an MCP
Python SDK. It speaks newline-delimited JSON-RPC over stdin/stdout.

Environment:
  YAI_SCOUT_URL   default http://127.0.0.1:8010
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from typing import Any

TOOL = {
    "name": "freshness_check",
    "description": "Check an LLM answer for stale claims using YAI Scout.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "as_of": {"type": "string"},
            "max_claims": {"type": "integer", "minimum": 1, "maximum": 10},
        },
        "required": ["answer"],
    },
}


def call_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    base = os.environ.get("YAI_SCOUT_URL", "http://127.0.0.1:8010").rstrip("/")
    payload = {
        "answer": str(arguments["answer"]),
        "as_of": str(arguments.get("as_of") or ""),
        "max_claims": int(arguments.get("max_claims") or 3),
        "mode": "live",
    }
    request = urllib.request.Request(
        base + "/freshness/verify",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        report = json.loads(response.read().decode())
    text = "\n".join(
        f"{verdict['status']}: {verdict.get('rationale', '')}"
        for verdict in report.get("verdicts", [])
    )
    return {"content": [{"type": "text", "text": text or "INSUFFICIENT"}], "report": report}


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "yai-scout-freshness", "version": "0.1"},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": [TOOL]}}
    if method == "tools/call":
        params = message.get("params") or {}
        if params.get("name") != "freshness_check":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": "unknown tool"},
            }
        try:
            result = call_tool(params.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as exc:  # noqa: BLE001
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": str(exc)},
            }
    if request_id is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": "method not found"},
    }


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
            response = handle(message)
        except Exception as exc:  # noqa: BLE001
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": str(exc)},
            }
        if response is not None:
            print(json.dumps(response), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
