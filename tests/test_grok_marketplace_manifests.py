import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class GrokMarketplaceManifestTests(unittest.TestCase):
    def test_grok_manifests_parse_and_mcp_servers_match(self):
        grok_plugin = json.loads((ROOT / ".grok-plugin/plugin.json").read_text(encoding="utf-8"))
        grok_mcp = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        cursor_plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        cursor_mcp = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))

        self.assertIsInstance(grok_plugin, dict)
        self.assertIsInstance(grok_mcp, dict)
        self.assertEqual(grok_plugin["name"], cursor_plugin["name"])
        self.assertEqual(grok_plugin["version"], cursor_plugin["version"])
        self.assertEqual(set(grok_mcp["mcpServers"]), set(cursor_mcp["mcpServers"]))
        self.assertEqual(
            grok_mcp["mcpServers"]["neuruh-public-micro-plugins"]["args"],
            ["-m", "neuruh_sovereign_agent_starter.mcp_server"],
        )


if __name__ == "__main__":
    unittest.main()
