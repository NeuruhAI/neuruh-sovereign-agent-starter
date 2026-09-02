import inspect
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from neuruh_sovereign_agent_starter import micro_plugins
from neuruh_sovereign_agent_starter.micro_plugins import (
    HANDOFF_PACK_SCHEMA_VERSION,
    cheap_route_main,
    choose_cheapest_capable_route,
    compile_context_packet,
    compile_handoff_pack,
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


class HandoffPackTests(unittest.TestCase):
    def test_envelope_contains_context_spine(self):
        pack = compile_handoff_pack({
            "mission_id": "HAND-001",
            "objective": "continue the public run",
            "next_action": "court preview",
            "canonical_refs": ["sha:abc"],
        })
        self.assertEqual(pack["schema_version"], HANDOFF_PACK_SCHEMA_VERSION)
        self.assertEqual(pack["schema_version"], "neuruh.handoff-pack.v0.1")
        self.assertEqual(pack["context"]["mission_id"], "HAND-001")
        self.assertEqual(pack["context"]["objective"], "continue the public run")
        self.assertEqual(pack["context"]["next_action"], "court preview")
        self.assertNotIn("from_run", pack)
        self.assertNotIn("to_run", pack)
        self.assertNotIn("produced_at", pack)
        self.assertNotIn("delta", pack)
        self.assertNotIn("last_proof", pack)
        self.assertNotIn("mission_id", pack)
        self.assertNotIn("objective", pack)
        self.assertNotIn("next_action", pack)

    def test_unknown_and_private_keys_are_refused(self):
        pack = compile_handoff_pack({
            "mission_id": "HAND-001",
            "objective": "continue",
            "giant_payload": "x" * 200,
            "secret_internal": {"foo": 1},
        })
        encoded = json.dumps(pack, sort_keys=True)
        self.assertNotIn("giant_payload", pack)
        self.assertNotIn("secret_internal", pack)
        self.assertNotIn("giant_payload", pack["context"])
        self.assertNotIn("secret_internal", encoded)

        with self.assertRaises(ValueError) as ctx:
            compile_handoff_pack({
                "mission_id": "HAND-001",
                "objective": "continue",
                "recipe": {"weights": [1, 2]},
                "customer_data": {"email": "hidden@example.com"},
            })
        message = str(ctx.exception)
        self.assertIn("recipe", message)
        self.assertIn("weights", message)
        self.assertIn("customer_data", message)

    def test_refuses_raw_transcript(self):
        with self.assertRaises(ValueError):
            compile_handoff_pack({"objective": "x", "transcript": "raw chat"})

    def test_optional_delta_only_when_before_and_after_supplied(self):
        before = {
            "mission_id": "HAND-001",
            "status": "blocked",
            "blocker": "missing receipt",
        }
        after = {
            "mission_id": "HAND-001",
            "status": "ready",
            "next_action": "court preview",
        }
        pack = compile_handoff_pack(
            {"mission_id": "HAND-001", "objective": "continue"},
            before=before,
            after=after,
        )
        self.assertEqual(pack["delta"], diff_public_state(before, after))
        self.assertFalse(pack["delta"]["unchanged"])

        bare = compile_handoff_pack({"mission_id": "HAND-001", "objective": "continue"})
        self.assertNotIn("delta", bare)

        with self.assertRaises(ValueError):
            compile_handoff_pack(
                {"mission_id": "HAND-001", "objective": "continue"},
                before=before,
            )

    def test_optional_last_proof_matches_public_proof_card(self):
        receipt = {
            "mission_id": "HAND-001",
            "status": "PASS",
            "commit_sha": "abc123",
            "tests": {"passed": 9},
            "private_recipe": {"weights": [1, 2, 3]},
            "prompt": "secret factory",
            "database_table": "internal_rows",
        }
        pack = compile_handoff_pack(
            {"mission_id": "HAND-001", "objective": "continue"},
            last_receipt=receipt,
        )
        self.assertEqual(pack["last_proof"], public_proof_card(receipt))
        self.assertEqual(pack["last_proof"]["status"], "PASS")
        self.assertNotIn("private_recipe", pack["last_proof"])
        self.assertNotIn("prompt", pack["last_proof"])
        self.assertNotIn("database_table", pack["last_proof"])
        self.assertNotIn("delta", pack)

    def test_refuses_oversized_bundle(self):
        with self.assertRaises(ValueError) as ctx:
            compile_handoff_pack({
                "mission_id": "HAND-001",
                "objective": "x" * 200,
            }, max_bytes=256)
        self.assertIn("max_bytes", str(ctx.exception))

    def test_composition_identity_calls_existing_functions(self):
        state = {"mission_id": "HAND-001", "objective": "continue"}
        before = {"status": "blocked"}
        after = {"status": "ready"}
        receipt = {"status": "PASS", "prompt": "secret factory"}
        with (
            patch.object(micro_plugins, "compile_context_packet", wraps=compile_context_packet) as ctx,
            patch.object(micro_plugins, "diff_public_state", wraps=diff_public_state) as diff,
            patch.object(micro_plugins, "public_proof_card", wraps=public_proof_card) as proof,
        ):
            pack = compile_handoff_pack(
                state,
                before=before,
                after=after,
                last_receipt=receipt,
                from_run="run-a",
                to_run="run-b",
            )
        ctx.assert_called_once()
        self.assertEqual(ctx.call_args.args[0], state)
        diff.assert_called_once()
        self.assertEqual(diff.call_args.args[0], before)
        self.assertEqual(diff.call_args.args[1], after)
        proof.assert_called_once_with(receipt)
        self.assertEqual(pack["context"], compile_context_packet(state))
        self.assertEqual(pack["delta"], diff_public_state(before, after))
        self.assertEqual(pack["last_proof"], public_proof_card(receipt))
        self.assertEqual(pack["from_run"], "run-a")
        self.assertEqual(pack["to_run"], "run-b")

        source = inspect.getsource(compile_handoff_pack)
        self.assertIn("compile_context_packet(", source)
        self.assertIn("diff_public_state(", source)
        self.assertIn("public_proof_card(", source)
        self.assertNotIn("_diff_nodes(", source)
        self.assertNotIn("_PUBLIC_PROOF_FIELDS", source)
        self.assertNotIn("_CONTEXT_FIELDS", source)

        with patch.object(micro_plugins, "diff_public_state", wraps=diff_public_state) as unused_diff:
            compile_handoff_pack(state)
        unused_diff.assert_not_called()

        with patch.object(micro_plugins, "public_proof_card", wraps=public_proof_card) as unused_proof:
            compile_handoff_pack(state)
        unused_proof.assert_not_called()

    def test_rejects_non_json_and_non_objects(self):
        with self.assertRaises(TypeError):
            compile_handoff_pack("not-an-object")
        with self.assertRaises(TypeError):
            compile_handoff_pack(["array"])

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
            handle.write("not-json")
            path = handle.name
        with self.assertRaises(json.JSONDecodeError):
            handoff_pack_main([path])

    def test_copies_optional_envelope_fields_without_inventing_them(self):
        pack = compile_handoff_pack({
            "mission_id": "HAND-001",
            "objective": "continue",
            "produced_at": "2026-09-01T00:00:00+00:00",
            "produced_refs": ["sha:abc"],
            "limitations": ["caller-supplied only"],
        })
        self.assertEqual(pack["produced_at"], "2026-09-01T00:00:00+00:00")
        self.assertEqual(pack["produced_refs"], ["sha:abc"])
        self.assertEqual(pack["limitations"], ["caller-supplied only"])
        self.assertNotIn("costs", pack)
        self.assertNotIn("proof", pack)


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
                    str(ROOT / "examples/mission-packet.synthetic.json"),
                    "--receipt",
                    str(ROOT / "examples/internal-receipt.synthetic.json"),
                    "--from-run",
                    "run-public-a",
                    "--to-run",
                    "run-public-b",
                ]),
                0,
            )
        pack = json.loads(buf.getvalue())
        self.assertEqual(pack["schema_version"], "neuruh.handoff-pack.v0.1")
        self.assertEqual(pack["context"]["mission_id"], "PACK-001")
        self.assertEqual(pack["from_run"], "run-public-a")
        self.assertEqual(pack["to_run"], "run-public-b")
        self.assertEqual(pack["last_proof"]["status"], "PASS")
        self.assertNotIn("private_recipe", pack["last_proof"])
        self.assertNotIn("delta", pack)


if __name__ == "__main__":
    unittest.main()
