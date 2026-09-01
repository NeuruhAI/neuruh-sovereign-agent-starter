import json
import unittest

from neuruh_sovereign_agent_starter.micro_plugins import (
    choose_cheapest_capable_route,
    compile_context_packet,
    public_proof_card,
)


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


if __name__ == "__main__":
    unittest.main()
