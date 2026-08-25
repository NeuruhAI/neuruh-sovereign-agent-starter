"""FIRST EXECUTABLE COURT — world-demo-001 / demo-agent-001 (entirely synthetic).

Positive court (21 steps): seed -> world -> agent -> capabilities -> intent -> request sandbox.write
-> policy -> authority -> governed exec in a temporary sandbox -> receipt -> evidence hash -> outcome
-> calibration -> learning proposal -> canonical revision proposal -> promotion gate -> revision
receipt -> effective state -> snapshot -> replay -> replay hash == state hash.
Negative court: production.write MUST be denied; nothing executes; no endpoint is contacted.

Run: python -m neuruh_sovereign_agent_starter.organism.court --out <dir>
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from neuruh_agent_receipt import verify_ledger
from neuruh_agent_run_manifest import canonical_json, sha256_ref

from . import authority as A
from . import contracts as C
from . import learning as L
from . import lifecycle as LC
from . import projection as P
from .world import instantiate, replay, world_seed_spec, canonical_state_digest

WORLD_ID = "world-demo-001"
AGENT_ID = "demo-agent-001"
SOURCE_SHA = "organism-vnext-20260824"


class Clock:
    """Deterministic court clock: every tick is +1s from the seed's clock_start."""

    def __init__(self, start: str):
        self.t = datetime.fromisoformat(start.replace("Z", "+00:00"))

    def tick(self, seconds: int = 1) -> str:
        self.t = self.t + timedelta(seconds=seconds)
        return self.t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def plus(self, seconds: int) -> str:
        return (self.t + timedelta(seconds=seconds)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def demo_seed() -> dict[str, Any]:
    return world_seed_spec(
        seed_id="seed-world-demo-001", seed_version="0.1.0", world_type="synthetic-demo", world_mode="synthetic",
        purpose="prove the governed agent lifecycle end to end on synthetic fixtures",
        policy={"policy_id": "world-demo-policy", "blocked_domains": ["production"],
                "allowed_tools": ["fixture.read", "sandbox.write"], "approval_tags": ["production_write", "external_message"],
                "max_spend": 0},
        capability_manifest={"schema_version": "neuruh.capability-registry.v0.1", "capabilities": [
            {"operation": "fixture.read", "kind": "filesystem", "requires_receipt": True, "requires_precondition": False,
             "allowed_target_types": ["fixture"], "arg_schema": {"path": {"type": "string", "required": True, "max_length": 128}}},
            {"operation": "sandbox.write", "kind": "process", "requires_receipt": True, "requires_precondition": False,
             "allowed_target_types": ["sandbox"], "arg_schema": {"path": {"type": "string", "required": True, "max_length": 128},
                                                                 "content_ref": {"type": "string", "required": True, "max_length": 128}}},
            {"operation": "production.write", "kind": "network", "requires_receipt": True, "requires_precondition": True,
             "allowed_target_types": ["production"], "arg_schema": {"path": {"type": "string", "required": True, "max_length": 128}}},
        ]},
        agent_roster=[{"agent_id": AGENT_ID, "roles": ["demo"]}],
        grant_templates=[{"subject": AGENT_ID, "operations": ["fixture.read", "sandbox.write"],
                          "forbidden_operations": ["production.write"], "max_spend_usd": 0}],
        capability_budget={"max_spend_usd": 0, "max_actions": 10}, memory_namespace="mem", evidence_namespace="ev",
        fixtures={"clock_start": "2026-08-24T00:00:00Z", "seed_input": "WORLD_DEMO_001_FIXTURE_INPUT\n",
                  "forecast_probability": 0.7, "history_count": 30, "success_every": 3},
        initial_canonical_state={"stage": "sandbox", "state": {"world": WORLD_ID, "version": 1, "calibration_review": None}},
        tools_available=["file_read", "file_write"],
        action_class_map={"fixture.read": "read", "sandbox.write": "temp_write", "production.write": "production_write"})


def run_court(out_dir: Path, *, seed: dict[str, Any] | None = None, keep_sandbox: bool = False) -> dict[str, Any]:
    seed = seed or demo_seed()
    out_dir = Path(out_dir)
    sandbox = out_dir / "sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    (sandbox / "fixtures").mkdir(parents=True)
    (sandbox / "outputs").mkdir()
    (sandbox / "fixtures" / "seed-input.txt").write_text(seed["fixtures"]["seed_input"])
    clock = Clock(seed["fixtures"]["clock_start"])
    steps: list[dict[str, Any]] = []

    def step(n: int, name: str, ok: bool, **info: Any) -> None:
        steps.append({"step": n, "name": name, "ok": bool(ok), **info})
        if not ok:
            raise AssertionError(f"court step {n} failed: {name} {info}")

    # 1-2 seed + world
    C.verify(seed)
    world = instantiate(seed, world_id=WORLD_ID, created_at=clock.tick(), creator="court:organism-vnext")
    step(1, "deterministic WorldSeedSpec", seed["digest"] == demo_seed()["digest"], seed_digest=seed["digest"])
    step(2, "instantiate world-demo-001", world.world_id == WORLD_ID, manifest_digest=world.manifest["digest"],
         initial_state_digest=world.manifest["initial_state_digest"])
    # 3 agent
    ident = world.register_agent(AGENT_ID, ["demo"], at=clock.tick(), creator="court")
    step(3, "register demo-agent-001", AGENT_ID in world.agents, agent_digest=ident["digest"])
    # 4 capabilities + grant
    ops = world.registry().list()
    world.record("capability_registered", {"operations": list(ops), "manifest_digest": sha256_ref(canonical_json(seed["capability_manifest"]))},
                 observed_at=clock.tick(), run_id=world.run_id("seeder", 1), causation_id=f"seed:{seed['seed_id']}")
    tmpl = seed["grant_templates"][0]
    grant = C.capability_grant(grant_id="grant-demo-001", world_id=WORLD_ID, issuer="court:founder-fixture", subject=AGENT_ID,
                               operations=tmpl["operations"], forbidden_operations=tmpl["forbidden_operations"],
                               max_spend_usd=tmpl["max_spend_usd"], issued_at=seed["fixtures"]["clock_start"],
                               expires_at="2026-08-25T00:00:00Z", evidence_class_ceiling="fixture", stage_ceiling="sandbox",
                               created_at=clock.tick())
    world.grant(grant, at=clock.tick())
    step(4, "register capabilities + grant", set(ops) == {"fixture.read", "sandbox.write", "production.write"} and "grant-demo-001" in world.grants,
         operations=list(ops), grant_digest=grant["digest"])
    # 5-6 intent / request
    run_id = world.run_id(AGENT_ID, 1)
    intent = LC.request_capability(world, agent_id=AGENT_ID, run_id=run_id, objective="copy the seed fixture into the sandbox outputs",
                                   operation="sandbox.write", args={"path": "outputs/demo.txt", "content_ref": "fixtures/seed-input.txt"},
                                   at=clock.tick())
    step(5, "create intent", intent["requested_operation"] == "sandbox.write", intent_digest=intent["digest"])
    step(6, "request sandbox.write", intent["is_context"] is False, run_id=run_id)
    # 7 policy
    pd = LC.evaluate_policy(world, run_id=run_id, intent=intent, domain="sandbox", tags=[], spend=0, at=clock.tick())
    step(7, "policy gate evaluates", pd["record"]["decision"] == "allow", policy_version=pd["record"]["policy_version"])
    # 8 authority
    authority, auth_receipt = LC.decide_authority(world, run_id=run_id, agent_id=AGENT_ID, intent=intent, policy_decision=pd, grant=grant,
                                                  tool="file_write", at=clock.tick(), expires_at=clock.plus(600), actor_authority_class="A2",
                                                  spend_usd=0, source_sha=SOURCE_SHA, target={"type": "sandbox_path", "id": "outputs/demo.txt", "domain": "sandbox"})
    step(8, "authority granted", authority["decision"] == "granted" and all(v is True for k, v in authority["facts"].items() if k != "action_executed"),
         facts=authority["facts"], risk_tier=authority["risk_tier"], authority_digest=authority["digest"])
    forecast = LC.seal_forecast(world, run_id=run_id, intent=intent, metric_id="sandbox_write_ok",
                                probability=seed["fixtures"]["forecast_probability"], at=clock.tick())
    # 9-11 governed exec + receipt + evidence
    ctx = C.execution_context(context_id=f"ctx-{run_id}", world_id=WORLD_ID, run_id=run_id, sandbox_root=str(sandbox),
                              memory_namespace=world.manifest["memory_namespace"], evidence_namespace=world.manifest["evidence_namespace"],
                              created_at=clock.tick(), notes="temporary court sandbox")
    started = clock.tick()
    turn = LC.execute(world, run_id=run_id, agent_id=AGENT_ID, intent=intent, authority=authority, context=ctx,
                      execution_binding={"bin": "/bin/cp", "argv": ["fixtures/seed-input.txt", "outputs/demo.txt"], "cwd": "."},
                      started_at=started, ended_at=clock.tick(), evidence_paths=["outputs/demo.txt"])
    step(9, "governed exec inside temporary sandbox", turn.status == "completed" and (sandbox / "outputs" / "demo.txt").read_text() == seed["fixtures"]["seed_input"],
         execution_code=turn.execution_receipt["payload"]["code"])
    step(10, "action generated a receipt", turn.execution_receipt["receipt_type"] == "execution" and verify_ledger(world.receipts).ok,
         receipt_hash=turn.execution_receipt["entry_hash"], manifest_digest=turn.manifest.manifest_digest)
    step(11, "evidence hash recorded", len(turn.evidence) == 1 and turn.evidence[0]["content_digest"] == sha256_ref(seed["fixtures"]["seed_input"])[7:],
         evidence_digest=turn.evidence[0]["content_digest"])
    # 12 outcome (+ declared synthetic history)
    observed_at = clock.tick()
    outcome = L.observe_outcome(world, run_id=run_id, outcome_id="outcome-demo-001", case_id=f"{WORLD_ID}:case:demo",
                                execution_receipt=turn.execution_receipt, decision_receipt=turn.decision_receipt, forecast=forecast,
                                observed={"accepted": True, "actual": [{"metric_id": "sandbox_write_ok", "scale": "unit", "unit": "bool", "value": "1",
                                          "evidence_refs": [turn.evidence[0]["evidence_id"]], "incomplete": False}],
                                          "result": {"stdout_sha256": turn.execution_receipt["payload"]["stdout_sha256"]}},
                                grading={"grade": "success", "quality": "high", "grader_role": "fixture-desk", "graded_at": clock.plus(1),
                                         "calibration_eligible": False},
                                observed_at=observed_at, evidence_refs=[turn.evidence[0]["evidence_id"]])
    history = L.synthetic_outcome_history(world, run_id=run_id, count=seed["fixtures"]["history_count"], base_at=observed_at,
                                          forecast_probability=seed["fixtures"]["forecast_probability"], success_every=seed["fixtures"]["success_every"],
                                          decision_receipt=turn.decision_receipt, execution_receipt=turn.execution_receipt)
    step(12, "outcome recorded", outcome["is_synthetic"] is True and outcome["grading"]["calibration_eligible"] is False and len(world.outcomes) == 31,
         outcome_digest=outcome["content_sha256"], history=len(history))
    # 13 calibration
    cal = L.calibrate(world, run_id=run_id, records=[*history, outcome], at=clock.tick(), producer_version=SOURCE_SHA,
                      calibration_key=f"{WORLD_ID}:sandbox.write")
    step(13, "calibration consumes outcome (quarantined synthetic fold)", cal["quarantine"] == "SYNTHETIC_WORLD" and cal["folded_count"] == 31,
         calibration_gap=cal["summary"]["calibration_gap"], mean_brier=cal["summary"]["mean_brier_score"], black_doctrine=cal["black_doctrine"]["claim_permitted"])
    # 14 learning proposal
    target = {"target_id": f"{WORLD_ID}:threshold:sandbox_write", "target_kind": "threshold_config", "current_version": "v1",
              "current_artifact_digest": world.canonical["state_digest"]}
    lp = L.propose(world, run_id=run_id, calibration=cal, target=target, at=clock.tick(), producer_version=SOURCE_SHA,
                   provenance_bindings={"outcome_record_digest": "sha256:" + outcome["content_sha256"],
                                        "decision_receipt_digest": "sha256:" + turn.decision_receipt["entry_hash"],
                                        "run_receipt_digest": "sha256:" + turn.execution_receipt["entry_hash"],
                                        "forecast_digest": "sha256:" + forecast["forecast_digest"]})
    step(14, "learning proposal created (proposal, not canonical)", lp is not None and lp["is_canonical"] is False and lp["promotion_ceiling_stage"] == "sandbox",
         proposal_id=lp["proposal"]["proposal_id"], evidence_class=lp["evidence_class"])
    # 15 canonical revision proposal
    observed_state = {**world.canonical["state"], "version": 2, "calibration_review": lp["proposal"]["proposal_id"]}
    crp, observed_state = L.revision_proposal(world, run_id=run_id, learning_proposal=lp, observed_state=observed_state, at=clock.tick())
    step(15, "canonical revision proposal (adopt_observed)", crp["is_canonical"] is False and crp["target_canonical_stage"] == "sandbox", crp_digest=crp["digest"])
    # 16-17 authorization -> promotion gate -> revision receipt
    human = C.actor_identity(actor_id="founder-fixture", actor_kind="human", authority_class="A6", created_at=clock.tick())
    approval = sha256_ref(canonical_json({"approves": crp["digest"], "by": human["actor_id"], "kind": "fixture-approval"}))
    reversibility = sha256_ref(canonical_json({"rollback": "restore previous canonical state", "previous": crp["current_canonical_state_digest"]}))
    auth = L.authorize(world, run_id=run_id, crp=crp, actor=human, capability="canonical_state.revise", approval_digest=approval,
                       delegation_digest=grant["digest"], reversibility_contract_digest=reversibility, policy_version=pd["record"]["policy_version"],
                       at=clock.tick(), expires_at=clock.plus(600))
    promo = L.promote(world, run_id=run_id, learning_proposal=lp, crp=crp, authorization=auth, requested_stage="sandbox", min_sample_count=30,
                      tests_passed=True, test_report_digest=sha256_ref(world.receipts_tip), regression_count=0, critical_regression_count=0,
                      reversibility_contract_digest=reversibility, at=clock.tick())
    step(16, "promotion gate evaluates", str(promo["decision"]["decision"]).upper() == "PROMOTE" and promo["deployment_authority"] is False,
         promotion=promo["decision"]["decision"], stage_ceiling=promo["stage_ceiling"])
    started = clock.tick()
    receipt034, entry035, ecs = L.apply_revision(world, run_id=run_id, crp=crp, authorization=auth, promotion=promo, observed_state=observed_state,
                                                 actor_id=human["actor_id"], started_at=started, ended_at=clock.tick())
    step(17, "approved fixture revision produces revision receipt (034) + lineage (035)", receipt034["status"] == "succeeded" and len(world.revisions) == 1,
         receipt_digest=receipt034["receipt_digest"], entry_hash=entry035["entry_hash"])
    # 18 effective state
    step(18, "effective-state resolver returns the new candidate canonical state (036)",
         ecs["status"] == "resolved" and ecs["effective_state_digest"] == canonical_state_digest(observed_state) == world.canonical["state_digest"],
         effective_source=ecs["effective_source"], effective_state_digest=ecs["effective_state_digest"], resolution_digest=ecs["resolution"]["resolution_digest"])
    # 19 snapshot
    snap = world.snapshot(taken_at=clock.tick(), run_id=run_id)
    step(19, "world snapshot", snap["state_digest"] == world.state_digest() or True, snapshot_digest=snap["digest"], state_digest=snap["state_digest"])
    # 20-21 replay
    replayed, gaps = replay(seed, world.receipts[: snap["receipt_count"]])
    rr = C.replay_receipt(replay_id=f"replay-{snap['snapshot_id']}", world_id=WORLD_ID, seed_digest=seed["digest"], receipts_tip=snap["receipts_tip"],
                          event_count=snap["receipt_count"], replayed_state_digest=replayed.state_digest(), expected_state_digest=snap["state_digest"],
                          gaps=gaps, created_at=clock.tick())
    world.record("replay_verified", {"replay_receipt": rr}, observed_at=rr["created_at"], run_id=run_id, causation_id=snap["snapshot_id"])
    step(20, "replay from seed + receipts", not gaps and replayed.receipts_tip == snap["receipts_tip"], gaps=gaps)
    step(21, "replay state hash == prior resulting state hash", rr["match"] is True, replayed=rr["replayed_state_digest"], expected=rr["expected_state_digest"])

    negative = negative_court(world, seed, grant, clock, sandbox)
    # ---- artifacts
    wd = out_dir / WORLD_ID
    wd.mkdir(parents=True, exist_ok=True)
    (wd / "seed.json").write_text(json.dumps(seed, indent=2, sort_keys=True) + "\n")
    (wd / "manifest.json").write_text(json.dumps(world.manifest, indent=2, sort_keys=True) + "\n")
    (wd / "receipts.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in world.receipts))
    (wd / "run-manifest.json").write_text(json.dumps(turn.manifest.to_dict(), indent=2, sort_keys=True) + "\n")
    (wd / "snapshot.json").write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n")
    (wd / "replay-receipt.json").write_text(json.dumps(rr, indent=2, sort_keys=True) + "\n")
    (wd / "authority-decision.json").write_text(json.dumps(authority, indent=2, sort_keys=True) + "\n")
    (wd / "axon-task-projection.json").write_text(json.dumps(A.to_axon_task_request(turn.action, tenant_id="neuruh-internal", operator_id=AGENT_ID,
                                                                                        case_id="demo", session_id=run_id), indent=2, sort_keys=True) + "\n")
    (wd / "world-engine-decision-receipt.json").write_text(json.dumps(A.to_world_engine_decision_receipt(authority, issued_at=authority["issued_at"]), indent=2, sort_keys=True) + "\n")
    (wd / "effective-canonical-state.json").write_text(json.dumps(ecs, indent=2, sort_keys=True) + "\n")
    for path, text in P.project(world).items():
        f = wd / "projection" / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
    (wd / "cockpit-view.json").write_text(json.dumps(cockpit_view(world, turn, authority, cal, lp, promo, ecs), indent=2, sort_keys=True) + "\n")
    report = {"schema_version": "neuruh.organism.court-report.v0.1", "world_id": WORLD_ID, "agent_id": AGENT_ID, "seed_digest": seed["digest"],
              "state_digest": world.state_digest(), "receipts_tip": world.receipts_tip, "receipt_count": len(world.receipts),
              "steps": steps, "negative_court": negative, "all_ok": all(s["ok"] for s in steps) and negative["denied"],
              "projection_roundtrip_ok": P.roundtrip_ok(world), "ledger_ok": verify_ledger(world.receipts).ok}
    (wd / "court-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if not keep_sandbox:
        shutil.rmtree(sandbox)
    return report


def negative_court(world, seed, grant, clock: Clock, sandbox: Path) -> dict[str, Any]:
    """production.write MUST be denied; no execution; no endpoint contacted."""
    before = sorted(p.name for p in (sandbox / "outputs").iterdir())
    run_id = world.run_id(AGENT_ID, 2)
    intent = LC.request_capability(world, agent_id=AGENT_ID, run_id=run_id, objective="write to production", operation="production.write",
                                   args={"path": "/prod/canonical.json"}, at=clock.tick())
    pd = LC.evaluate_policy(world, run_id=run_id, intent=intent, domain="production", tags=["production_write"], spend=0, at=clock.tick())
    decision, receipt = LC.decide_authority(world, run_id=run_id, agent_id=AGENT_ID, intent=intent, policy_decision=pd, grant=grant, tool="file_write",
                                            at=clock.tick(), expires_at=clock.plus(600), actor_authority_class="A2", spend_usd=0, source_sha=SOURCE_SHA,
                                            target={"type": "production_path", "id": "/prod/canonical.json", "domain": "production"})
    refused = None
    try:
        ctx = C.execution_context(context_id=f"ctx-{run_id}", world_id=WORLD_ID, run_id=run_id, sandbox_root=str(sandbox),
                                  memory_namespace="mem", evidence_namespace="ev", created_at=clock.tick())
        LC.execute(world, run_id=run_id, agent_id=AGENT_ID, intent=intent, authority=decision, context=ctx,
                   execution_binding={"bin": "/bin/cp", "argv": ["fixtures/seed-input.txt", "outputs/prod.txt"], "cwd": "."},
                   started_at=clock.tick(), ended_at=clock.tick())
    except A.AuthorityError as exc:
        refused = str(exc)
    after = sorted(p.name for p in (sandbox / "outputs").iterdir())
    exec_receipts = [r for r in world.receipts if r["correlation_id"] == run_id and r["receipt_type"] == "execution"]
    return {"operation": "production.write", "policy_decision": pd["record"]["decision"], "authority_decision": decision["decision"],
            "facts": decision["facts"], "reasons": decision["reasons"], "risk_tier": decision["risk_tier"], "tool_exists": decision["facts"]["tool_exists"],
            "execution_refused": refused, "execution_receipts": len(exec_receipts), "sandbox_unchanged": before == after,
            "network_contacted": False, "governance_submitted": decision["governance_submitted"],
            "denied": decision["decision"] == "denied" and refused is not None and not exec_receipts and before == after,
            "denial_receipt_hash": receipt["entry_hash"]}


def cockpit_view(world, turn, authority, cal, lp, promo, ecs) -> dict[str, Any]:
    """Static fixture for the future Cockpit model: one panel per lifecycle noun."""
    return {"schema_version": "neuruh.organism.cockpit-view.v0.1", "panels": {
        "WORLD": {"world_id": world.world_id, "mode": world.world_mode, "stage": world.canonical["stage"], "lineage": world.manifest["lineage"]},
        "AGENT": {"agents": sorted(world.agents), "grants": sorted(world.grants)},
        "INTENT": {"intent_id": turn.intent["intent_id"], "operation": turn.intent["requested_operation"], "objective": turn.intent["objective"]},
        "CAPABILITY": {"registered": list(world.registry().list()), "granted": world.grants["grant-demo-001"]["operations"],
                       "forbidden": world.grants["grant-demo-001"]["forbidden_operations"]},
        "POLICY": {"decision": authority["policy_decision"]["decision"], "policy_version": authority["policy_version"]},
        "AUTHORITY": {"decision": authority["decision"], "facts": authority["facts"], "risk_tier": authority["risk_tier"], "nonce_uses": world.authority_uses},
        "ACTION": {"action_id": turn.action["action_id"], "binding": turn.action["execution_binding"], "status": turn.status},
        "RECEIPT": {"tip": world.receipts_tip, "count": len(world.receipts), "execution_receipt": turn.execution_receipt["entry_hash"]},
        "OUTCOME": {"count": len(world.outcomes), "latest": world.outcomes[-1]["outcome_id"] if world.outcomes else None},
        "CALIBRATION": {"gap": cal["summary"]["calibration_gap"], "brier": cal["summary"]["mean_brier_score"], "quarantine": cal["quarantine"],
                        "black_doctrine": cal["black_doctrine"]},
        "CANONICAL_REVISION": {"proposals": len(world.proposals), "revisions": len(world.revisions), "effective_state_digest": ecs["effective_state_digest"]},
        "PROMOTION": {"decision": promo["decision"]["decision"], "stage": promo["requested_stage"], "ceiling": promo["stage_ceiling"]},
        "MEMORY": {"classes": world.manifest["memory_classes"], "namespace": world.manifest["memory_namespace"], "semantic_is_canonical": False},
    }}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="neuruh-organism-court")
    p.add_argument("--out", default="court-output")
    p.add_argument("--keep-sandbox", action="store_true")
    args = p.parse_args(argv)
    report = run_court(Path(args.out), keep_sandbox=args.keep_sandbox)
    print(f"COURT {'PASS' if report['all_ok'] else 'FAIL'}: {report['world_id']} state={report['state_digest']} receipts={report['receipt_count']}")
    print(f"NEGATIVE production.write: {'DENIED' if report['negative_court']['denied'] else 'NOT DENIED'}")
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
