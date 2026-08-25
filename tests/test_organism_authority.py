import unittest

from neuruh_sovereign_agent_starter.organism import authority as A
from neuruh_sovereign_agent_starter.organism import contracts as C
from neuruh_sovereign_agent_starter.organism import lifecycle as LC
from neuruh_sovereign_agent_starter.organism.court import AGENT_ID, WORLD_ID, demo_seed
from neuruh_sovereign_agent_starter.organism.world import instantiate

AT = "2026-08-24T00:00:01Z"
EXP = "2026-08-24T01:00:00Z"
REQUEST_STRING_FIELDS = ["schema_version", "request_id", "mission_id", "plan_id", "step_id", "correlation_id", "causation_id",
                         "authority_class", "operation", "tool", "mutation_class", "evidence_class", "repository", "domain",
                         "summary", "requested_capability", "policy_version", "precondition_hash", "nonce", "issued_at"]


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.w = instantiate(demo_seed(), world_id=WORLD_ID, created_at=AT, creator="t")
        self.w.register_agent(AGENT_ID, ["demo"], at=AT, creator="t")
        self.grant = C.capability_grant(grant_id="g", world_id=WORLD_ID, issuer="founder", subject=AGENT_ID,
                                        operations=["fixture.read", "sandbox.write"], forbidden_operations=["production.write"],
                                        max_spend_usd=0, issued_at="2026-08-24T00:00:00Z", expires_at="2026-08-25T00:00:00Z",
                                        evidence_class_ceiling="fixture", stage_ceiling="sandbox", created_at=AT)
        self.w.grant(self.grant, at=AT)
        self.run_id = self.w.run_id(AGENT_ID, 1)

    def intent(self, op="sandbox.write", args=None):
        return LC.request_capability(self.w, agent_id=AGENT_ID, run_id=self.run_id, objective="o", operation=op,
                                     args=args or {"path": "outputs/x", "content_ref": "fixtures/y"}, at=AT)

    def decide(self, intent, *, grant="default", tool="file_write", domain="sandbox", tags=(), spend=0.0, at=AT):
        pd = LC.evaluate_policy(self.w, run_id=self.run_id, intent=intent, domain=domain, tags=list(tags), spend=spend, at=AT)
        g = self.grant if grant == "default" else grant
        d, _ = LC.decide_authority(self.w, run_id=self.run_id, agent_id=AGENT_ID, intent=intent, policy_decision=pd, grant=g,
                                   tool=tool, at=at, expires_at=EXP, actor_authority_class="A2", spend_usd=spend, source_sha="s",
                                   target={"type": "sandbox_path", "id": "x", "domain": domain})
        return d

    def test_all_facts_true_grants(self):
        d = self.decide(self.intent())
        self.assertEqual(d["decision"], "granted")
        self.assertEqual(d["risk_tier"], "R1")
        self.assertEqual(d["world_engine_level"], "L1_PREPARE")
        self.assertIs(d["facts"]["action_executed"], False)
        self.assertEqual(d["max_uses"], 1)

    def test_tool_existence_is_not_authority(self):
        d = self.decide(self.intent(), grant=None)
        self.assertIs(d["facts"]["tool_exists"], True)
        self.assertIs(d["facts"]["capability_registered"], True)
        self.assertIs(d["facts"]["capability_granted"], False)
        self.assertEqual(d["decision"], "denied")
        self.assertIs(d["execution_authority"], False)

    def test_unknown_is_not_false(self):
        d = self.decide(self.intent(), tool=None)
        self.assertEqual(d["facts"]["tool_exists"], C.UNKNOWN)
        self.assertIsNot(d["facts"]["tool_exists"], False)
        self.assertEqual(d["decision"], "denied")
        tampered = {**self.grant, "operations": ["production.write"]}     # digest no longer matches
        d2 = self.decide(self.intent(), grant=tampered)
        self.assertEqual(d2["facts"]["capability_granted"], C.UNKNOWN)
        self.assertEqual(d2["decision"], "denied")
        with self.assertRaises(C.ContractError):
            C.tri("maybe", "x")

    def test_policy_escalate_becomes_approval_required(self):
        d = self.decide(self.intent(), tags=["external_message"])
        self.assertEqual(d["facts"]["policy_allows"], C.UNKNOWN)
        self.assertEqual(d["decision"], "approval_required")
        self.assertIs(d["facts"]["authority_present"], False)

    def test_forbidden_expired_and_overspend_deny(self):
        self.assertEqual(self.decide(self.intent("production.write", {"path": "/p"}), domain="production")["decision"], "denied")
        self.assertEqual(self.decide(self.intent(), at="2026-08-26T00:00:00Z")["decision"], "denied")
        self.assertEqual(self.decide(self.intent(), spend=5.0)["decision"], "denied")

    def test_unknown_action_class_fails_closed(self):
        d = A.decide(world_id=WORLD_ID, run_id=self.run_id, agent_id=AGENT_ID, intent=self.intent(), registry=self.w.registry(),
                     policy_record={"action_id": "a", "decision": "allow", "policy_id": "p", "policy_version": "sha256:" + "0" * 64, "reasons": []},
                     grant=self.grant, tools_available=self.w.tools_available, tool="file_write", action_class="warp_drive",
                     actor_authority_class="A2", spend_usd=0, at=AT, expires_at=EXP, evidence_class="fixture", source_sha="s", target={})
        self.assertEqual(d["decision"], "denied")
        self.assertIsNone(d["risk_tier"])

    def test_no_authority_no_action_and_single_use(self):
        denied = self.decide(self.intent(), grant=None)
        with self.assertRaises(A.AuthorityError):
            A.assert_usable(denied, at=AT, uses_so_far=0)
        granted = self.decide(self.intent())
        A.assert_usable(granted, at=AT, uses_so_far=0)
        with self.assertRaises(A.AuthorityError):
            A.assert_usable(granted, at=AT, uses_so_far=1)
        with self.assertRaises(A.AuthorityError):
            A.assert_usable(granted, at="2026-08-24T02:00:00Z", uses_so_far=0)

    def test_governance_projection_is_complete_and_unsubmitted(self):
        d = self.decide(self.intent())
        g = d["governance_request"]
        for f in REQUEST_STRING_FIELDS:
            self.assertIsInstance(g[f], str); self.assertTrue(g[f], f)
        self.assertEqual(g["schema_version"], "gov.decision.request.v1")
        self.assertEqual(g["mutation_class"], "reversible_write")
        self.assertIs(d["governance_submitted"], False)
        self.assertEqual(g["requester"]["component"], "neuruh-sovereign-agent-starter/organism")

    def test_world_engine_projection_checksum(self):
        from hashlib import sha256
        from neuruh_agent_run_manifest import canonical_json
        d = self.decide(self.intent())
        r = A.to_world_engine_decision_receipt(d, issued_at=AT)
        body = {k: v for k, v in r.items() if k != "checksum"}
        self.assertEqual(r["checksum"], sha256(canonical_json(body).encode()).hexdigest())
        self.assertEqual(r["authority"], "L1_PREPARE")


if __name__ == "__main__":
    unittest.main()
