import json
import tempfile
import unittest
from pathlib import Path

from neuruh_agent_receipt import verify_ledger
from neuruh_sovereign_agent_starter.organism.court import run_court


class CourtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.a = run_court(Path(cls.tmp.name) / "a")
        cls.b = run_court(Path(cls.tmp.name) / "b")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_positive_court_all_21_steps_pass(self):
        self.assertTrue(self.a["all_ok"])
        self.assertEqual([s["step"] for s in self.a["steps"]], list(range(1, 22)))
        self.assertTrue(all(s["ok"] for s in self.a["steps"]))
        self.assertTrue(self.a["ledger_ok"])
        self.assertTrue(self.a["projection_roundtrip_ok"])

    def test_negative_court_production_write_denied(self):
        n = self.a["negative_court"]
        self.assertTrue(n["denied"])
        self.assertEqual(n["authority_decision"], "denied")
        self.assertEqual(n["policy_decision"], "deny")
        self.assertIs(n["facts"]["tool_exists"], True)          # the tool exists; that is not authority
        self.assertIs(n["facts"]["capability_registered"], True)
        self.assertIs(n["facts"]["capability_granted"], False)
        self.assertEqual(n["execution_receipts"], 0)
        self.assertTrue(n["sandbox_unchanged"])
        self.assertFalse(n["network_contacted"])
        self.assertFalse(n["governance_submitted"])

    def test_deterministic_replay_and_cross_run_identity(self):
        self.assertEqual(self.a["state_digest"], self.b["state_digest"])
        self.assertEqual(self.a["receipts_tip"], self.b["receipts_tip"])
        ra = (Path(self.tmp.name) / "a" / "world-demo-001" / "receipts.jsonl").read_text()
        rb = (Path(self.tmp.name) / "b" / "world-demo-001" / "receipts.jsonl").read_text()
        self.assertEqual(ra, rb)
        rr = json.loads((Path(self.tmp.name) / "a" / "world-demo-001" / "replay-receipt.json").read_text())
        self.assertTrue(rr["match"]); self.assertEqual(rr["gaps"], [])
        receipts = [json.loads(l) for l in ra.splitlines()]
        self.assertTrue(verify_ledger(receipts).ok)

    def test_artifacts_written_and_sandbox_removed(self):
        wd = Path(self.tmp.name) / "a" / "world-demo-001"
        for f in ("seed.json", "manifest.json", "receipts.jsonl", "snapshot.json", "replay-receipt.json", "run-manifest.json",
                  "authority-decision.json", "axon-task-projection.json", "world-engine-decision-receipt.json",
                  "effective-canonical-state.json", "cockpit-view.json", "court-report.json", "projection/Worlds/world-demo-001/STATE.md"):
            self.assertTrue((wd / f).exists(), f)
        self.assertFalse((Path(self.tmp.name) / "a" / "sandbox").exists())
        view = json.loads((wd / "cockpit-view.json").read_text())
        self.assertEqual(sorted(view["panels"]), sorted(["WORLD", "AGENT", "INTENT", "CAPABILITY", "POLICY", "AUTHORITY", "ACTION", "RECEIPT",
                                                          "OUTCOME", "CALIBRATION", "CANONICAL_REVISION", "PROMOTION", "MEMORY"]))
        axon = json.loads((wd / "axon-task-projection.json").read_text())
        self.assertTrue(axon["govern_only"])


if __name__ == "__main__":
    unittest.main()
