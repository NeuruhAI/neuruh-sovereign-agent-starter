"""Stdio MCP adapter for the three public micro-plugin functions.

This module is a JSON-RPC 2.0 / MCP stdio wrapper.  It does not reimplement
context packing, route selection, or proof-card projection — it imports and
calls the existing functions in ``micro_plugins``.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Mapping

from .micro_plugins import (
    choose_cheapest_capable_route,
    compile_context_packet,
    public_proof_card,
)

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "neuruh-public-micro-plugins"
SERVER_VERSION = "0.1.4-alpha"
TOOL_NAMES = ("context_pack", "cheap_route", "proof_card")

CONTEXT_PACK_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["state"],
    "properties": {
        "state": {
            "type": "object",
            "additionalProperties": True,
            "properties": {
                "mission_id": {"type": "string"},
                "objective": {"type": "string"},
                "current_state": {},
                "changed_since_last_run": {"type": "array"},
                "canonical_refs": {"type": "array", "items": {"type": "string"}},
                "known_failures": {"type": "array"},
                "blockers": {"type": "array"},
                "authority": {},
                "budget": {},
                "acceptance_test": {},
                "next_action": {"type": "string"},
            },
        },
        "max_bytes": {"type": "integer", "minimum": 256, "default": 4096},
    },
}

CHEAP_ROUTE_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["candidates"],
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["candidate_id", "layer"],
                "properties": {
                    "candidate_id": {"type": "string"},
                    "layer": {"type": "string", "enum": ["L0", "L1", "L2", "L3", "L4"]},
                    "success_probability": {"type": "number", "minimum": 0, "maximum": 1},
                    "expected_value_usd": {"type": "number", "minimum": 0},
                    "execution_cost_usd": {"type": "number", "minimum": 0},
                    "model_cost_usd": {"type": "number", "minimum": 0},
                    "risk_cost_usd": {"type": "number", "minimum": 0},
                    "founder_minutes": {"type": "number", "minimum": 0},
                    "latency_minutes": {"type": "number", "minimum": 0},
                },
            },
        },
        "minimum_success_probability": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "default": 0.8,
        },
        "founder_minute_cost_usd": {"type": "number", "minimum": 0},
        "latency_minute_cost_usd": {"type": "number", "minimum": 0},
    },
}

PROOF_CARD_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["record"],
    "properties": {
        "record": {
            "type": "object",
            "additionalProperties": True,
            "properties": {
                "mission": {},
                "mission_id": {"type": "string"},
                "artifact": {},
                "version": {"type": "string"},
                "status": {"type": "string"},
                "outcome": {},
                "commit_sha": {"type": "string"},
                "tests": {},
                "public_url": {"type": "string"},
                "limitations": {},
                "generated_at": {"type": "string"},
            },
        },
        "extra_allow": {"type": "array", "items": {"type": "string"}},
    },
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "context_pack",
        "description": (
            "Compile a bounded pointer-heavy execution packet. "
            "Calls compile_context_packet. Refuses transcript/chat keys."
        ),
        "inputSchema": CONTEXT_PACK_INPUT_SCHEMA,
    },
    {
        "name": "cheap_route",
        "description": (
            "Choose the highest net-value candidate above a capability floor. "
            "Calls choose_cheapest_capable_route."
        ),
        "inputSchema": CHEAP_ROUTE_INPUT_SCHEMA,
    },
    {
        "name": "proof_card",
        "description": (
            "Project a record through the public proof-card allowlist. "
            "Calls public_proof_card. Unknown fields are omitted."
        ),
        "inputSchema": PROOF_CARD_INPUT_SCHEMA,
    },
]


def _ok(id_: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _error(id_: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def _tool_text(value: Any, *, is_error: bool = False) -> dict[str, Any]:
    payload = {
        "content": [
            {
                "type": "text",
                "text": json.dumps(value, sort_keys=True, ensure_ascii=False),
            }
        ]
    }
    if is_error:
        payload["isError"] = True
    return payload


def _call_context_pack(arguments: Mapping[str, Any]) -> dict[str, Any]:
    state = arguments.get("state")
    kwargs: dict[str, Any] = {}
    if "max_bytes" in arguments:
        kwargs["max_bytes"] = arguments["max_bytes"]
    return compile_context_packet(state, **kwargs)


def _call_cheap_route(arguments: Mapping[str, Any]) -> dict[str, Any]:
    candidates = arguments.get("candidates")
    kwargs: dict[str, Any] = {}
    for key in (
        "minimum_success_probability",
        "founder_minute_cost_usd",
        "latency_minute_cost_usd",
    ):
        if key in arguments:
            kwargs[key] = arguments[key]
    return choose_cheapest_capable_route(candidates, **kwargs).as_dict()


def _call_proof_card(arguments: Mapping[str, Any]) -> dict[str, Any]:
    record = arguments.get("record")
    kwargs: dict[str, Any] = {}
    if "extra_allow" in arguments:
        kwargs["extra_allow"] = arguments["extra_allow"]
    return public_proof_card(record, **kwargs)


_DISPATCH = {
    "context_pack": _call_context_pack,
    "cheap_route": _call_cheap_route,
    "proof_card": _call_proof_card,
}


def handle_rpc(message: Mapping[str, Any]) -> dict[str, Any] | None:
    """Handle one JSON-RPC message. Notifications return None."""
    if not isinstance(message, Mapping) or message.get("jsonrpc") != "2.0":
        return _error(message.get("id") if isinstance(message, Mapping) else None, -32600, "Invalid Request")

    method = message.get("method")
    id_ = message.get("id")
    params = message.get("params") or {}
    if id_ is None:
        return None

    if method == "initialize":
        return _ok(
            id_,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )
    if method == "ping":
        return _ok(id_, {})
    if method == "tools/list":
        return _ok(id_, {"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        handler = _DISPATCH.get(name)
        if handler is None:
            return _error(id_, -32602, f"unknown tool: {name}")
        if not isinstance(arguments, Mapping):
            return _error(id_, -32602, "arguments must be an object")
        try:
            return _ok(id_, _tool_text(handler(arguments)))
        except (TypeError, ValueError) as exc:
            return _ok(id_, _tool_text({"error": str(exc)}, is_error=True))
    return _error(id_, -32601, f"Method not found: {method}")


def _read_message(stdin) -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = stdin.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        decoded = line.decode("ascii")
        key, _, value = decoded.partition(":")
        headers[key.strip().lower()] = value.strip()
    length = int(headers["content-length"])
    body = stdin.read(length)
    return json.loads(body.decode("utf-8"))


def _write_message(stdout, message: Mapping[str, Any]) -> None:
    body = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    stdout.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
    stdout.flush()


def serve_stdio(stdin=None, stdout=None) -> None:
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    while True:
        try:
            message = _read_message(stdin)
        except (OSError, ValueError, json.JSONDecodeError, KeyError, UnicodeDecodeError):
            break
        if message is None:
            break
        response = handle_rpc(message)
        if response is not None:
            _write_message(stdout, response)


def main() -> int:
    serve_stdio()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
