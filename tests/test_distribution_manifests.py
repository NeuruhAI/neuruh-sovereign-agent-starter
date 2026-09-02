import json
import re
import tomllib
import unittest
from pathlib import Path

from neuruh_sovereign_agent_starter.mcp_server import SERVER_NAME, SERVER_VERSION

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "neuruh-public-micro-plugins"
PLUGIN_VERSION = "0.1.9-alpha"


class DistributionManifestTests(unittest.TestCase):
    def _json(self, path: str):
        return json.loads((ROOT / path).read_text(encoding="utf-8"))

    def test_identity_is_aligned_across_plugin_surfaces(self):
        agent = self._json("plugin.json")
        grok = self._json(".grok-plugin/plugin.json")
        claude = self._json(".claude-plugin/plugin.json")
        for manifest in (agent, grok, claude):
            self.assertEqual(manifest["name"], PLUGIN_NAME)
            self.assertEqual(manifest["version"], PLUGIN_VERSION)
            self.assertEqual(manifest["license"], "Apache-2.0")
        self.assertEqual(SERVER_NAME, PLUGIN_NAME)
        self.assertEqual(SERVER_VERSION, PLUGIN_VERSION)

    def test_python_version_maps_to_plugin_release_version(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)a0", project["version"])
        self.assertIsNotNone(match)
        self.assertEqual(f"{match.group(1)}.{match.group(2)}.{match.group(3)}-alpha", PLUGIN_VERSION)

    def test_mcp_config_keys_match(self):
        root = self._json("mcp.json")
        scanner = self._json(".mcp.json")
        self.assertEqual(set(root["mcpServers"]), {PLUGIN_NAME})
        self.assertEqual(set(scanner["mcpServers"]), {PLUGIN_NAME})
        self.assertEqual(root["mcpServers"][PLUGIN_NAME], scanner["mcpServers"][PLUGIN_NAME])

    def test_distribution_doc_refuses_duplicate_xai_submission(self):
        text = (ROOT / "DISTRIBUTION.md").read_text(encoding="utf-8")
        self.assertIn("xai-org/plugin-marketplace#503", text)
        self.assertIn("DO NOT DUPLICATE", text)
        self.assertIn("READY_FOR_FORM", text)
        self.assertIn("BLOCKED_ON_PACKAGE_PUBLICATION", text)


if __name__ == "__main__":
    unittest.main()
