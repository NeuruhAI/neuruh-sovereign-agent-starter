import copy, json, os, tempfile, unittest
from pathlib import Path

from neuruh_agent_receipt import verify_ledger
from neuruh_agent_run_manifest import RunManifest
from neuruh_sovereign_agent_starter import StarterConfig, StarterError, run, openai_compatible_infer


def base_config(root):
    return {
      "schema_version":"neuruh.sovereign-agent-starter.v0.1",
      "agent_id":"agent-test","mission":"bounded test run","sandbox_root":root,
      "policy":{"policy_id":"p1","blocked_domains":[],"allowed_tools":["demo.print"],"approval_tags":["needs_human"],"max_spend":0},
      "capability_manifest":{"schema_version":"neuruh.capability-registry.v0.1","capabilities":[{"operation":"demo.print","kind":"process","requires_receipt":True,"requires_precondition":False,"allowed_target_types":["stdout"],"arg_schema":{"label":{"type":"string","required":True,"max_length":32}}}]},
      "inference":{"backends":[{"name":"local","kind":"local","base_url":"http://127.0.0.1:9999","model":"demo","health_paths":["/health"]}],"required":False,"prompt":None,"timeout_seconds":0.1},
      "action":{"action_id":"a1","domain":"demo","operation":"demo.print","args":{"label":"x"},"tags":[],"spend":0},
      "execution_binding":{"operation":"demo.print","bin":"/usr/bin/printf","argv":["SOVEREIGN_OK"],"cwd":root},
      "dry_run":False,
    }

class StarterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=self.tmp.name
    def tearDown(self): self.tmp.cleanup()
    def config(self, mutate=None):
        raw=base_config(self.root)
        if mutate: mutate(raw)
        return StarterConfig.from_mapping(raw)
    def test_successful_run_executes_exact_binding(self):
        r=run(self.config(),probe=lambda *_: True,run_id="run-success")
        self.assertEqual(r.manifest.status,"completed"); self.assertEqual(r.execution["code"],"EXECUTED"); self.assertTrue(r.execution["ok"])
    def test_manifest_independently_verifies(self):
        r=run(self.config(),probe=lambda *_: True,run_id="run-manifest")
        self.assertEqual(RunManifest.from_mapping(r.manifest.to_dict()).run_id,"run-manifest")
    def test_receipt_chain_verifies(self):
        r=run(self.config(),probe=lambda *_: True,run_id="run-receipts")
        self.assertTrue(verify_ledger(r.receipts).ok); self.assertGreaterEqual(len(r.receipts),3)
    def test_policy_deny_never_executes(self):
        c=self.config(lambda x: x["policy"]["blocked_domains"].append("demo"))
        r=run(c,probe=lambda *_: True,run_id="run-deny")
        self.assertEqual(r.manifest.status,"denied"); self.assertIsNone(r.execution); self.assertEqual(len(r.manifest.executions),0)
    def test_policy_escalate_never_executes(self):
        c=self.config(lambda x: x["action"]["tags"].append("needs_human"))
        r=run(c,probe=lambda *_: True,run_id="run-escalate")
        self.assertEqual(r.manifest.status,"escalated"); self.assertIsNone(r.execution); self.assertEqual(len(r.manifest.executions),0)
    def test_required_inference_unavailable_fails_before_execution(self):
        c=self.config(lambda x: x["inference"].update(required=True))
        r=run(c,probe=lambda *_: False,run_id="run-no-model")
        self.assertEqual(r.manifest.status,"failed"); self.assertIsNone(r.execution)
    def test_optional_inference_unavailable_can_still_execute(self):
        r=run(self.config(),probe=lambda *_: False,run_id="run-optional")
        self.assertEqual(r.manifest.status,"completed"); self.assertEqual(r.manifest.inference.health,"unavailable")
    def test_inference_output_is_evidence_not_command(self):
        def mutate(x): x["inference"]["prompt"]="say something"
        c=self.config(mutate)
        r=run(c,probe=lambda *_: True,infer=lambda backend,prompt,timeout:"MODEL_SAYS_RM_RF",run_id="run-model-evidence")
        self.assertEqual(r.inference_output,"MODEL_SAYS_RM_RF"); self.assertEqual(r.execution["args"],["SOVEREIGN_OK"]); self.assertTrue(any(e.evidence_id=="inference-output" for e in r.manifest.evidence))
    def test_dry_run_does_not_execute(self):
        c=self.config(lambda x: x.update(dry_run=True))
        r=run(c,probe=lambda *_: True,run_id="run-dry")
        self.assertEqual(r.manifest.status,"dry_run"); self.assertEqual(r.execution["code"],"DRY_RUN"); self.assertEqual(r.manifest.executions[0].status,"dry_run")
    def test_unknown_capability_fails_closed(self):
        c=self.config(lambda x: x["action"].update(operation="missing")) if False else None
        raw=base_config(self.root); raw["action"]["operation"]="missing"; raw["execution_binding"]["operation"]="missing"
        cfg=StarterConfig.from_mapping(raw)
        with self.assertRaises(StarterError) as ctx: run(cfg,probe=lambda *_:True)
        self.assertEqual(ctx.exception.code,"E_CAPABILITY_UNKNOWN")
    def test_bad_capability_args_fail_closed(self):
        raw=base_config(self.root); raw["action"]["args"]={}
        cfg=StarterConfig.from_mapping(raw)
        with self.assertRaises(StarterError) as ctx: run(cfg,probe=lambda *_:True)
        self.assertEqual(ctx.exception.code,"E_ARGUMENTS")
    def test_non_process_capability_rejected(self):
        raw=base_config(self.root); raw["capability_manifest"]["capabilities"][0]["kind"]="data"
        cfg=StarterConfig.from_mapping(raw)
        with self.assertRaises(StarterError) as ctx: run(cfg,probe=lambda *_:True)
        self.assertEqual(ctx.exception.code,"E_CAPABILITY_KIND")
    def test_binding_operation_must_match_action(self):
        raw=base_config(self.root); raw["execution_binding"]["operation"]="other"
        with self.assertRaises(StarterError) as ctx: StarterConfig.from_mapping(raw)
        self.assertEqual(ctx.exception.code,"E_BINDING")
    def test_unknown_config_field_rejected(self):
        raw=base_config(self.root); raw["private_router"]="forbidden"
        with self.assertRaises(StarterError): StarterConfig.from_mapping(raw)
    def test_traversal_cwd_fails_without_escape(self):
        raw=base_config(self.root); raw["execution_binding"]["cwd"]="../"
        cfg=StarterConfig.from_mapping(raw)
        r=run(cfg,probe=lambda *_:True,run_id="run-traversal")
        self.assertEqual(r.manifest.status,"failed"); self.assertFalse(r.execution["ok"]); self.assertIn(r.execution["code"],{"E_TRAVERSAL","E_OUTSIDE_ROOT"})
    def test_execution_failure_records_failed_manifest(self):
        raw=base_config(self.root); raw["execution_binding"]["bin"]="/usr/bin/false"; raw["execution_binding"]["argv"]=[]
        cfg=StarterConfig.from_mapping(raw)
        r=run(cfg,probe=lambda *_:True,run_id="run-fail")
        self.assertEqual(r.manifest.status,"failed"); self.assertFalse(r.execution["ok"])
    def test_remote_inference_endpoint_refused(self):
        class B: base_url="https://provider.example"; model="x"
        with self.assertRaises(StarterError) as ctx: openai_compatible_infer(B(),"hello",0.1)
        self.assertEqual(ctx.exception.code,"E_INFERENCE_ENDPOINT")
    def test_deny_does_not_probe_inference(self):
        c=self.config(lambda x: x["policy"]["blocked_domains"].append("demo"))
        calls=[]
        r=run(c,probe=lambda *a: calls.append(a) or True,run_id="run-no-probe-deny")
        self.assertEqual(r.manifest.status,"denied"); self.assertEqual(calls,[]); self.assertEqual(r.manifest.inference.health,"not_used")
    def test_escalate_does_not_probe_inference(self):
        c=self.config(lambda x: x["action"]["tags"].append("needs_human"))
        calls=[]
        r=run(c,probe=lambda *a: calls.append(a) or True,run_id="run-no-probe-escalate")
        self.assertEqual(r.manifest.status,"escalated"); self.assertEqual(calls,[]); self.assertEqual(r.manifest.inference.health,"not_used")
    def test_remote_backend_rejected_at_config_boundary(self):
        raw=base_config(self.root); raw["inference"]["backends"][0]["base_url"]="https://provider.example"
        with self.assertRaises(StarterError) as ctx: StarterConfig.from_mapping(raw)
        self.assertEqual(ctx.exception.code,"E_INFERENCE_ENDPOINT")
    def test_cloud_backend_rejected_at_config_boundary(self):
        raw=base_config(self.root); raw["inference"]["backends"][0]["kind"]="cloud"
        with self.assertRaises(StarterError) as ctx: StarterConfig.from_mapping(raw)
        self.assertEqual(ctx.exception.code,"E_INFERENCE_ENDPOINT")
    def test_policy_unknown_tool_denies_without_exec(self):
        raw=base_config(self.root); raw["policy"]["allowed_tools"]=["other"]
        cfg=StarterConfig.from_mapping(raw)
        r=run(cfg,probe=lambda *_:True,run_id="run-tool-deny")
        self.assertEqual(r.manifest.status,"denied"); self.assertIsNone(r.execution)

if __name__=="__main__": unittest.main()
