import io
import json
import os
import socket
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from neuruh_sovereign_agent_starter import mcp_server, micro_plugins
from neuruh_sovereign_agent_starter.micro_plugins import (
    choose_cheapest_capable_route,
    compile_context_packet,
    public_proof_card,
)

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_TOKENS = (
    "axon",
    "mother",
    "iar",
    "deedsonar",
    "jgi",
    "governance-core",
    "governance_core",
)


def _rpc(method, *, id_=1, params=None):
    message = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params is not None:
        message["params"] = params
    return mcp_server.handle_rpc(message)


def _tool_payload(response):
    text = response["result"]["content"][0]["text"]
    return json.loads(text)


def _write_rpc(raw: bytes) -> bytes:
    return f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii") + raw


class McpProtocolTests(unittest.TestCase):
    def test_initialize_tools_list_and_call(self):
        init = _rpc("initialize", params={"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test"}})
        self.assertEqual(init["result"]["serverInfo"]["name"], "neuruh-public-micro-plugins")
        self.assertIsNone(mcp_server.handle_rpc({"jsonrpc": "2.0", "method": "notifications/initialized"}))

        listed = _rpc("tools/list", id_=2)
        names = [tool["name"] for tool in listed["result"]["tools"]]
        self.assertEqual(names, ["context_pack", "cheap_route", "proof_card"])
        for tool in listed["result"]["tools"]:
            schema = tool["inputSchema"]
            self.assertEqual(schema["type"], "object")
            self.assertIn("properties", schema)
            self.assertTrue(schema.get("required"))

        mission = json.loads((ROOT / "examples/mission-packet.synthetic.json").read_text(encoding="utf-8"))
        packed = _rpc("tools/call", id_=3, params={"name": "context_pack", "arguments": {"state": mission}})
        self.assertEqual(_tool_payload(packed)["mission_id"], "PACK-001")
        self.assertNotIn("giant_payload", _tool_payload(packed))

        candidates = json.loads((ROOT / "examples/route-candidates.synthetic.json").read_text(encoding="utf-8"))
        routed = _rpc("tools/call", id_=4, params={"name": "cheap_route", "arguments": {"candidates": candidates}})
        self.assertEqual(_tool_payload(routed)["candidate_id"], "deterministic-l0")

        receipt = json.loads((ROOT / "examples/internal-receipt.synthetic.json").read_text(encoding="utf-8"))
        card = _rpc("tools/call", id_=5, params={"name": "proof_card", "arguments": {"record": receipt}})
        payload = _tool_payload(card)
        self.assertEqual(payload["status"], "PASS")
        self.assertNotIn("private_recipe", payload)
        self.assertNotIn("prompt", payload)
        self.assertNotIn("axon_route", payload)

    def test_stdio_initialize_list_and_call(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        proc = subprocess.Popen(
            [sys.executable, "-m", "neuruh_sovereign_agent_starter.mcp_server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        self.addCleanup(proc.kill)
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "context_pack", "arguments": {"state": {"mission_id": "STDIO", "objective": "roundtrip"}}},
            },
        ]
        blob = b"".join(_write_rpc(json.dumps(m).encode("utf-8")) for m in messages)
        stdout, stderr = proc.communicate(blob, timeout=10)
        self.assertEqual(proc.returncode, 0, stderr.decode("utf-8", errors="replace"))
        decoded = []
        buf = stdout
        while buf:
            header, _, rest = buf.partition(b"\r\n\r\n")
            self.assertIn(b"Content-Length:", header)
            length = int(header.split(b":", 1)[1].strip())
            body, buf = rest[:length], rest[length:]
            decoded.append(json.loads(body))
        self.assertEqual(len(decoded), 3)
        self.assertEqual(decoded[0]["result"]["serverInfo"]["name"], "neuruh-public-micro-plugins")
        self.assertEqual([t["name"] for t in decoded[1]["result"]["tools"]], list(mcp_server.TOOL_NAMES))
        self.assertEqual(json.loads(decoded[2]["result"]["content"][0]["text"])["mission_id"], "STDIO")


class McpDelegationTests(unittest.TestCase):
    def test_imported_functions_are_the_released_primitives(self):
        self.assertIs(mcp_server.compile_context_packet, micro_plugins.compile_context_packet)
        self.assertIs(mcp_server.choose_cheapest_capable_route, micro_plugins.choose_cheapest_capable_route)
        self.assertIs(mcp_server.public_proof_card, micro_plugins.public_proof_card)
        self.assertIs(mcp_server.compile_context_packet, compile_context_packet)
        self.assertIs(mcp_server.choose_cheapest_capable_route, choose_cheapest_capable_route)
        self.assertIs(mcp_server.public_proof_card, public_proof_card)

    def test_context_pack_calls_compile_context_packet(self):
        with patch.object(mcp_server, "compile_context_packet", return_value={"mission_id": "MOCK"}) as mocked:
            response = _rpc("tools/call", params={"name": "context_pack", "arguments": {"state": {"mission_id": "X"}, "max_bytes": 512}})
            mocked.assert_called_once_with({"mission_id": "X"}, max_bytes=512)
            self.assertEqual(_tool_payload(response)["mission_id"], "MOCK")

    def test_cheap_route_calls_choose_cheapest_capable_route(self):
        decision = micro_plugins.RouteDecision("id", "L0", 1.0, 2.0, 0.1)
        with patch.object(mcp_server, "choose_cheapest_capable_route", return_value=decision) as mocked:
            response = _rpc(
                "tools/call",
                params={
                    "name": "cheap_route",
                    "arguments": {"candidates": [{"candidate_id": "id", "layer": "L0"}], "minimum_success_probability": 0.9},
                },
            )
            mocked.assert_called_once_with([{"candidate_id": "id", "layer": "L0"}], minimum_success_probability=0.9)
            self.assertEqual(_tool_payload(response)["candidate_id"], "id")

    def test_proof_card_calls_public_proof_card(self):
        with patch.object(mcp_server, "public_proof_card", return_value={"status": "MOCK"}) as mocked:
            response = _rpc(
                "tools/call",
                params={"name": "proof_card", "arguments": {"record": {"status": "PASS"}, "extra_allow": ["demo"]}},
            )
            mocked.assert_called_once_with({"status": "PASS"}, extra_allow=["demo"])
            self.assertEqual(_tool_payload(response)["status"], "MOCK")


class McpBoundaryTests(unittest.TestCase):
    def test_refuses_raw_transcript_through_mcp(self):
        response = _rpc(
            "tools/call",
            params={"name": "context_pack", "arguments": {"state": {"objective": "x", "transcript": "raw chat"}}},
        )
        self.assertTrue(response["result"]["isError"])
        self.assertIn("raw conversational context", _tool_payload(response)["error"])

    def test_proof_card_allowlist_only_through_mcp(self):
        response = _rpc(
            "tools/call",
            params={
                "name": "proof_card",
                "arguments": {
                    "record": {
                        "status": "PASS",
                        "private_recipe": {"weights": [1]},
                        "prompt": "secret",
                        "database_table": "internal_rows",
                    }
                },
            },
        )
        payload = _tool_payload(response)
        self.assertEqual(payload["status"], "PASS")
        self.assertNotIn("private_recipe", payload)
        self.assertNotIn("prompt", payload)
        self.assertNotIn("database_table", payload)

    def test_no_private_imports_or_refs_in_packaging_surface(self):
        paths = [
            ROOT / "src/neuruh_sovereign_agent_starter/mcp_server.py",
            ROOT / "src/neuruh_sovereign_agent_starter/plugin_demo.py",
            ROOT / "plugin.json",
            ROOT / "mcp.json",
            *sorted((ROOT / "skills").rglob("SKILL.md")),
            *sorted((ROOT / "schemas").glob("*.json")),
        ]
        for path in paths:
            text = path.read_text(encoding="utf-8").lower()
            for token in FORBIDDEN_TOKENS:
                if path.name.endswith("SKILL.md") and token in {"axon", "mother", "iar", "deedsonar"}:
                    self.assertIn("not", text)
                    continue
                self.assertNotIn(token, text, f"{path} contains {token}")
            self.assertNotIn("import axon", text)
            self.assertNotIn("import mother", text)

    def test_mcp_server_source_does_not_reimplement_primitives(self):
        source = (ROOT / "src/neuruh_sovereign_agent_starter/mcp_server.py").read_text(encoding="utf-8")
        self.assertIn("from .micro_plugins import", source)
        self.assertIn("compile_context_packet", source)
        self.assertIn("choose_cheapest_capable_route", source)
        self.assertIn("public_proof_card", source)
        self.assertNotIn("_FORBIDDEN_CONTEXT_KEYS", source)
        self.assertNotIn("_PUBLIC_PROOF_FIELDS", source)
        self.assertNotIn("founder_minutes *", source)

    def test_no_network_required_at_runtime(self):
        class Guard(socket.socket):
            def __init__(self, *args, **kwargs):
                raise AssertionError("network socket opened")

        with patch("socket.socket", Guard):
            packed = _rpc("tools/call", params={"name": "context_pack", "arguments": {"state": {"mission_id": "N", "objective": "offline"}}})
            self.assertEqual(_tool_payload(packed)["mission_id"], "N")


class PluginManifestTests(unittest.TestCase):
    def test_plugin_and_mcp_json_match_agent_plugin_schema_shape(self):
        plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        mcp = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["$schema"], "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json")
        self.assertEqual(plugin["name"], "neuruh-public-micro-plugins")
        self.assertEqual(
            plugin["description"],
            "public-safe context pack, cheapest-capable route, and proof card. no private neuruh runtime.",
        )
        extra_plugin = set(plugin) - {
            "$schema",
            "name",
            "version",
            "description",
            "author",
            "homepage",
            "repository",
            "license",
            "keywords",
            "extensions",
        }
        self.assertEqual(extra_plugin, set())
        self.assertEqual(mcp["$schema"], "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json")
        self.assertEqual(set(mcp), {"$schema", "mcpServers"})
        server = mcp["mcpServers"]["neuruh-public-micro-plugins"]
        self.assertEqual(server["type"], "stdio")
        self.assertEqual(server["cwd"], "${PLUGIN_ROOT}")
        self.assertEqual(server["command"], "python3")
        self.assertNotIn(".cursor-plugin", (ROOT / "plugin.json").read_text(encoding="utf-8"))

        try:
            import jsonschema
        except ImportError:
            return
        plugin_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["$schema", "name"],
            "additionalProperties": False,
            "properties": {
                "$schema": {"const": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"},
                "name": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 64,
                    "pattern": "^(?!.*(?:--|\\.\\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$",
                },
                "version": {"type": "string"},
                "description": {"type": "string"},
                "author": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"name": {"type": "string"}, "email": {"type": "string"}, "url": {"type": "string"}},
                },
                "homepage": {"type": "string"},
                "repository": {"type": "string"},
                "license": {"type": "string"},
                "keywords": {"type": "array", "items": {"type": "string"}},
                "extensions": {"type": "object", "additionalProperties": {"type": "object"}},
            },
        }
        mcp_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["$schema", "mcpServers"],
            "additionalProperties": False,
            "properties": {
                "$schema": {"const": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"},
                "mcpServers": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "required": ["type", "command"],
                        "additionalProperties": False,
                        "properties": {
                            "type": {"const": "stdio"},
                            "command": {"type": "string", "minLength": 1},
                            "args": {"type": "array", "items": {"type": "string"}},
                            "env": {"type": "object", "additionalProperties": {"type": "string"}},
                            "cwd": {
                                "type": "string",
                                "pattern": r"^(?:\./|\$\{PLUGIN_ROOT\}(?:/|$)|\$\{PLUGIN_DATA\}(?:/|$))",
                            },
                        },
                    },
                },
            },
        }
        jsonschema.validate(plugin, plugin_schema)
        jsonschema.validate(mcp, mcp_schema)

    def test_skills_exist_and_point_at_mcp_tools(self):
        mapping = {
            "neuruh-context-pack": "context_pack",
            "neuruh-cheap-route": "cheap_route",
            "neuruh-proof-card": "proof_card",
        }
        for name, tool in mapping.items():
            text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(f"name: {name}", text)
            self.assertIn("Use when", text)
            self.assertIn(tool, text)
            self.assertIn("Never invent", text)


class FixtureRoundtripTests(unittest.TestCase):
    def test_demo_module_uses_existing_functions_on_fixtures(self):
        from neuruh_sovereign_agent_starter.plugin_demo import main

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            self.assertEqual(main(), 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["context_pack"]["mission_id"], "PACK-001")
        self.assertEqual(data["cheap_route"]["candidate_id"], "deterministic-l0")
        self.assertEqual(data["proof_card"]["status"], "PASS")
        self.assertNotIn("private_recipe", data["proof_card"])


if __name__ == "__main__":
    unittest.main()
