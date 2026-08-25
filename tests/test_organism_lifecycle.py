import tempfile
import unittest
from pathlib import Path

from neuruh_agent_receipt import verify_ledger
from neuruh_sovereign_agent_starter.organism import authority as A
from neuruh_sovereign_agent_starter.organism import contracts as C
from neuruh_sovereign_agent_starter.organism import learning as L
from neuruh_sovereign_agent_starter.organism import lifecycle as LC
from neuruh_sovereign_agent_starter.organism.court import AGENT_ID, WORLD_ID, Clock, demo_seed
from neuruh_sovereign_agent_starter.organism.world import instantiate, world_seed_spec

AT0 = "2026-08-24T00:00:00Z"


def live_seed():
    s = demo_seed()
    kw = {k: s[k] for k in ("seed_id", "seed_version", "world_type", "purpose", "policy", "capability_manifest", "agent_roster",
                             "grant_templates", "capability_budget", "memory_namespace", "evidence_namespace", "fixtures",
                             "initial_canonical_state", "tools_available", "action_class_map")}
    return world_seed_spec(world_mode="live", **kw)


class Harness:
    """Builds a world + one executed governed turn in a temporary sandbox."""

    def __init__(self, seed=None):
        self.seed = seed or demo_seed()
        self.tmp = tempfile.TemporaryDirectory()
        self.sandbox = Path(self.tmp.name) / "sb"
        (self.sandbox / "fixtures").mkdir(parents=True)
        (self.sandbox / "outputs").mkdir()
        (self.sandbox / "fixtures" / "seed-input.txt").write_text("X\n")
        self.clock = Clock(AT0)
        self.w = instantiate(self.seed, world_id=WORLD_ID, created_at=self.clock.tick(), creator="t")
        self.w.register_agent(AGENT_ID, ["demo"], at=self.clock.tick(), creator="t")
        self.grant = C.capability_grant(grant_id="g", world_id=WORLD_ID, issuer="founder", subject=AGENT_ID,
                                        operations=["fixture.read", "sandbox.write"], forbidden_operations=["production.write"],
                                        max_spend_usd=0, issued_at=AT0, expires_at="2026-08-25T00:00:00Z",
                                        evidence_class_ceiling=self.w.evidence_class, stage_ceiling="sandbox", created_at=self.clock.tick())
        self.w.grant(self.grant, at=self.clock.tick())
        self.run_id = self.w.run_id(AGENT_ID, 1)
        self.intent = LC.request_capability(self.w, agent_id=AGENT_ID, run_id=self.run_id, objective="copy", operation="sandbox.write",
                                            args={"path": "outputs/demo.txt", "content_ref": "fixtures/seed-input.txt"}, at=self.clock.tick())
        self.pd = LC.evaluate_policy(self.w, run_id=self.run_id, intent=self.intent, domain="sandbox", tags=[], spend=0, at=self.clock.tick())
        self.auth, _ = LC.decide_authority(self.w, run_id=self.run_id, agent_id=AGENT_ID, intent=self.intent, policy_decision=self.pd,
                                           grant=self.grant, tool="file_write", at=self.clock.tick(), expires_at=self.clock.plus(600),
                                           actor_authority_class="A2", spend_usd=0, source_sha="s", target={"type": "sandbox_path", "id": "x"})
        self.forecast = LC.seal_forecast(self.w, run_id=self.run_id, intent=self.intent, metric_id="ok", probability=0.7, at=self.clock.tick())
        self.ctx = C.execution_context(context_id="ctx", world_id=WORLD_ID, run_id=self.run_id, sandbox_root=str(self.sandbox),
                                       memory_namespace="m", evidence_namespace="e", created_at=self.clock.tick())

    def execute(self, authority=None, ctx=None, cwd="."):
        return LC.execute(self.w, run_id=self.run_id, agent_id=AGENT_ID, intent=self.intent, authority=authority or self.auth,
                          context=ctx or self.ctx, execution_binding={"bin": "/bin/cp", "argv": ["fixtures/seed-input.txt", "outputs/demo.txt"], "cwd": cwd},
                          started_at=self.clock.tick(), ended_at=self.clock.tick(), evidence_paths=["outputs/demo.txt"])

    def outcome(self, turn, **over):
        grading = {"grade": "success", "quality": "high", "grader_role": "desk", "graded_at": self.clock.plus(2), "calibration_eligible": True}
        return L.observe_outcome(self.w, run_id=self.run_id, outcome_id=over.get("outcome_id", "o1"), case_id="c1",
                                 execution_receipt=over.get("execution_receipt", turn.execution_receipt),
                                 decision_receipt=over.get("decision_receipt", turn.decision_receipt), forecast=self.forecast,
                                 observed={"accepted": True, "actual": [{"metric_id": "ok", "scale": "unit", "unit": "bool", "value": "1",
                                           "evidence_refs": ["ev"], "incomplete": False}], "result": {}},
                                 grading=grading, observed_at=self.clock.tick(), evidence_refs=["ev"])


class InvariantTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()

    def tearDown(self):
        self.h.tmp.cleanup()

    def test_no_action_no_receipt(self):
        turn = self.h.execute()
        self.assertEqual(turn.status, "completed")
        ex = [r for r in self.h.w.receipts if r["correlation_id"] == self.h.run_id and r["receipt_type"] == "execution"]
        self.assertEqual(len(ex), 1)
        self.assertEqual(ex[0]["payload"]["cwd"], ".")
        self.assertTrue(verify_ledger(self.h.w.receipts).ok)
        chain = {r["entry_hash"] for r in self.h.w.receipts}
        for ref in turn.manifest.receipts:
            self.assertIn(ref.entry_hash, chain)
        self.assertEqual([r.seq for r in turn.manifest.receipts], list(range(len(turn.manifest.receipts))))

    def test_no_authority_no_action(self):
        denied, _ = LC.decide_authority(self.h.w, run_id=self.h.run_id, agent_id=AGENT_ID, intent=self.h.intent, policy_decision=self.h.pd,
                                        grant=None, tool="file_write", at=self.h.clock.tick(), expires_at=self.h.clock.plus(60),
                                        actor_authority_class="A2", spend_usd=0, source_sha="s", target={})
        with self.assertRaises(A.AuthorityError):
            self.h.execute(authority=denied)
        self.assertFalse([r for r in self.h.w.receipts if r["receipt_type"] == "execution"])
        self.assertFalse((self.h.sandbox / "outputs" / "demo.txt").exists())

    def test_authority_is_single_use(self):
        self.h.execute()
        with self.assertRaises(A.AuthorityError):
            self.h.execute()
        self.assertEqual(self.h.w.authority_uses[self.h.auth["authority_id"]], 1)

    def test_context_is_not_intent(self):
        self.assertIs(self.h.intent["is_context"], False)
        self.assertIs(self.h.ctx["is_intent"], False)
        self.assertNotIn("sandbox_root", self.h.intent)
        self.assertNotIn("objective", self.h.ctx)
        wrong = C.execution_context(context_id="ctx2", world_id=WORLD_ID, run_id="run-other", sandbox_root=str(self.h.sandbox),
                                    memory_namespace="m", evidence_namespace="e", created_at=AT0)
        with self.assertRaises(LC.LifecycleError):
            self.h.execute(ctx=wrong)

    def test_absolute_cwd_binding_refused(self):
        with self.assertRaises(LC.LifecycleError):
            self.h.execute(cwd=str(self.h.sandbox))

    def test_no_receipt_no_outcome_claim(self):
        turn = self.h.execute()
        with self.assertRaises(L.LearningError):
            self.h.outcome(turn, execution_receipt=turn.decision_receipt)
        foreign = dict(turn.execution_receipt); foreign["correlation_id"] = "run-x"
        with self.assertRaises(L.LearningError):
            self.h.outcome(turn, execution_receipt=foreign)

    def test_synthetic_outcome_is_never_calibration_eligible(self):
        turn = self.h.execute()
        rec = self.h.outcome(turn)
        self.assertIs(rec["is_synthetic"], True)
        self.assertIs(rec["grading"]["calibration_eligible"], False)
        self.assertEqual(rec["authority"], "NONE")

    def test_no_outcome_no_calibration(self):
        with self.assertRaises(L.LearningError):
            L.calibrate(self.h.w, run_id=self.h.run_id, records=[], at=AT0, producer_version="v", calibration_key="k")
        turn = self.h.execute()
        rec = self.h.outcome(turn)
        stranger = {**rec, "content_sha256": "0" * 64}
        with self.assertRaises(L.LearningError):
            L.calibrate(self.h.w, run_id=self.h.run_id, records=[stranger], at=AT0, producer_version="v", calibration_key="k")
        cal = L.calibrate(self.h.w, run_id=self.h.run_id, records=[rec], at=self.h.clock.tick(), producer_version="v", calibration_key="k")
        self.assertEqual(cal["quarantine"], "SYNTHETIC_WORLD")
        self.assertEqual(cal["evidence_class"], "fixture")
        self.assertIs(cal["black_doctrine"]["claim_permitted"], False)      # 1 sample < 30

    def test_proposal_is_not_canonical(self):
        with self.assertRaises(C.ContractError):
            C.seal("learning_proposal", {"learning_proposal_id": "x", "created_at": AT0, "is_canonical": True}, id_field="learning_proposal_id")

    def test_no_approval_no_canonical_revision(self):
        turn = self.h.execute()
        rec = self.h.outcome(turn)
        fake019 = {"schema_version": C.ESTABLISHED["learning_update_proposal"], "proposal_id": "p1", "target_kind": "threshold_config",
                   "target_id": "t", "proposal_digest": "sha256:" + "0" * 64, "sample_count": 30, "current_version": "v1",
                   "candidate_version": "v2", "calibration_summary_digest": "sha256:" + "1" * 64}
        lp = C.learning_proposal(world_id=WORLD_ID, run_id=self.h.run_id, world_mode="synthetic", proposal=fake019, provenance_={},
                                 calibration_digest="sha256:" + "2" * 64, created_at=AT0)
        crp, obs = L.revision_proposal(self.h.w, run_id=self.h.run_id, learning_proposal=lp, observed_state={"v": 2}, at=self.h.clock.tick())
        human = C.actor_identity(actor_id="h", actor_kind="human", authority_class="A6", created_at=AT0)
        agent = C.actor_identity(actor_id="a", actor_kind="agent", authority_class="A2", created_at=AT0)
        kw = dict(run_id=self.h.run_id, crp=crp, capability="canonical_state.revise", delegation_digest="sha256:" + "3" * 64,
                  reversibility_contract_digest="sha256:" + "4" * 64, policy_version="sha256:" + "5" * 64, at=self.h.clock.tick(),
                  expires_at=self.h.clock.plus(60))
        with self.assertRaises(L.LearningError):
            L.authorize(self.h.w, actor=human, approval_digest=None, **kw)
        with self.assertRaises(L.LearningError):
            L.authorize(self.h.w, actor=agent, approval_digest="sha256:" + "6" * 64, **kw)
        self.assertEqual(self.h.w.canonical["state_digest"], self.h.w.manifest and self.h.w.canonical["state_digest"])
        self.assertEqual(self.h.w.revisions, [])

    def test_fixture_evidence_cannot_promote_past_sandbox(self):
        d = {"decision_id": "d", "decision": "promote", "promotion_digest": "sha256:" + "0" * 64}
        with self.assertRaises(C.ContractError):
            C.promotion_decision(world_id=WORLD_ID, run_id="r", decision=d, requested_stage="canary", evidence_class="fixture", created_at=AT0)
        C.promotion_decision(world_id=WORLD_ID, run_id="r", decision=d, requested_stage="sandbox", evidence_class="fixture", created_at=AT0)

    def test_promotion_hold_blocks_revision(self):
        held = C.promotion_decision(world_id=WORLD_ID, run_id="r", decision={"decision_id": "d", "decision": "hold", "promotion_digest": "sha256:" + "0" * 64},
                                    requested_stage="sandbox", evidence_class="fixture", created_at=AT0)
        with self.assertRaises(L.LearningError):
            L.apply_revision(self.h.w, run_id="r", crp={"target_canonical_stage": "sandbox"}, authorization={}, promotion=held,
                             observed_state={}, actor_id="h", started_at=AT0, ended_at=AT0)


class LiveModeSeamTests(unittest.TestCase):
    """The live branch uses outcome-record's real S1 seam (shape test on non-synthetic records)."""

    def test_live_world_uses_real_s1(self):
        h = Harness(live_seed())
        try:
            turn = h.execute()
            rec = h.outcome(turn)
            self.assertIs(rec["grading"]["calibration_eligible"], True)
            cal = L.calibrate(h.w, run_id=h.run_id, records=[rec], at=h.clock.tick(), producer_version="v", calibration_key="k")
            self.assertIsNone(cal["quarantine"])
            self.assertEqual(cal["evidence_class"], "live")
            self.assertEqual(cal["folded_count"], 1)
        finally:
            h.tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
