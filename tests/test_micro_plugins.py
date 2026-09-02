import inspect
import io
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from neuruh_sovereign_agent_starter import micro_plugins
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
)

ROOT = Path(__file__).resolve().parents[1]


class ContextPackTests(unittest.TestCase):
    def test_keeps_execution_spine_and_drops_unknown_payload(self):
        packet = compile_context_packet({
            "mission_id": "SHIP-001",
            "objective": "ship the offer",
            "canonical_refs": ["sha:abc"],
            "next_action": "court preview",
            "giant_payload": "x" * 10000,
        })
        self.assertEqual(packet["mission_id"], "SHIP-001")
        self.assertNotIn("giant_payload", packet)
        self.assertLessEqual(len(json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()), 4096)

    def test_refuses_raw_transcript(self):
        with self.assertRaises(ValueError):
            compile_context_packet({"objective": "x", "transcript": "raw chat"})

    def test_trims_pointer_lists_to_budget(self):
        packet = compile_context_packet({
            "mission_id": "M1",
            "objective": "bounded",
            "canonical_refs": [f"artifact:{i}:" + "x" * 100 for i in range(100)],
            "next_action": "continue",
        }, max_bytes=700)
        self.assertLessEqual(len(json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()), 700)
        self.assertEqual(packet["next_action"], "continue")

    def test_parent_mission_id_survives_context_pack(self):
        packet = compile_context_packet({
            "mission_id": "HAND-002",
            "parent_mission_id": "HAND-001",
            "objective": "continue",
        })
        self.assertEqual(packet["parent_mission_id"], "HAND-001")
        self.assertEqual(packet["mission_id"], "HAND-002")


class CheapRouteTests(unittest.TestCase):
    def test_deterministic_route_beats_equivalent_frontier_route(self):
        choice = choose_cheapest_capable_route([
            {
                "candidate_id": "deterministic",
                "layer": "L0",
                "success_probability": 0.95,
                "expected_value_usd": 100,
                "execution_cost_usd": 0.01,
                "model_cost_usd": 0,
                "founder_minutes": 0,
                "latency_minutes": 0.1,
            },
            {
                "candidate_id": "frontier",
                "layer": "L4",
                "success_probability": 0.95,
                "expected_value_usd": 100,
                "execution_cost_usd": 0.01,
                "model_cost_usd": 1.5,
                "founder_minutes": 0,
                "latency_minutes": 1,
            },
        ])
        self.assertEqual(choice.candidate_id, "deterministic")
        self.assertEqual(choice.layer, "L0")

    def test_rejects_below_capability_floor(self):
        with self.assertRaises(ValueError):
            choose_cheapest_capable_route([
                {"candidate_id": "cheap-but-bad", "layer": "L0", "success_probability": 0.5}
            ], minimum_success_probability=0.8)

    def test_high_value_capable_route_can_justify_more_cost(self):
        choice = choose_cheapest_capable_route([
            {
                "candidate_id": "cheap-low-value",
                "layer": "L0",
                "success_probability": 0.9,
                "expected_value_usd": 10,
                "execution_cost_usd": 0,
            },
            {
                "candidate_id": "costly-high-value",
                "layer": "L3",
                "success_probability": 0.9,
                "expected_value_usd": 1000,
                "model_cost_usd": 2,
            },
        ])
        self.assertEqual(choice.candidate_id, "costly-high-value")


class PublicProofTests(unittest.TestCase):
    def test_allowlist_hides_private_fields(self):
        card = public_proof_card({
            "mission_id": "M1",
            "status": "PASS",
            "commit_sha": "abc123",
            "tests": {"passed": 9},
            "private_recipe": {"weights": [1, 2, 3]},
            "prompt": "secret factory",
            "database_table": "internal_rows",
        })
        self.assertEqual(card["status"], "PASS")
        self.assertNotIn("private_recipe", card)
        self.assertNotIn("prompt", card)
        self.assertNotIn("database_table", card)

    def test_explicit_extra_allow_is_required_for_extra_field(self):
        record = {"status": "PASS", "demo": "public fixture"}
        self.assertNotIn("demo", public_proof_card(record))
        self.assertEqual(public_proof_card(record, extra_allow=["demo"])["demo"], "public fixture")


class StateDiffTests(unittest.TestCase):
    def test_reports_added_removed_and_changed_paths(self):
        delta = diff_public_state(
            {
                "mission_id": "SHIP-001",
                "status": "blocked",
                "blocker": "missing receipt",
                "counts": {"done": 1},
            },
            {
                "mission_id": "SHIP-001",
                "status": "ready",
                "counts": {"done": 2},
                "next_action": "court preview",
            },
        )
        self.assertFalse(delta["unchanged"])
        self.assertEqual(delta["added"], [{"path": "next_action", "value": "court preview"}])
        self.assertEqual(delta["removed"], [{"path": "blocker", "value": "missing receipt"}])
        self.assertEqual(
            delta["changed"],
            [
                {"path": "counts.done", "before": 1, "after": 2},
                {"path": "status", "before": "blocked", "after": "ready"},
            ],
        )

    def test_identical_objects_are_unchanged(self):
        state = {"mission_id": "M1", "status": "ready"}
        delta = diff_public_state(state, {"mission_id": "M1", "status": "ready"})
        self.assertTrue(delta["unchanged"])
        self.assertEqual(delta["added"], [])
        self.assertEqual(delta["removed"], [])
        self.assertEqual(delta["changed"], [])

    def test_refuses_private_and_conversational_fields(self):
        with self.assertRaises(ValueError) as ctx:
            diff_public_state(
                {"status": "ready", "recipe": {"weights": [1, 2]}},
                {"status": "ready", "prompt": "secret factory"},
            )
        message = str(ctx.exception)
        self.assertIn("recipe", message)
        self.assertIn("prompt", message)
        self.assertIn("weights", message)

    def test_list_index_paths_are_deterministic(self):
        first = diff_public_state(
            {"items": [{"id": "a"}, {"id": "b"}]},
            {"items": [{"id": "a"}, {"id": "c"}, {"id": "d"}]},
        )
        second = diff_public_state(
            {"items": [{"id": "a"}, {"id": "b"}]},
            {"items": [{"id": "a"}, {"id": "c"}, {"id": "d"}]},
        )
        self.assertEqual(first, second)
        self.assertEqual(
            first["changed"],
            [{"path": "items.1.id", "before": "b", "after": "c"}],
        )
        self.assertEqual(first["added"], [{"path": "items.2", "value": {"id": "d"}}])

    def test_refuses_oversized_delta(self):
        with self.assertRaises(ValueError):
            diff_public_state(
                {"payload": "a" * 200},
                {"payload": "b" * 200},
                max_bytes=256,
            )


def _path_list(delta):
    paths = []
    for kind in ("added", "changed", "removed"):
        paths.extend(f"{kind}:{item['path']}" for item in delta[kind])
    return paths


class HandoffPackTests(unittest.TestCase):
    def test_parent_mission_id_and_spine_come_from_inputs(self):
        packet = compile_handoff_packet(
            {
                "mission_id": "HAND-001",
                "objective": "prior",
                "current_state": {"status": "blocked", "blocker": "missing receipt"},
            },
            {
                "mission_id": "HAND-002",
                "objective": "continue the public run",
                "current_state": {"status": "ready"},
                "canonical_refs": ["sha:abc"],
                "next_action": "court preview",
                "giant_payload": "x" * 200,
            },
        )
        self.assertEqual(packet["parent_mission_id"], "HAND-001")
        self.assertEqual(packet["mission_id"], "HAND-002")
        self.assertEqual(packet["objective"], "continue the public run")
        self.assertEqual(packet["next_action"], "court preview")
        self.assertEqual(packet["canonical_refs"], ["sha:abc"])
        self.assertNotIn("giant_payload", packet)
        self.assertNotIn("schema_version", packet)
        self.assertNotIn("delta", packet)
        self.assertNotIn("last_proof", packet)

    def test_parent_mission_id_falls_back_to_mission(self):
        packet = compile_handoff_packet(
            {"mission": "OLD-MISSION", "current_state": {"status": "ready"}},
            {"mission_id": "HAND-002", "objective": "continue", "current_state": {"status": "ready"}},
        )
        self.assertEqual(packet["parent_mission_id"], "OLD-MISSION")
        self.assertNotIn("changed_since_last_run", packet)

    def test_requires_parent_mission_id(self):
        with self.assertRaises(ValueError) as ctx:
            compile_handoff_packet(
                {"objective": "prior"},
                {"mission_id": "HAND-002", "objective": "continue"},
            )
        self.assertIn("parent_mission_id", str(ctx.exception))

    def test_changed_since_last_run_is_derived_not_trusted(self):
        previous = {
            "mission_id": "HAND-001",
            "current_state": {"status": "blocked", "blocker": "missing receipt", "counts": {"done": 1}},
        }
        current = {
            "mission_id": "HAND-002",
            "objective": "continue",
            "current_state": {"status": "ready", "counts": {"done": 2}},
            "changed_since_last_run": ["this-is-a-lie"],
            "next_action": "court preview",
        }
        packet = compile_handoff_packet(previous, current)
        expected = _path_list(diff_public_state(previous["current_state"], current["current_state"]))
        self.assertEqual(packet["changed_since_last_run"], expected)
        self.assertNotIn("this-is-a-lie", packet["changed_since_last_run"])
        self.assertTrue(all(item.startswith(("added:", "changed:", "removed:")) for item in packet["changed_since_last_run"]))
        self.assertFalse(any("missing receipt" in item for item in packet["changed_since_last_run"]))

    def test_refuses_raw_transcript(self):
        with self.assertRaises(ValueError) as ctx:
            compile_handoff_packet(
                {"mission_id": "HAND-001", "transcript": "raw chat"},
                {"mission_id": "HAND-002", "objective": "continue"},
            )
        self.assertIn("transcript", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            compile_handoff_packet(
                {"mission_id": "HAND-001"},
                {"mission_id": "HAND-002", "prompt_history": ["secret"]},
            )
        self.assertIn("prompt_history", str(ctx.exception))

    def test_refuses_nested_private_refs(self):
        with self.assertRaises(ValueError) as ctx:
            compile_handoff_packet(
                {"mission_id": "HAND-001", "current_state": {"status": "ready"}},
                {
                    "mission_id": "HAND-002",
                    "objective": "continue",
                    "current_state": {
                        "status": "ready",
                        "private_url": "https://internal.example",
                        "recipe": {"weights": [1, 2]},
                    },
                },
            )
        message = str(ctx.exception)
        self.assertIn("private_url", message)
        self.assertIn("recipe", message)
        self.assertIn("weights", message)

    def test_refuses_oversized_delta_with_refs_not_blobs(self):
        with self.assertRaises(ValueError) as ctx:
            compile_handoff_packet(
                {"mission_id": "HAND-001", "current_state": {"payload": "a" * 200}},
                {"mission_id": "HAND-002", "objective": "continue", "current_state": {"payload": "b" * 200}},
                max_bytes=256,
            )
        self.assertIn("max_bytes", str(ctx.exception))
        self.assertIn("refs", str(ctx.exception))

    def test_composition_uses_real_diff_and_pack_functions(self):
        previous = {"mission_id": "HAND-001", "current_state": {"status": "blocked"}}
        current = {
            "mission_id": "HAND-002",
            "objective": "continue",
            "current_state": {"status": "ready"},
            "changed_since_last_run": ["ignore-me"],
        }
        self.assertIs(compile_handoff_packet.__globals__["diff_public_state"], diff_public_state)
        self.assertIs(compile_handoff_packet.__globals__["compile_context_packet"], compile_context_packet)
        with (
            patch.object(micro_plugins, "diff_public_state", wraps=diff_public_state) as diff,
            patch.object(micro_plugins, "compile_context_packet", wraps=compile_context_packet) as packed,
        ):
            packet = compile_handoff_packet(previous, current)
        diff.assert_called_once()
        packed.assert_called_once()
        self.assertEqual(diff.call_args.args[0], previous["current_state"])
        self.assertEqual(diff.call_args.args[1], current["current_state"])
        composed = packed.call_args.args[0]
        self.assertEqual(composed["parent_mission_id"], "HAND-001")
        self.assertNotEqual(composed["changed_since_last_run"], ["ignore-me"])
        self.assertEqual(packet, compile_context_packet(composed))
        source = inspect.getsource(compile_handoff_packet)
        self.assertIn("diff_public_state(", source)
        self.assertIn("compile_context_packet(", source)
        self.assertNotIn("public_proof_card(", source)
        self.assertNotIn("_diff_nodes(", source)
        self.assertNotIn("trimmable", source)

    def test_deterministic_canonical_json(self):
        previous = {"mission_id": "HAND-001", "current_state": {"b": 1, "a": 0}}
        current = {"mission_id": "HAND-002", "objective": "continue", "current_state": {"a": 1, "b": 1}}
        first = compile_handoff_packet(previous, current)
        second = compile_handoff_packet(previous, current)
        self.assertEqual(first, second)
        self.assertEqual(
            json.dumps(first, sort_keys=True, separators=(",", ":")),
            json.dumps(second, sort_keys=True, separators=(",", ":")),
        )

    def test_no_network(self):
        class Guard(socket.socket):
            def __init__(self, *args, **kwargs):
                raise AssertionError("network socket opened")

        with patch("socket.socket", Guard):
            packet = compile_handoff_packet(
                {"mission_id": "HAND-001", "current_state": {"status": "ready"}},
                {"mission_id": "HAND-002", "objective": "offline", "current_state": {"status": "ready"}},
            )
        self.assertEqual(packet["parent_mission_id"], "HAND-001")

    def test_rejects_non_json_and_non_objects(self):
        with self.assertRaises(TypeError):
            compile_handoff_packet("not-an-object", {"mission_id": "HAND-002"})
        with self.assertRaises(TypeError):
            compile_handoff_packet({"mission_id": "HAND-001"}, ["array"])

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as previous:
            previous.write('{"mission_id": "HAND-001"}')
            previous_path = previous.name
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as current:
            current.write("not-json")
            current_path = current.name
        err = io.StringIO()
        with patch("sys.stderr", err), patch("sys.stdout", io.StringIO()):
            self.assertEqual(handoff_pack_main([previous_path, current_path]), 1)
        message = err.getvalue()
        self.assertTrue(message.strip())
        self.assertEqual(message.count("\n"), 1)
        self.assertNotIn("Traceback", message)


class MicroPluginCliTests(unittest.TestCase):
    def test_cli_entry_points_still_read_synthetic_fixtures(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            self.assertEqual(context_pack_main([str(ROOT / "examples/mission-packet.synthetic.json")]), 0)
        self.assertEqual(json.loads(buf.getvalue())["mission_id"], "PACK-001")

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            self.assertEqual(cheap_route_main([str(ROOT / "examples/route-candidates.synthetic.json")]), 0)
        self.assertEqual(json.loads(buf.getvalue())["candidate_id"], "deterministic-l0")

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            self.assertEqual(proof_card_main([str(ROOT / "examples/internal-receipt.synthetic.json")]), 0)
        card = json.loads(buf.getvalue())
        self.assertEqual(card["status"], "PASS")
        self.assertNotIn("private_recipe", card)

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            self.assertEqual(
                handoff_pack_main([
                    str(ROOT / "examples/handoff-previous.synthetic.json"),
                    str(ROOT / "examples/handoff-current.synthetic.json"),
                ]),
                0,
            )
        pack = json.loads(buf.getvalue())
        self.assertEqual(pack["parent_mission_id"], "HAND-001")
        self.assertEqual(pack["mission_id"], "HAND-002")
        self.assertNotIn("this-is-a-lie", pack.get("changed_since_last_run", []))
        self.assertNotIn("giant_payload", pack)
        self.assertTrue(any(item.startswith(("added:", "changed:", "removed:")) for item in pack["changed_since_last_run"]))

    def test_cli_prints_one_stderr_line_on_transcript_refusal(self):
        err = io.StringIO()
        with patch("sys.stderr", err), patch("sys.stdout", io.StringIO()):
            rc = context_pack_main([str(ROOT / "examples/demos/bloated-mission.transcript-refuse.synthetic.json")])
        self.assertEqual(rc, 1)
        message = err.getvalue()
        self.assertIn("transcript", message)
        self.assertEqual(message.count("\n"), 1)
        self.assertNotIn("Traceback", message)
        self.assertNotIn("ValueError", message)


if __name__ == "__main__":
    unittest.main()
