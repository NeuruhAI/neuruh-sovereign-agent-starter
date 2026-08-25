import unittest

from neuruh_sovereign_agent_starter.organism import contracts as C
from neuruh_sovereign_agent_starter.organism import lifecycle as LC
from neuruh_sovereign_agent_starter.organism import product_adapter as PA
from neuruh_sovereign_agent_starter.organism.world import instantiate

AT = "2026-08-24T00:00:01Z"


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapters = PA.all_adapters()
        self.ds = self.adapters["deedsonar-nc"]

    def test_nine_products_declared_not_wired(self):
        self.assertEqual(sorted(self.adapters), sorted(["deedsonar-nc", "property-intelligence", "findsellprofit", "bookeit", "neuruh-factory",
                                                        "venture-factory", "liquidity-engine", "curbclaim", "proofos"]))
        for a in self.adapters.values():
            C.verify(a)
            self.assertEqual(a["adapter_status"], "DECLARED_NOT_WIRED")
            self.assertIs(a["declares_authority"], False)
            for c in a["capabilities"]:
                self.assertIn(c["risk_tier"], C.RISK_TIERS)
        self.assertTrue(self.ds["protected"]); self.assertTrue(self.adapters["property-intelligence"]["protected"])

    def test_deedsonar_separated_capabilities(self):
        self.assertEqual(len(self.ds["agents"]), 7)
        self.assertIs(PA.authorizes(self.ds, role="research", operation="research.property"), True)
        self.assertIs(PA.authorizes(self.ds, role="research", operation="seller.contact"), False)
        self.assertIs(PA.authorizes(self.ds, role="signal", operation="transaction.execute"), False)
        self.assertIs(PA.authorizes(self.ds, role="acquisition", operation="transaction.execute"), False)
        self.assertEqual(PA.authorizes(self.ds, role="janitor", operation="anything"), C.UNKNOWN)
        tiers = {c["operation"]: c["risk_tier"] for c in self.ds["capabilities"]}
        self.assertEqual(tiers["seller.contact"], "R4"); self.assertEqual(tiers["transaction.execute"], "R4")
        self.assertEqual(tiers["research.property"], "R0")

    def test_phone_evidence_never_implies_consent(self):
        phone = [{"source_type": "phone_enrichment", "pointer": "x"}]
        self.assertEqual(PA.consent_fact(phone), C.UNKNOWN)
        self.assertIs(PA.consent_fact(phone + [{"source_type": "consent_record"}]), True)
        self.assertIs(PA.consent_fact(phone + [{"source_type": "dnc_match"}]), False)

    def test_adapter_compiles_to_a_synthetic_world_where_research_cannot_contact(self):
        seed = PA.seed_for_adapter(self.ds, seed_id="seed-ds-nc", seed_version="0.1.0", clock_start="2026-08-24T00:00:00Z")
        self.assertEqual(seed["connectors"], [])
        w = instantiate(seed, world_id="world-deedsonar-nc-synthetic", created_at=AT, creator="t")
        agent = "deedsonar-nc-research"
        w.register_agent(agent, ["research"], at=AT, creator="t")
        tmpl = next(g for g in seed["grant_templates"] if g["subject"] == agent)
        self.assertIn("seller.contact", tmpl["forbidden_operations"])
        grant = C.capability_grant(grant_id="g-research", world_id=w.world_id, issuer="founder", subject=agent, operations=tmpl["operations"],
                                   forbidden_operations=tmpl["forbidden_operations"], max_spend_usd=0, issued_at="2026-08-24T00:00:00Z",
                                   expires_at="2026-08-25T00:00:00Z", evidence_class_ceiling="fixture", stage_ceiling="sandbox", created_at=AT)
        w.grant(grant, at=AT)
        run_id = w.run_id(agent, 1)
        intent = LC.request_capability(w, agent_id=agent, run_id=run_id, objective="contact the seller", operation="seller.contact",
                                       args={"subject_id": "parcel-1"}, at=AT)
        pd = LC.evaluate_policy(w, run_id=run_id, intent=intent, domain="outreach", tags=["external_message"], spend=0, at=AT)
        d, _ = LC.decide_authority(w, run_id=run_id, agent_id=agent, intent=intent, policy_decision=pd, grant=grant, tool="twilio_send", at=AT,
                                   expires_at="2026-08-24T01:00:00Z", actor_authority_class="A2", spend_usd=0, source_sha="s", target={})
        self.assertIs(d["facts"]["tool_exists"], True)
        self.assertIs(d["facts"]["capability_registered"], True)
        self.assertIs(d["facts"]["capability_granted"], False)
        self.assertEqual(d["risk_tier"], "R4")
        self.assertEqual(d["decision"], "denied")


if __name__ == "__main__":
    unittest.main()
