import io
import json
import socket
import unittest
from pathlib import Path
from unittest.mock import patch

from neuruh_sovereign_agent_starter.mcp_server import SERVER_VERSION
from neuruh_sovereign_agent_starter.micro_plugins import (
    cheap_route_main,
    choose_cheapest_capable_route,
    compile_context_packet,
    compile_handoff_packet,
    context_pack_main,
    diff_public_state,
    handoff_pack_main,
    proof_card_main,
    public_proof_card,
    state_diff_main,
)

ROOT = Path(__file__).resolve().parents[1]
DEMOS = ROOT / "examples" / "demos"
UNKNOWN_BLOAT_KEYS = (
    "debug_dump",
    "operator_notes",
    "session_cache",
    "telemetry_junk",
    "scratchpad",
    "ignored_blob",
)
PRIVATE_PROOF_KEYS = (
    "private_recipe",
    "prompt",
    "transcript",
    "database_table",
    "axon_route",
    "mother_state",
)


class DemoFixturePresenceTests(unittest.TestCase):
    def test_required_demo_files_exist_and_stay_small(self):
        required = [
            "bloated-mission.synthetic.json",
            "bloated-mission.transcript-refuse.synthetic.json",
            "three-routes.synthetic.json",
            "docs-release-receipt.synthetic.json",
        ]
        for name in required:
            path = DEMOS / name
            self.assertTrue(path.is_file(), name)
        bloated = DEMOS / "bloated-mission.synthetic.json"
        self.assertGreater(bloated.stat().st_size, 512)
        for name in required:
            if name.startswith("bloated-mission.synthetic"):
                continue
            size = (DEMOS / name).stat().st_size
            self.assertLessEqual(size, 2048, f"{name} is {size} bytes")

    def test_legacy_two_candidate_fixture_is_unchanged_shape(self):
        candidates = json.loads((ROOT / "examples/route-candidates.synthetic.json").read_text(encoding="utf-8"))
        self.assertEqual(len(candidates), 2)
        self.assertEqual([c["candidate_id"] for c in candidates], ["deterministic-l0", "frontier-l4"])


class DemoAContextPackTests(unittest.TestCase):
    def test_bloated_input_packs_and_drops_unknown_keys(self):
        state = json.loads((DEMOS / "bloated-mission.synthetic.json").read_text(encoding="utf-8"))
        for key in UNKNOWN_BLOAT_KEYS:
            self.assertIn(key, state)
        self.assertNotIn("transcript", {k.lower() for k in state})
        self.assertNotIn("chat", {k.lower() for k in state})
        packet = compile_context_packet(state)
        encoded = json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()
        self.assertLessEqual(len(encoded), 4096)
        self.assertEqual(packet["mission_id"], "DEMO-A")
        for key in UNKNOWN_BLOAT_KEYS:
            self.assertNotIn(key, packet)

    def test_transcript_fixture_is_refused_by_library(self):
        state = json.loads((DEMOS / "bloated-mission.transcript-refuse.synthetic.json").read_text(encoding="utf-8"))
        with self.assertRaises(ValueError) as ctx:
            compile_context_packet(state)
        self.assertIn("transcript", str(ctx.exception))


class DemoBCheapRouteTests(unittest.TestCase):
    def test_three_route_fixture_selects_l0(self):
        candidates = json.loads((DEMOS / "three-routes.synthetic.json").read_text(encoding="utf-8"))
        self.assertEqual(len(candidates), 3)
        layers = {item["layer"] for item in candidates}
        self.assertEqual(layers, {"L0", "L2", "L4"})
        choice = choose_cheapest_capable_route(candidates, minimum_success_probability=0.8)
        self.assertEqual(choice.candidate_id, "deterministic-l0")
        self.assertEqual(choice.layer, "L0")


class DemoCProofCardTests(unittest.TestCase):
    def test_junk_receipt_omits_private_keys_including_transcript(self):
        record = json.loads((DEMOS / "internal-receipt-junk.synthetic.json").read_text(encoding="utf-8"))
        for key in PRIVATE_PROOF_KEYS:
            self.assertIn(key, record)
        card = public_proof_card(record)
        self.assertEqual(card["status"], "PASS")
        self.assertEqual(card["mission_id"], "DEMO-C")
        for key in PRIVATE_PROOF_KEYS:
            self.assertNotIn(key, card)


class DemoDStateAndHandoffTests(unittest.TestCase):
    def test_reuses_tagged_form_a_fixtures(self):
        previous = ROOT / "examples/handoff-previous.synthetic.json"
        current = ROOT / "examples/handoff-current.synthetic.json"
        self.assertTrue(previous.is_file())
        self.assertTrue(current.is_file())
        self.assertFalse((DEMOS / "state-before.synthetic.json").exists())
        self.assertFalse((DEMOS / "state-after.synthetic.json").exists())
        before = json.loads(previous.read_text(encoding="utf-8"))
        after = json.loads(current.read_text(encoding="utf-8"))
        delta = diff_public_state(before, after)
        self.assertFalse(delta["unchanged"])
        self.assertTrue(any(item["path"] == "current_state.status" for item in delta["changed"]))
        packet = compile_handoff_packet(before, after)
        self.assertEqual(packet["parent_mission_id"], "HAND-001")
        self.assertEqual(packet["mission_id"], "HAND-002")
        self.assertNotIn("giant_payload", packet)
        self.assertNotIn("this-is-a-lie", packet.get("changed_since_last_run", []))
        self.assertTrue(
            any(item.startswith(("added:", "changed:", "removed:")) for item in packet["changed_since_last_run"])
        )


class DemoCliShapeTests(unittest.TestCase):
    def test_three_demo_clis_match_public_shape(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            self.assertEqual(context_pack_main([str(DEMOS / "bloated-mission.synthetic.json")]), 0)
        packed = json.loads(buf.getvalue())
        self.assertEqual(packed["mission_id"], "DEMO-A")
        self.assertNotIn("ignored_blob", packed)

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            self.assertEqual(
                cheap_route_main([str(DEMOS / "three-routes.synthetic.json"), "--min-success", "0.8"]),
                0,
            )
        routed = json.loads(buf.getvalue())
        self.assertEqual(routed["candidate_id"], "deterministic-l0")
        self.assertEqual(routed["layer"], "L0")

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            self.assertEqual(proof_card_main([str(DEMOS / "internal-receipt-junk.synthetic.json")]), 0)
        card = json.loads(buf.getvalue())
        self.assertEqual(card["status"], "PASS")
        self.assertNotIn("private_recipe", card)
        self.assertNotIn("transcript", card)

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            self.assertEqual(
                state_diff_main([
                    str(ROOT / "examples/handoff-previous.synthetic.json"),
                    str(ROOT / "examples/handoff-current.synthetic.json"),
                ]),
                0,
            )
        self.assertFalse(json.loads(buf.getvalue())["unchanged"])

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            self.assertEqual(
                handoff_pack_main([
                    str(ROOT / "examples/handoff-previous.synthetic.json"),
                    str(ROOT / "examples/handoff-current.synthetic.json"),
                ]),
                0,
            )
        self.assertEqual(json.loads(buf.getvalue())["parent_mission_id"], "HAND-001")

    def test_no_network(self):
        class Guard(socket.socket):
            def __init__(self, *args, **kwargs):
                raise AssertionError("network socket opened")

        with patch("socket.socket", Guard):
            compile_context_packet(json.loads((DEMOS / "bloated-mission.synthetic.json").read_text(encoding="utf-8")))
            choose_cheapest_capable_route(
                json.loads((DEMOS / "three-routes.synthetic.json").read_text(encoding="utf-8")),
                minimum_success_probability=0.8,
            )
            public_proof_card(json.loads((DEMOS / "internal-receipt-junk.synthetic.json").read_text(encoding="utf-8")))


class PublicProofCardFileTests(unittest.TestCase):
    def test_committed_card_is_cli_projection_of_synthetic_record(self):
        source = json.loads((DEMOS / "docs-release-receipt.synthetic.json").read_text(encoding="utf-8"))
        expected = public_proof_card(source)
        committed = json.loads((ROOT / "PUBLIC_PROOF_CARD.v0.1.7-alpha.json").read_text(encoding="utf-8"))
        self.assertEqual(committed, expected)
        self.assertEqual(committed["version"], "0.1.7-alpha")
        limitations = " ".join(committed["limitations"]).lower()
        self.assertIn("packaging/docs", limitations)
        self.assertIn("not a production receipt", limitations)
        for key in ("private_recipe", "prompt", "transcript", "database_table", "private_url"):
            self.assertNotIn(key, committed)


class VersionSurfaceTests(unittest.TestCase):
    def test_plugin_and_mcp_server_versions_match_this_release(self):
        plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["version"], "0.1.9-alpha")
        self.assertEqual(SERVER_VERSION, "0.1.9-alpha")

    def test_handoff_skill_exists_and_state_diff_has_no_skill(self):
        self.assertTrue((ROOT / "skills/neuruh-handoff-pack/SKILL.md").is_file())
        self.assertFalse((ROOT / "skills/neuruh-state-diff").exists())
        listed = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(listed["mcpServers"]["neuruh-public-micro-plugins"]["env"]["PYTHONPATH"], "${PLUGIN_ROOT}/src")


if __name__ == "__main__":
    unittest.main()
