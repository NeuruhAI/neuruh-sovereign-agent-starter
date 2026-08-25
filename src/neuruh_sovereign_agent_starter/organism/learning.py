"""Outcome compounding loop — the governed back half, composed from the real primitives.

    ACTION RECEIPT -> OUTCOME RECORD (outcome-record v1, AUTHORITY=NONE)
                   -> CALIBRATION (017 via outcome-record S1, or a quarantined fixture fold)
                   -> LEARNING PROPOSAL (019 via outcome-record S2; proposal only)
                   -> CANONICAL REVISION PROPOSAL (030 shape; proposal only)
                   -> AUTHORIZATION CONTRACT (033; needs a human approval digest)
                   -> PROMOTION GATE (020; PROMOTE/HOLD/BLOCK, never deployment authority)
                   -> REVISION RECEIPT (034) -> REVISION LEDGER (035) -> EFFECTIVE STATE (036)

Every step is recorded on the world's receipt chain so replay can rebuild it.
Learning stays governed: no step here can apply anything without the 033
authorization, and a fixture/synthetic world can never promote past `sandbox`.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence

from neuruh_agent_run_manifest import canonical_json, sha256_ref
from neuruh_canonical_state_revision_authorization_contract import create_authorization, verify_authorization
from neuruh_canonical_state_revision_ledger import CanonicalRevisionLedger, append_revision
from neuruh_canonical_state_revision_receipt import create_receipt
from neuruh_effective_canonical_state_resolver import resolve
from neuruh_outcome_calibration_ledger import CalibrationEntry, CalibrationLedger, summarize
from neuruh_outcome_record import (
    OutcomeRecordError, black_doctrine_assess, build_record, s2_calibration_to_learning_update,
    to_017_summary, to_governance_request, verify_record,
)
from neuruh_promotion_gate import PromotionGate, PromotionPolicy, PromotionRequest

from . import contracts as C
from .world import World, canonical_state_digest

GRADE_ACTUAL = {"success": 1, "failure": 0}


class LearningError(C.ContractError):
    pass


# ------------------------------------------------------------------ outcome
def observe_outcome(world: World, *, run_id: str, outcome_id: str, case_id: str, execution_receipt: Mapping[str, Any],
                    decision_receipt: Mapping[str, Any], forecast: Mapping[str, Any], observed: Mapping[str, Any],
                    grading: Mapping[str, Any], observed_at: str, evidence_refs: Sequence[str] = (),
                    entity: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """NO_RECEIPT_NO_OUTCOME_CLAIM: an outcome binds to an execution receipt and a decision receipt."""
    if execution_receipt.get("receipt_type") != "execution" or execution_receipt.get("authority") != "execution-evidence":
        raise LearningError("outcome requires an execution-evidence receipt")
    if decision_receipt.get("receipt_type") != "decision":
        raise LearningError("outcome requires a governance-decision receipt")
    if execution_receipt["correlation_id"] != run_id:
        raise LearningError("execution receipt belongs to a different run")
    synthetic = world.world_mode == "synthetic"
    test = world.world_mode == "fixture"
    grading = dict(grading)
    if synthetic or test:
        grading["calibration_eligible"] = False      # the primitive refuses otherwise; we never lie to it
    record = build_record(
        outcome_id=outcome_id, case_id=case_id, observed=dict(observed), observed_at=observed_at,
        evidence_refs=list(evidence_refs), grading=grading,
        decision_receipt_digest=decision_receipt["entry_hash"], run_receipt_digest=execution_receipt["entry_hash"],
        forecast=dict(forecast), entity=dict(entity or {}), is_test=test, is_synthetic=synthetic)
    verify_record(record)
    world.record("outcome_observed", {"outcome_record": record, "world_mode": world.world_mode},
                 observed_at=observed_at, run_id=run_id, causation_id=execution_receipt["entry_hash"])
    return record


def synthetic_outcome_history(world: World, *, run_id: str, count: int, base_at: str, forecast_probability: float,
                              success_every: int, decision_receipt: Mapping[str, Any],
                              execution_receipt: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Deterministic fixture history so a synthetic world can exercise calibration honestly
    (every record is is_synthetic=True and never calibration_eligible for the live path)."""
    out = []
    for i in range(count):
        p = base_at.split("T")[0]
        at = f"{p}T{10 + i // 60:02d}:{i % 60:02d}:00Z"
        forecast = {"forecast_digest": sha256(f"forecast|{world.world_id}|{i}".encode()).hexdigest(),
                    "forecast_version": "fixture-fc-v1", "predicted": [{"metric_id": "sandbox_write_ok", "scale": "unit",
                    "unit": "prob", "value": str(forecast_probability)}], "probability": forecast_probability,
                    "recorded_at": at}
        success = (i % success_every) == 0
        obs = {"accepted": success, "actual": [{"metric_id": "sandbox_write_ok", "scale": "unit", "unit": "bool",
               "value": "1" if success else "0", "evidence_refs": [f"ev-fixture-{i}"], "incomplete": False}], "result": {}}
        rec = observe_outcome(world, run_id=run_id, outcome_id=f"fixture-outcome-{i:03d}", case_id=f"{world.world_id}:case:{i:03d}",
                              execution_receipt=execution_receipt, decision_receipt=decision_receipt, forecast=forecast,
                              observed=obs, grading={"grade": "success" if success else "failure", "quality": "high",
                                                     "grader_role": "fixture-desk", "graded_at": f"{p}T12:{i % 60:02d}:30Z",
                                                     "calibration_eligible": False},
                              observed_at=f"{p}T12:{i % 60:02d}:00Z", evidence_refs=[f"ev-fixture-{i}"])
        out.append(rec)
    return out


# ------------------------------------------------------------------ calibration
def _fixture_fold(world: World, records: Sequence[Mapping[str, Any]], *, ledger_id: str, producer_id: str,
                  producer_version: str, calibration_key: str) -> dict[str, Any]:
    """Quarantined mirror of outcome-record S1 for non-live worlds: same 017 primitives, same
    pre-outcome rule, same Brier — but tagged synthetic and NEVER promotable past sandbox."""
    entries, skipped, s1 = [], [], []
    prev = None
    for seq, rec in enumerate(records):
        verify_record(rec)
        f, g = rec["forecast"], rec["grading"]
        why = None
        if "probability" not in f or not f.get("recorded_at"):
            why = "forecast lacks probability/recorded_at"
        elif not (str(f["recorded_at"]) < str(rec["observed_at"])):
            why = "forecast is not pre-outcome"
        elif g["grade"] not in GRADE_ACTUAL:
            why = f"grade {g['grade']!r} has no binary actual"
        if why:
            skipped.append({"outcome_id": rec["outcome_id"], "reason": why})
            continue
        d = rec["content_sha256"]
        entry = CalibrationEntry(
            ledger_id=ledger_id, calibration_id=f"cal-{d[:16]}", sequence=len(entries),
            run_id=f"run:{rec['run_receipt_digest']}", action_id=f"dec:{rec['decision_receipt_digest']}",
            prediction_id=f"pred-{d[:16]}", calibration_key=calibration_key, producer_id=producer_id,
            producer_version=producer_version, decision_receipt_digest="sha256:" + rec["decision_receipt_digest"],
            prediction_digest="", predicted_probability=float(f["probability"]), predicted_at=f["recorded_at"],
            outcome_digest="sha256:" + d, actual_outcome=GRADE_ACTUAL[g["grade"]], observed_at=rec["observed_at"],
            tags=("synthetic", f"world:{world.world_id}", f"mode:{world.world_mode}"), previous_entry_hash=prev)
        entry = CalibrationEntry(**{**entry.__dict__, "prediction_digest": entry.calculated_prediction_digest()}).seal()
        entries.append(entry)
        s1.append({"outcome_record_digest": d, "probability": float(f["probability"]), "actual": GRADE_ACTUAL[g["grade"]]})
        prev = entry.entry_hash
    if not entries:
        raise LearningError("no records folded into fixture calibration; skipped=" + str(skipped))
    ledger = CalibrationLedger(tuple(entries))
    ledger.validate()
    summary = summarize(ledger, calibration_key)
    return {"calibration_summary": summary.to_dict(), "calibration_ledger_digest": ledger.digest(),
            "ledger_tip": ledger.tip, "folded_count": len(entries), "skipped": skipped, "s1_entries": s1,
            "black_doctrine": black_doctrine_assess(len(entries))}


def calibrate(world: World, *, run_id: str, records: Sequence[Mapping[str, Any]], at: str,
              producer_version: str, calibration_key: str) -> dict[str, Any]:
    """NO_OUTCOME_NO_CALIBRATION. Live worlds use the real S1 seam; everything else is quarantined."""
    if not records:
        raise LearningError("calibration requires at least one outcome record")
    for r in records:
        if r["content_sha256"] not in {o["content_sha256"] for o in world.outcomes}:
            raise LearningError("calibration may only consume outcomes recorded on this world's chain")
    ledger_id = f"calibration:{world.world_id}"
    producer_id = "neuruh-sovereign-agent-starter.organism"
    pv = sha256_ref(producer_version)
    if world.world_mode == "live":
        # Real S1 seam: outcome-record derives the calibration cell from the record's case_id
        # (one key per summary) — the primitive owns the key; the caller's key is recorded as intent only.
        folded = to_017_summary(records, ledger_id=ledger_id, producer_id=producer_id, producer_version=pv,
                                calibration_key=None)
    else:
        folded = _fixture_fold(world, records, ledger_id=ledger_id, producer_id=producer_id, producer_version=pv,
                               calibration_key=calibration_key)
    rec = C.calibration_record(
        calibration_id=f"calrec-{folded['ledger_tip'][:24]}", world_id=world.world_id, run_id=run_id,
        world_mode=world.world_mode, summary=folded["calibration_summary"], ledger_digest=folded["calibration_ledger_digest"],
        ledger_tip=folded["ledger_tip"], folded_count=folded["folded_count"], skipped=folded["skipped"],
        black_doctrine=folded["black_doctrine"], created_at=at)
    world.record("calibration_recorded", {"calibration_record": rec}, observed_at=at, run_id=run_id,
                 causation_id=records[-1]["content_sha256"])
    return rec


# ------------------------------------------------------------------ learning proposal
def propose(world: World, *, run_id: str, calibration: Mapping[str, Any], target: Mapping[str, Any],
            provenance_bindings: Mapping[str, str], at: str, producer_version: str, min_sample: int = 20,
            gap_threshold: float = 0.10, brier_threshold: float = 0.20) -> dict[str, Any] | None:
    """S2: calibration summary -> 019 proposal. Returns None when there is honestly no signal."""
    C.verify(calibration)
    s2 = s2_calibration_to_learning_update(
        calibration_summary=calibration["summary"], calibration_ledger_digest=calibration["ledger_digest"],
        target=dict(target), provenance_bindings=dict(provenance_bindings), created_at=at,
        producer_version=sha256_ref(producer_version), min_sample=min_sample, gap_threshold=gap_threshold,
        brier_threshold=brier_threshold)
    if s2 is None:
        return None
    gov = to_governance_request(s2, issued_at=at, evidence_class=world.evidence_class)
    lp = C.learning_proposal(world_id=world.world_id, run_id=run_id, world_mode=world.world_mode,
                             proposal=s2["learning_update_proposal"], provenance_={**s2["provenance"], "governance_request": gov,
                                                                                    "governance_submitted": False},
                             calibration_digest=calibration["digest"], created_at=at)
    world.record("learning_proposed", {"proposal": lp}, observed_at=at, run_id=run_id, causation_id=calibration["digest"])
    return lp


def revision_proposal(world: World, *, run_id: str, learning_proposal: Mapping[str, Any], observed_state: Mapping[str, Any],
                      at: str) -> tuple[dict[str, Any], dict[str, Any]]:
    C.verify(learning_proposal)
    if learning_proposal["world_id"] != world.world_id:
        raise LearningError("CHILD_WORLD_CANNOT_MUTATE_PARENT_DIRECTLY: a proposal may only target its own world's canonical state")
    obs_digest = canonical_state_digest(observed_state)
    cur = world.canonical
    drift = sha256_ref(canonical_json({"drift": "adopt_observed", "canonical": cur["state_digest"], "observed": obs_digest}))
    crp = C.canonical_revision_proposal(
        proposal_id=f"crp-{learning_proposal['proposal']['proposal_id']}", world_id=world.world_id, run_id=run_id,
        target_id=cur["target_id"], current_canonical_stage=cur["stage"], current_canonical_state_digest=cur["state_digest"],
        observed_stage=cur["stage"], observed_state_digest=obs_digest, learning_proposal_digest=learning_proposal["digest"],
        evidence_class=world.evidence_class, created_at=at, drift_entry_digest=drift)
    world.record("revision_proposed", {"proposal": crp, "observed_state": dict(observed_state)}, observed_at=at,
                 run_id=run_id, causation_id=learning_proposal["digest"])
    return crp, dict(observed_state)


# ------------------------------------------------------------------ authorization / promotion
def authorize(world: World, *, run_id: str, crp: Mapping[str, Any], actor: Mapping[str, Any], capability: str,
              approval_digest: str | None, delegation_digest: str, reversibility_contract_digest: str,
              policy_version: str, at: str, expires_at: str) -> dict[str, Any]:
    """NO_APPROVAL_NO_CANONICAL_REVISION: a 033 contract cannot be created without a human approval digest."""
    C.verify(crp)
    C.verify(actor)
    if not approval_digest or not approval_digest.startswith("sha256:"):
        raise LearningError("canonical revision authorization requires a content-bound human approval digest")
    if actor["actor_kind"] != "human":
        raise LearningError("only a human actor can approve a canonical revision in v0.1")
    attestation = sha256_ref(canonical_json({"attestation": world.state_digest(), "world": world.world_id}))
    a = create_authorization(
        authorization_id=f"ca-{crp['proposal_id']}", run_id=run_id, action_id="canonical-revise", target_id=crp["target_id"],
        actor_id=actor["actor_id"], authority_class="canonical-state-manager", capability=capability,
        reconciliation_proposal_digest=crp["digest"], drift_entry_digest=crp["drift_entry_digest"],
        state_attestation_digest=attestation, current_canonical_lifecycle_entry_digest=world.lifecycle_anchor_digest,
        revision_mode="adopt_observed", current_canonical_stage=crp["current_canonical_stage"],
        current_canonical_state_digest=crp["current_canonical_state_digest"], observed_stage=crp["observed_stage"],
        observed_state_digest=crp["observed_state_digest"], target_canonical_stage=crp["target_canonical_stage"],
        target_canonical_state_digest=crp["target_canonical_state_digest"], approval_digest=approval_digest,
        delegation_digest=delegation_digest, reversibility_contract_digest=reversibility_contract_digest,
        policy_version=policy_version, issued_at=at, expires_at=expires_at)
    auth = a.to_dict()
    world.record("revision_authorized", {"authorization": auth, "approval_digest": approval_digest},
                 observed_at=at, run_id=run_id, causation_id=crp["digest"])
    return auth


def promote(world: World, *, run_id: str, learning_proposal: Mapping[str, Any], crp: Mapping[str, Any],
            authorization: Mapping[str, Any], requested_stage: str, min_sample_count: int, tests_passed: bool,
            test_report_digest: str | None, regression_count: int, critical_regression_count: int,
            reversibility_contract_digest: str, at: str) -> dict[str, Any]:
    p = learning_proposal["proposal"]
    C._in(requested_stage, C.STAGES, "requested_stage")
    if requested_stage != crp["target_canonical_stage"]:
        raise LearningError("promotion request stage must equal the revision's (state-only) stage")
    policy = PromotionPolicy(f"promotion:{world.world_id}", (p["target_kind"],), (requested_stage,), int(min_sample_count),
                             0, True, True, True)
    req = PromotionRequest(f"preq-{p['proposal_id']}", p["proposal_id"], p["proposal_digest"], p["target_id"], p["target_kind"],
                           p["current_version"], p["candidate_version"], p["calibration_summary_digest"], int(p["sample_count"]),
                           bool(tests_passed), test_report_digest, int(regression_count), int(critical_regression_count),
                           authorization["approval_digest"], reversibility_contract_digest, requested_stage, at)
    d = PromotionGate(policy).evaluate(req, decision_id=f"pdec-{p['proposal_id']}", decided_at=at)
    wrapper = C.promotion_decision(world_id=world.world_id, run_id=run_id, decision=d.to_dict(), requested_stage=requested_stage,
                                   evidence_class=world.evidence_class, created_at=at)
    event = {"PROMOTE": "promotion_eligible", "HOLD": "promotion_held", "BLOCK": "promotion_blocked"}[str(d.decision).upper()]
    world.record(event, {"promotion_decision": wrapper}, observed_at=at, run_id=run_id, causation_id=authorization["authorization_digest"])
    return wrapper


# ------------------------------------------------------------------ revision + effective state
def apply_revision(world: World, *, run_id: str, crp: Mapping[str, Any], authorization: Mapping[str, Any],
                   promotion: Mapping[str, Any], observed_state: Mapping[str, Any], actor_id: str,
                   started_at: str, ended_at: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """034 receipt -> 035 lineage entry -> 036 resolution. The only path that moves canonical state."""
    if str(promotion["decision"]["decision"]).upper() != "PROMOTE":
        raise LearningError("revision refused: promotion gate did not return PROMOTE")
    if promotion["stage_ceiling"] and C.STAGES.index(crp["target_canonical_stage"]) > C.STAGES.index(promotion["stage_ceiling"]):
        raise LearningError("revision refused: stage above the evidence-class ceiling")
    from neuruh_canonical_state_revision_authorization_contract import CanonicalStateRevisionAuthorization
    a = CanonicalStateRevisionAuthorization.from_mapping(authorization)
    verify_authorization(a, now=started_at, uses_so_far=0)
    if a.target_id != world.canonical["target_id"]:
        raise LearningError("CHILD_WORLD_CANNOT_MUTATE_PARENT_DIRECTLY: authorization targets another world")
    obs_digest = canonical_state_digest(observed_state)
    if obs_digest != crp["target_canonical_state_digest"]:
        raise LearningError("observed state does not hash to the proposal's target state digest")
    write_digest = sha256_ref(canonical_json({"world": world.world_id, "write": dict(observed_state)}))
    post_record = {"target_id": crp["target_id"], "stage": crp["target_canonical_stage"], "state_digest": obs_digest}
    post_record_digest = sha256_ref(canonical_json(post_record))
    verification_digest = sha256_ref(canonical_json({"post_state_digest": obs_digest, "matches_target": True}))
    r = create_receipt(
        receipt_id=f"cr-{crp['proposal_id']}", run_id=run_id, action_id="canonical-revise", target_id=crp["target_id"],
        actor_id=actor_id, canonical_revision_authorization_digest=a.authorization_digest,
        reconciliation_proposal_digest=crp["digest"], drift_entry_digest=crp["drift_entry_digest"],
        previous_canonical_lifecycle_entry_digest=world.lifecycle_anchor_digest, revision_mode="adopt_observed",
        pre_canonical_stage=crp["current_canonical_stage"], pre_canonical_state_digest=crp["current_canonical_state_digest"],
        target_canonical_stage=crp["target_canonical_stage"], target_canonical_state_digest=crp["target_canonical_state_digest"],
        canonical_store_write_digest=write_digest, post_canonical_record_digest=post_record_digest,
        post_canonical_stage=crp["target_canonical_stage"], post_canonical_state_digest=obs_digest,
        verification_digest=verification_digest, status="succeeded", started_at=started_at, ended_at=ended_at)
    receipt = r.to_dict()
    ledger = CanonicalRevisionLedger(tuple(_entry_objects(world)))
    ledger = append_revision(
        ledger, revision_id=f"rev-{crp['proposal_id']}", target_id=crp["target_id"],
        lifecycle_anchor_digest=world.lifecycle_anchor_digest, anchor_stage=world.anchor["to_stage"],
        anchor_state_digest=world.anchor["post_state_digest"], revision_authorization_digest=a.authorization_digest,
        revision_receipt_digest=r.receipt_digest, receipt_status="succeeded", receipt_revision_mode="adopt_observed",
        receipt_previous_lifecycle_entry_digest=world.lifecycle_anchor_digest,
        receipt_pre_canonical_stage=crp["current_canonical_stage"], receipt_pre_canonical_state_digest=crp["current_canonical_state_digest"],
        receipt_target_canonical_stage=crp["target_canonical_stage"], receipt_target_canonical_state_digest=crp["target_canonical_state_digest"],
        receipt_post_canonical_stage=crp["target_canonical_stage"], receipt_post_canonical_state_digest=obs_digest, recorded_at=ended_at)
    entry = ledger.entries[-1].to_dict()
    world.record("revision_recorded", {"revision_entry": entry, "post_state": dict(observed_state), "receipt": receipt},
                 observed_at=ended_at, run_id=run_id, causation_id=a.authorization_digest)
    ecs = resolve_effective(world, run_id=run_id, at=ended_at)
    return receipt, entry, ecs


def _entry_objects(world: World):
    from neuruh_canonical_state_revision_ledger import CanonicalRevisionEntry
    return [CanonicalRevisionEntry.from_mapping(e) for e in world.revisions]


def resolve_effective(world: World, *, run_id: str, at: str) -> dict[str, Any]:
    """036: what is the effective canonical state of this world now? (first consumer of resolution_digest)"""
    tips = [{"lifecycle_entry_digest": world.lifecycle_anchor_digest, "stage": world.anchor["to_stage"],
             "state_digest": world.anchor["post_state_digest"], "sequence": 0, "target_id": world.canonical["target_id"]}]
    lineages = [list(world.revisions)] if world.revisions else []
    res = resolve(target_id=world.canonical["target_id"], lifecycle_tips=tips, revision_lineages=lineages)
    ecs = C.effective_canonical_state(world_id=world.world_id, target_id=world.canonical["target_id"], resolution=res.to_dict(),
                                      created_at=at)
    world.record("effective_state_resolved", {"effective_canonical_state": ecs}, observed_at=at, run_id=run_id,
                 causation_id=res.resolution_digest)
    return ecs
