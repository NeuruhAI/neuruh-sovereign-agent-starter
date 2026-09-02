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
        # An external web form is a blocker, not a readiness state: the repo cannot
        # complete it, so it must not be filed next to states this repo can reach.
        self.assertIn("BLOCKED_EXTERNAL_FORM", text)
        self.assertIn("BLOCKED_ON_PACKAGE_PUBLICATION", text)
        self.assertIn("BLOCKED_ON_PACKAGE_RESTRUCTURE", text)
        # Never let the doc claim the marketplace accepted the plugin.
        self.assertNotIn("ACCEPTED", text.upper().replace("NOT ACCEPTED", ""))



class ClaudeMarketplaceTests(unittest.TestCase):
    """A Claude Code user adds a marketplace, not a bare plugin manifest.

    Without .claude-plugin/marketplace.json the repository cannot be added with
    `/plugin marketplace add NeuruhAI/neuruh-sovereign-agent-starter`, so the
    Claude surface would be a manifest that no one can install.
    """

    def setUp(self):
        self.marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        self.plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))

    def test_marketplace_lists_this_repo_as_the_plugin_source(self):
        self.assertTrue(self.marketplace["name"])
        self.assertTrue(self.marketplace["owner"]["name"])
        entries = self.marketplace["plugins"]
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["source"], "./")
        self.assertEqual(entry["name"], self.plugin["name"])
        self.assertEqual(entry["license"], self.plugin["license"])
        self.assertEqual(entry["repository"], self.plugin["repository"])

    def test_marketplace_requests_no_credentials_and_stays_brand_scoped(self):
        entry = self.marketplace["plugins"][0]
        # The manifest must not *declare* a credential requirement. Saying
        # "no account or API key" in the description is the opposite: a promise
        # this plugin keeps, so match on requirement-shaped fields, not words.
        for field in ("env", "envVars", "credentials", "secrets", "config", "permissions", "auth"):
            self.assertNotIn(field, entry, f"marketplace entry must not declare {field}")
            self.assertNotIn(field, self.marketplace)
        self.assertIn("no account or api key", entry["description"].lower())
        for keyword in entry["keywords"]:
            self.assertIn("neuruh", keyword.lower(), "keywords must stay brand-scoped")


if __name__ == "__main__":
    unittest.main()
