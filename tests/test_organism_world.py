import unittest

from neuruh_agent_receipt import ReceiptValidationError
from neuruh_sovereign_agent_starter.organism import contracts as C
from neuruh_sovereign_agent_starter.organism import learning as L
from neuruh_sovereign_agent_starter.organism.court import AGENT_ID, WORLD_ID, demo_seed
from neuruh_sovereign_agent_starter.organism.world import (
    NEVER_INHERITED, World, WorldError, instantiate, replay, world_seed_spec,
)

AT = "2026-08-24T00:00:01Z"


def seed_kwargs(**over):
    s = demo_seed()
    kw = {k: s[k] for k in ("seed_id", "seed_version", "world_type", "world_mode", "purpose", "policy", "capability_manifest",
                             "agent_roster", "grant_templates", "capability_budget", "memory_namespace", "evidence_namespace",
                             "fixtures", "initial_canonical_state", "tools_available", "action_class_map")}
    kw.update(over)
    return kw


def grant_for(world, subject=AGENT_ID, gid="g1"):
    return C.capability_grant(grant_id=gid, world_id=world.world_id, issuer="founder", subject=subject,
                              operations=["fixture.read", "sandbox.write"], forbidden_operations=["production.write"],
                              max_spend_usd=0, issued_at="2026-08-24T00:00:00Z", expires_at="2026-08-25T00:00:00Z",
                              evidence_class_ceiling="fixture", stage_ceiling="sandbox", created_at=AT)


class SeedTests(unittest.TestCase):
    def test_same_seed_same_fixture_same_initial_hash(self):
        a = instantiate(demo_seed(), world_id=WORLD_ID, created_at="2026-08-24T01:00:00Z", creator="x")
        b = instantiate(demo_seed(), world_id=WORLD_ID, created_at="2026-09-01T09:09:09Z", creator="y")
        self.assertEqual(demo_seed()["digest"], demo_seed()["digest"])
        self.assertEqual(a.manifest["initial_state_digest"], b.manifest["initial_state_digest"])
        self.assertEqual(a.lifecycle_anchor_digest, b.lifecycle_anchor_digest)
        self.assertNotEqual(a.manifest["digest"], b.manifest["digest"])  # created_at differs, state hash does not

    def test_different_fixture_different_initial_hash(self):
        s2 = world_seed_spec(**seed_kwargs(fixtures={**demo_seed()["fixtures"], "seed_input": "OTHER\n"}))
        a = instantiate(demo_seed(), world_id=WORLD_ID, created_at=AT, creator="x")
        b = instantiate(s2, world_id=WORLD_ID, created_at=AT, creator="x")
        self.assertNotEqual(a.manifest["initial_state_digest"], b.manifest["initial_state_digest"])

    def test_seed_refusals(self):
        with self.assertRaises(WorldError):
            world_seed_spec(**seed_kwargs(fixtures={"seed_input": "x"}))          # no clock_start
        with self.assertRaises(WorldError):
            world_seed_spec(**seed_kwargs(connectors=[{"id": "twilio"}]))         # synthetic + connectors
        with self.assertRaises(WorldError):
            world_seed_spec(**seed_kwargs(action_class_map={"sandbox.write": "launch_missiles"}))
        with self.assertRaises(C.ContractError):
            world_seed_spec(**seed_kwargs(world_mode="production"))


class WorldTests(unittest.TestCase):
    def setUp(self):
        self.w = instantiate(demo_seed(), world_id=WORLD_ID, created_at=AT, creator="t")

    def test_record_fails_closed(self):
        with self.assertRaises(WorldError):
            self.w.record("made_up_event", {}, observed_at=AT, run_id="r", causation_id="c")
        with self.assertRaises(WorldError):
            self.w.record("source_observed", {"chain_of_thought": "..."}, observed_at=AT, run_id="r", causation_id="c")
        with self.assertRaises(WorldError):
            self.w.record("source_observed", {}, observed_at=AT, run_id="", causation_id="c")

    def test_grant_requires_registered_agent_and_same_world(self):
        with self.assertRaises(WorldError):
            self.w.grant(grant_for(self.w), at=AT)
        self.w.register_agent(AGENT_ID, ["demo"], at=AT, creator="t")
        other = instantiate(demo_seed(), world_id="world-other", created_at=AT, creator="t")
        with self.assertRaises(WorldError):
            self.w.grant(grant_for(other), at=AT)
        g = self.w.grant(grant_for(self.w), at=AT)
        self.assertEqual(self.w.grants["g1"]["digest"], g["digest"])

    def test_snapshot_and_replay_reconstruct_state(self):
        self.w.register_agent(AGENT_ID, ["demo"], at=AT, creator="t")
        self.w.grant(grant_for(self.w), at=AT)
        snap = self.w.snapshot(taken_at="2026-08-24T00:00:05Z", run_id=self.w.run_id(AGENT_ID, 1))
        replayed, gaps = replay(demo_seed(), self.w.receipts[: snap["receipt_count"]])
        self.assertEqual(gaps, [])
        self.assertEqual(replayed.state_digest(), snap["state_digest"])
        self.assertEqual(replayed.receipts_tip, snap["receipts_tip"])
        self.assertEqual(set(replayed.grants), {"g1"})

    def test_replay_refuses_tampered_chain(self):
        self.w.register_agent(AGENT_ID, ["demo"], at=AT, creator="t")
        tampered = [dict(r) for r in self.w.receipts]
        tampered[1]["payload"] = {**tampered[1]["payload"], "identity": {**tampered[1]["payload"]["identity"], "roles": ["root"]}}
        with self.assertRaises(ReceiptValidationError):
            replay(demo_seed(), tampered)

    def test_replay_refuses_wrong_seed(self):
        s2 = world_seed_spec(**seed_kwargs(fixtures={**demo_seed()["fixtures"], "seed_input": "OTHER\n"}))
        with self.assertRaises(WorldError):
            replay(s2, self.w.receipts)


class ForkTests(unittest.TestCase):
    def setUp(self):
        self.p = instantiate(demo_seed(), world_id=WORLD_ID, created_at=AT, creator="t")
        self.p.register_agent(AGENT_ID, ["demo"], at=AT, creator="t")
        self.pg = self.p.grant(grant_for(self.p), at=AT)

    def test_fork_never_inherits_credentials_or_production(self):
        for item in NEVER_INHERITED:
            with self.assertRaises(WorldError):
                self.p.fork(child_world_id="c", created_at=AT, creator="t", purpose="x", inherit=[item], run_id="r1")
        with self.assertRaises(WorldError):
            self.p.fork(child_world_id="c", created_at=AT, creator="t", purpose="x", inherit=["secrets"], run_id="r1")

    def test_fork_inherits_only_what_is_declared_and_keeps_lineage(self):
        child, branch = self.p.fork(child_world_id="world-demo-001-b", created_at="2026-08-24T00:01:00Z", creator="t",
                                    purpose="branch", inherit=["canonical_state"], run_id="r1")
        self.assertEqual(child.manifest["parent_world_id"], WORLD_ID)
        self.assertEqual(child.manifest["lineage"], [WORLD_ID])
        self.assertEqual(child.canonical["state_digest"], self.p.canonical["state_digest"])
        self.assertEqual(child.grants, {})                       # authority never flows across worlds
        self.assertEqual(child.agents, {})
        self.assertIn("world-demo-001-b", self.p.children)
        self.assertEqual(branch["never_inherited"], list(NEVER_INHERITED))
        self.assertNotEqual(child.manifest["initial_state_digest"], self.p.manifest["initial_state_digest"])
        self.assertNotEqual(child.canonical["target_id"], self.p.canonical["target_id"])

    def test_child_grant_is_a_subset_of_parent_grant(self):
        child, _ = self.p.fork(child_world_id="world-demo-001-c", created_at=AT, creator="t", purpose="b", inherit=[], run_id="r1")
        child.register_agent("child-agent", ["demo"], at=AT, creator="t")
        cg = self.p.derive_child_grant(self.pg, child, grant_id="g-child", subject="child-agent", created_at=AT)
        self.assertEqual(cg["operations"], self.pg["operations"])
        self.assertEqual(cg["forbidden_operations"], self.pg["forbidden_operations"])
        self.assertEqual(cg["derived_from_grant"], self.pg["digest"])
        self.assertEqual(cg["hard_floors"], C.DEFAULT_HARD_FLOORS)
        child.grant(cg, at=AT)

    def test_child_world_cannot_mutate_parent_directly(self):
        child, _ = self.p.fork(child_world_id="world-demo-001-d", created_at=AT, creator="t", purpose="b", inherit=[], run_id="r1")
        fake019 = {"schema_version": C.ESTABLISHED["learning_update_proposal"], "proposal_id": "p1", "target_kind": "policy",
                   "target_id": "t", "proposal_digest": "sha256:" + "0" * 64, "sample_count": 30, "current_version": "v1",
                   "candidate_version": "v2", "calibration_summary_digest": "sha256:" + "1" * 64}
        child_lp = C.learning_proposal(world_id=child.world_id, run_id="r", world_mode=child.world_mode, proposal=fake019,
                                       provenance_={}, calibration_digest="sha256:" + "2" * 64, created_at=AT)
        with self.assertRaises(L.LearningError):
            L.revision_proposal(self.p, run_id="r", learning_proposal=child_lp, observed_state={"v": 2}, at=AT)
        self.assertEqual(self.p.revisions, [])


if __name__ == "__main__":
    unittest.main()
