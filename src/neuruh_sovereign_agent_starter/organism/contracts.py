"""Canonical organism contracts (neuruh.organism.*.v0.1).

Thin, content-addressed envelopes that CONVERGE the existing Neuruh
primitives without renaming them. Where a mature contract already exists
(capability registry 007, policy gate 006, agent receipt 001, run manifest 009,
outcome record v1, calibration ledger 017, learning update proposal 019,
promotion gate 020, canonical revision 033/034/035, effective resolver 036)
the organism WRAPS it: the established object is carried verbatim under a
named key and the wrapper adds only the organism envelope
(world_id / run_id / actor / evidence_class / digest).

Rules enforced here, not merely documented:
  * UNKNOWN is not FALSE — tri-state facts are True | False | "unknown".
  * CONTEXT is not INTENT — ExecutionContext and Intent are distinct objects;
    an intent digest never covers context.
  * PROPOSAL is not CANONICAL — every proposal carries is_canonical=False and
    cannot be sealed otherwise.
Every envelope carries schema_version, a stable id, created_at, provenance,
correlation (run_id) and a content digest.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from neuruh_agent_run_manifest import canonical_json, sha256_ref

UNKNOWN = "unknown"

# ---- vocabularies adopted from existing organs (provenance in CONTRACT_GRAPH) ----
WORLD_MODES = ("live", "shadow", "fixture", "synthetic")          # recipe_engine.closed_loop.identity.WorldMode
PROMOTABLE_MODES = frozenset({"live"})                            # recipe_engine PROMOTABLE_MODES
EVIDENCE_CLASSES = ("fixture", "live")                            # autonomous-governance-core trust.mjs
STAGES = ("sandbox", "canary", "pilot", "production")             # Commons 026/029/033–036
AUTHORITY_CLASSES = ("A0", "A1", "A2", "A3", "A4", "A5", "A6")     # governance trust.mjs
MUTATION_CLASSES = ("read_only", "reversible_write", "persistent_write", "destructive")
RISK_TIERS = ("R0", "R1", "R2", "R3", "R4", "R5")                 # governance risk.mjs
WORLD_ENGINE_AUTHORITY_LEVELS = (                                 # neuruh-world-engine-alpha constants.py
    "L0_OBSERVE", "L1_PREPARE", "L2_PROPOSE", "L3_APPROVE_SCOPED", "L4_EXECUTE", "L5_IRREVERSIBLE")
# Subset of governance ACTION_CLASS_TIERS (risk.mjs @ fc50bd0). Unknown class => fail closed.
ACTION_CLASS_TIERS = {
    "read": "R0", "query": "R0", "health": "R0", "status": "R0", "retrieval": "R0", "git_inspect": "R0",
    "artifact_write": "R1", "report_write": "R1", "receipt_write": "R1", "temp_write": "R1", "preview_write": "R1",
    "repo_edit": "R2", "test_run": "R2", "build": "R2", "git_commit": "R2", "git_push": "R2",
    "qualified_adoption": "R3",
    "external_message": "R4", "spend": "R4", "production_write": "R4",
    "destructive": "R5", "privileged": "R5",
}
TIER_TO_WORLD_ENGINE_LEVEL = {"R0": "L0_OBSERVE", "R1": "L1_PREPARE", "R2": "L2_PROPOSE",
                              "R3": "L3_APPROVE_SCOPED", "R4": "L4_EXECUTE", "R5": "L5_IRREVERSIBLE"}
STAGE_CEILING_FOR_EVIDENCE = {"fixture": "sandbox", "live": "production"}

SCHEMA = {
    "agent_identity": "neuruh.organism.agent-identity.v0.1",
    "actor_identity": "neuruh.organism.actor-identity.v0.1",
    "world_identity": "neuruh.organism.world-identity.v0.1",
    "intent": "neuruh.organism.intent.v0.1",
    "capability_grant": "neuruh.organism.capability-grant.v0.1",
    "policy_decision": "neuruh.organism.policy-decision.v0.1",
    "authority_decision": "neuruh.organism.authority-decision.v0.1",
    "action_request": "neuruh.organism.action-request.v0.1",
    "execution_context": "neuruh.organism.execution-context.v0.1",
    "evidence_reference": "neuruh.organism.evidence-reference.v0.1",
    "calibration_record": "neuruh.organism.calibration-record.v0.1",
    "learning_proposal": "neuruh.organism.learning-proposal.v0.1",
    "canonical_revision_proposal": "neuruh.organism.canonical-revision-proposal.v0.1",
    "promotion_decision": "neuruh.organism.promotion-decision.v0.1",
    "effective_canonical_state": "neuruh.organism.effective-canonical-state.v0.1",
    "replay_receipt": "neuruh.organism.replay-receipt.v0.1",
    "world_seed_spec": "neuruh.organism.world-seed-spec.v0.1",
    "world_manifest": "neuruh.organism.world-manifest.v0.1",
    "world_snapshot": "neuruh.organism.world-snapshot.v0.1",
    "world_branch": "neuruh.organism.world-branch.v0.1",
    "world_event": "neuruh.organism.world-event.v0.1",
    "memory_namespace": "neuruh.organism.memory-namespace.v0.1",
    "product_world_adapter": "neuruh.organism.product-world-adapter.v0.1",
}
# Established contracts carried verbatim (never renamed).
ESTABLISHED = {
    "capability": "neuruh.capability-registry.v0.1",
    "policy_record": "policy-gate DecisionRecord (neuruh-policy-gate 006)",
    "execution_receipt": "neuruh.agent-receipt.v1alpha1",
    "run_manifest": "neuruh.agent-run-manifest.v0.1",
    "outcome_record": "neuruh.outcome-record.v1",
    "calibration_entry": "neuruh.outcome-calibration-ledger.v0.1",
    "learning_update_proposal": "neuruh.learning-update-proposal.v0.1",
    "promotion": "neuruh.promotion-gate.v0.1",
    "canonical_revision_authorization": "neuruh.canonical-state-revision-authorization-contract.v0.1",
    "canonical_revision_receipt": "neuruh.canonical-state-revision-receipt.v0.1",
    "canonical_revision_ledger": "neuruh.canonical-state-revision-ledger.v0.1",
    "effective_resolution": "neuruh.effective-canonical-state-resolver.v0.1",
    "governance_request": "gov.decision.request.v1",
    "closed_loop_event": "neuruh.closed-loop.event.v1",
}


class ContractError(ValueError):
    """Fail-closed refusal for a malformed or dishonest contract object."""


def _s(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be a non-empty string")
    return value


def _in(value: Any, allowed: Sequence[str], name: str) -> str:
    if value not in allowed:
        raise ContractError(f"{name} must be one of {list(allowed)}; got {value!r}")
    return value


def tri(value: Any, name: str) -> bool | str:
    """Validate a tri-state fact. Only True, False or the literal "unknown"."""
    if value is True or value is False or value == UNKNOWN:
        return value
    raise ContractError(f"{name} must be True, False or 'unknown' — not {value!r}")


def seal(kind: str, body: Mapping[str, Any], *, id_field: str) -> dict[str, Any]:
    """Stamp schema_version + digest; refuse envelopes missing id/created_at."""
    if kind not in SCHEMA:
        raise ContractError(f"unknown contract kind {kind!r}")
    if "digest" in body:
        raise ContractError("body must not carry a digest before sealing")
    out = {"schema_version": SCHEMA[kind], **dict(body)}
    _s(out.get(id_field), id_field)
    _s(out.get("created_at"), "created_at")
    if "is_canonical" in out and out["is_canonical"] is not False:
        raise ContractError("a proposal cannot be sealed as canonical (PROPOSAL_IS_NOT_CANONICAL)")
    out["digest"] = sha256_ref(canonical_json(out))
    return out


def verify(obj: Mapping[str, Any]) -> bool:
    body = {k: v for k, v in obj.items() if k != "digest"}
    if obj.get("digest") != sha256_ref(canonical_json(body)):
        raise ContractError("digest mismatch")
    if obj.get("schema_version") not in SCHEMA.values():
        raise ContractError("unknown organism schema_version")
    return True


def provenance(source: str, **extra: Any) -> dict[str, Any]:
    return {"source": _s(source, "provenance.source"), **extra}


# ------------------------------------------------------------------ identities
def agent_identity(*, agent_id: str, world_id: str, roles: Sequence[str], created_at: str,
                   creator: str, provenance_: Mapping[str, Any]) -> dict[str, Any]:
    return seal("agent_identity", {
        "agent_id": _s(agent_id, "agent_id"), "world_id": _s(world_id, "world_id"), "kind": "agent",
        "roles": [str(r) for r in roles], "created_at": created_at, "creator": _s(creator, "creator"),
        "provenance": dict(provenance_),
    }, id_field="agent_id")


def actor_identity(*, actor_id: str, actor_kind: str, authority_class: str, created_at: str,
                   source_sha: str | None = None) -> dict[str, Any]:
    _in(actor_kind, ("human", "agent", "service", "runtime"), "actor_kind")
    _in(authority_class, AUTHORITY_CLASSES, "authority_class")
    return seal("actor_identity", {
        "actor_id": _s(actor_id, "actor_id"), "actor_kind": actor_kind,
        "authority_class": authority_class, "source_sha": source_sha, "created_at": created_at,
    }, id_field="actor_id")


def world_identity(*, world_id: str, world_type: str, world_mode: str, seed_id: str, seed_version: str,
                   created_at: str, creator: str, parent_world_id: str | None = None,
                   lineage: Sequence[str] = ()) -> dict[str, Any]:
    _in(world_mode, WORLD_MODES, "world_mode")
    return seal("world_identity", {
        "world_id": _s(world_id, "world_id"), "world_type": _s(world_type, "world_type"),
        "world_mode": world_mode, "parent_world_id": parent_world_id, "lineage": list(lineage),
        "seed_id": _s(seed_id, "seed_id"), "seed_version": _s(seed_version, "seed_version"),
        "created_at": created_at, "creator": _s(creator, "creator"),
    }, id_field="world_id")


# ------------------------------------------------------------------ intent / context
def intent(*, intent_id: str, world_id: str, agent_id: str, run_id: str, objective: str,
           requested_operation: str, args: Mapping[str, Any], created_at: str,
           source: str, evidence_refs: Sequence[str] = ()) -> dict[str, Any]:
    """An intent names WHAT the agent wants. It never carries context."""
    return seal("intent", {
        "intent_id": _s(intent_id, "intent_id"), "world_id": world_id, "agent_id": agent_id,
        "run_id": _s(run_id, "run_id"), "objective": _s(objective, "objective"),
        "requested_operation": _s(requested_operation, "requested_operation"),
        "args": dict(args), "evidence_refs": list(evidence_refs), "created_at": created_at,
        "provenance": provenance(source), "is_context": False,
    }, id_field="intent_id")


def execution_context(*, context_id: str, world_id: str, run_id: str, sandbox_root: str,
                      memory_namespace: str, evidence_namespace: str, created_at: str,
                      environment_allowlist: Sequence[str] = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL"),
                      connectors: Sequence[Mapping[str, Any]] = (), notes: str = "") -> dict[str, Any]:
    """Context describes WHERE/HOW a run happens. It is never an intent."""
    return seal("execution_context", {
        "context_id": _s(context_id, "context_id"), "world_id": world_id, "run_id": run_id,
        "sandbox_root": _s(sandbox_root, "sandbox_root"), "memory_namespace": memory_namespace,
        "evidence_namespace": evidence_namespace, "environment_allowlist": list(environment_allowlist),
        "connectors": [dict(c) for c in connectors], "notes": notes, "created_at": created_at,
        "is_intent": False,
    }, id_field="context_id")


# ------------------------------------------------------------------ capability grant
DEFAULT_HARD_FLOORS = {"production_write": False, "external_contact": False, "destructive": False}


def capability_grant(*, grant_id: str, world_id: str, issuer: str, subject: str,
                     operations: Sequence[str], forbidden_operations: Sequence[str], max_spend_usd: float,
                     issued_at: str, expires_at: str, evidence_class_ceiling: str, stage_ceiling: str,
                     created_at: str, derived_from_grant: str | None = None) -> dict[str, Any]:
    """Bounded, expiring, non-transferable capability grant (modelled on gov.grant.v1
    FounderGrant). Hard floors are hard-coded false: no grant can carry production
    write, external contact or destructive permission."""
    _in(evidence_class_ceiling, EVIDENCE_CLASSES, "evidence_class_ceiling")
    _in(stage_ceiling, STAGES, "stage_ceiling")
    ops = sorted({_s(o, "operation") for o in operations})
    forb = sorted({_s(o, "forbidden_operation") for o in forbidden_operations})
    if set(ops) & set(forb):
        raise ContractError("an operation cannot be both granted and forbidden")
    if float(max_spend_usd) < 0:
        raise ContractError("max_spend_usd cannot be negative")
    if not (issued_at < expires_at):
        raise ContractError("grant must expire after it is issued")
    return seal("capability_grant", {
        "grant_id": _s(grant_id, "grant_id"), "world_id": world_id, "issuer": _s(issuer, "issuer"),
        "subject": _s(subject, "subject"), "operations": ops, "forbidden_operations": forb,
        "max_spend_usd": float(max_spend_usd), "issued_at": issued_at, "expires_at": expires_at,
        "evidence_class_ceiling": evidence_class_ceiling, "stage_ceiling": stage_ceiling,
        "hard_floors": dict(DEFAULT_HARD_FLOORS), "transferable": False,
        "derived_from_grant": derived_from_grant, "created_at": created_at,
    }, id_field="grant_id")


# ------------------------------------------------------------------ decisions / actions
def policy_decision(*, world_id: str, run_id: str, intent_id: str, record: Mapping[str, Any],
                    decided_at: str) -> dict[str, Any]:
    """Wrap a policy-gate DecisionRecord verbatim."""
    for k in ("action_id", "decision", "policy_id", "policy_version", "reasons"):
        if k not in record:
            raise ContractError(f"policy record missing {k}")
    _in(record["decision"], ("allow", "deny", "escalate"), "record.decision")
    return seal("policy_decision", {
        "policy_decision_id": f"pd-{sha256_ref(canonical_json(dict(record)))[7:31]}",
        "world_id": world_id, "run_id": run_id, "intent_id": intent_id,
        "record": dict(record), "created_at": decided_at,
    }, id_field="policy_decision_id")


def action_request(*, action_id: str, world_id: str, run_id: str, agent_id: str, intent_id: str,
                   authority_digest: str, operation: str, args: Mapping[str, Any],
                   execution_binding: Mapping[str, Any], created_at: str) -> dict[str, Any]:
    for k in ("bin", "argv", "cwd"):
        if k not in execution_binding:
            raise ContractError(f"execution_binding missing {k}")
    if not authority_digest.startswith("sha256:"):
        raise ContractError("action request requires an authority decision digest (NO_AUTHORITY_NO_ACTION)")
    return seal("action_request", {
        "action_id": _s(action_id, "action_id"), "world_id": world_id, "run_id": run_id,
        "agent_id": agent_id, "intent_id": intent_id, "authority_digest": authority_digest,
        "operation": operation, "args": dict(args),
        "execution_binding": {"bin": execution_binding["bin"], "argv": list(execution_binding["argv"]),
                              "cwd": execution_binding["cwd"]},
        "created_at": created_at,
    }, id_field="action_id")


def evidence_reference(*, evidence_id: str, world_id: str, source_type: str, pointer: str,
                       observed_at: str, content_digest: str, state: str = "observed",
                       visibility: str = "INTERNAL") -> dict[str, Any]:
    """recipe_engine EvidenceRef field names + 009 `state` + world scope."""
    if len(content_digest) != 64 or any(c not in "0123456789abcdef" for c in content_digest):
        raise ContractError("content_digest must be a bare lowercase sha256 hex")
    _in(state, ("observed", "derived", "claimed"), "state")
    return seal("evidence_reference", {
        "evidence_id": _s(evidence_id, "evidence_id"), "world_id": world_id,
        "source_type": _s(source_type, "source_type"), "pointer": _s(pointer, "pointer"),
        "observed_at": observed_at, "content_digest": content_digest, "state": state,
        "visibility": visibility, "created_at": observed_at,
    }, id_field="evidence_id")


# ------------------------------------------------------------------ learning chain wrappers
def calibration_record(*, calibration_id: str, world_id: str, run_id: str, world_mode: str,
                       summary: Mapping[str, Any], ledger_digest: str, ledger_tip: str, folded_count: int,
                       skipped: Sequence[Mapping[str, Any]], black_doctrine: Mapping[str, Any],
                       created_at: str) -> dict[str, Any]:
    _in(world_mode, WORLD_MODES, "world_mode")
    evidence_class = "live" if world_mode == "live" else "fixture"
    return seal("calibration_record", {
        "calibration_id": _s(calibration_id, "calibration_id"), "world_id": world_id, "run_id": run_id,
        "world_mode": world_mode, "evidence_class": evidence_class,
        "quarantine": None if world_mode == "live" else f"{world_mode.upper()}_WORLD",
        "summary": dict(summary), "ledger_digest": ledger_digest, "ledger_tip": ledger_tip,
        "folded_count": int(folded_count), "skipped": [dict(s) for s in skipped],
        "black_doctrine": dict(black_doctrine), "authority": "NONE", "created_at": created_at,
    }, id_field="calibration_id")


def learning_proposal(*, world_id: str, run_id: str, world_mode: str, proposal: Mapping[str, Any],
                      provenance_: Mapping[str, Any], calibration_digest: str, created_at: str) -> dict[str, Any]:
    _in(world_mode, WORLD_MODES, "world_mode")
    if proposal.get("schema_version") != ESTABLISHED["learning_update_proposal"]:
        raise ContractError("learning proposal must wrap a 019 learning update proposal")
    evidence_class = "live" if world_mode == "live" else "fixture"
    return seal("learning_proposal", {
        "learning_proposal_id": f"lp-{proposal['proposal_id']}", "world_id": world_id, "run_id": run_id,
        "world_mode": world_mode, "evidence_class": evidence_class,
        "promotion_ceiling_stage": STAGE_CEILING_FOR_EVIDENCE[evidence_class],
        "proposal": dict(proposal), "provenance": dict(provenance_),
        "calibration_digest": calibration_digest, "is_canonical": False, "authority": "NONE",
        "created_at": created_at,
    }, id_field="learning_proposal_id")


def canonical_revision_proposal(*, proposal_id: str, world_id: str, run_id: str, target_id: str,
                                current_canonical_stage: str, current_canonical_state_digest: str,
                                observed_stage: str, observed_state_digest: str,
                                learning_proposal_digest: str, evidence_class: str, created_at: str,
                                drift_entry_digest: str | None = None) -> dict[str, Any]:
    """030-shaped adopt_observed proposal (state-only: stage may not change)."""
    _in(current_canonical_stage, STAGES, "current_canonical_stage")
    _in(observed_stage, STAGES, "observed_stage")
    _in(evidence_class, EVIDENCE_CLASSES, "evidence_class")
    if observed_stage != current_canonical_stage:
        raise ContractError("canonical revision is state-only; a stage change needs the lifecycle path")
    return seal("canonical_revision_proposal", {
        "proposal_id": _s(proposal_id, "proposal_id"), "world_id": world_id, "run_id": run_id,
        "target_id": _s(target_id, "target_id"), "revision_mode": "adopt_observed",
        "current_canonical_stage": current_canonical_stage,
        "current_canonical_state_digest": current_canonical_state_digest,
        "observed_stage": observed_stage, "observed_state_digest": observed_state_digest,
        "target_canonical_stage": current_canonical_stage,
        "target_canonical_state_digest": observed_state_digest,
        "drift_entry_digest": drift_entry_digest, "learning_proposal_digest": learning_proposal_digest,
        "evidence_class": evidence_class, "is_canonical": False, "authority": "NONE",
        "created_at": created_at,
    }, id_field="proposal_id")


def promotion_decision(*, world_id: str, run_id: str, decision: Mapping[str, Any], requested_stage: str,
                       evidence_class: str, created_at: str) -> dict[str, Any]:
    _in(evidence_class, EVIDENCE_CLASSES, "evidence_class")
    _in(requested_stage, STAGES, "requested_stage")
    ceiling = STAGE_CEILING_FOR_EVIDENCE[evidence_class]
    if STAGES.index(requested_stage) > STAGES.index(ceiling):
        raise ContractError(f"{evidence_class} evidence cannot request stage {requested_stage} (ceiling {ceiling})")
    for k in ("decision_id", "decision", "promotion_digest"):
        if k not in decision:
            raise ContractError(f"promotion decision missing {k}")
    return seal("promotion_decision", {
        "promotion_decision_id": f"wpd-{decision['decision_id']}", "world_id": world_id, "run_id": run_id,
        "requested_stage": requested_stage, "evidence_class": evidence_class, "stage_ceiling": ceiling,
        "decision": dict(decision), "deployment_authority": False, "created_at": created_at,
    }, id_field="promotion_decision_id")


def effective_canonical_state(*, world_id: str, target_id: str, resolution: Mapping[str, Any],
                              created_at: str) -> dict[str, Any]:
    for k in ("resolution_digest", "resolution_status"):
        if k not in resolution:
            raise ContractError(f"resolution missing {k}")
    return seal("effective_canonical_state", {
        "effective_state_id": f"ecs-{resolution['resolution_digest'][7:31]}", "world_id": world_id,
        "target_id": target_id, "status": resolution["resolution_status"], "reason_code": resolution.get("reason_code"),
        "effective_stage": resolution.get("effective_stage"),
        "effective_state_digest": resolution.get("effective_state_digest"),
        "effective_source": resolution.get("effective_source"),
        "resolution": dict(resolution), "candidate": True, "authority": "NONE", "created_at": created_at,
    }, id_field="effective_state_id")


def replay_receipt(*, replay_id: str, world_id: str, seed_digest: str, receipts_tip: str, event_count: int,
                   replayed_state_digest: str, expected_state_digest: str, gaps: Sequence[str],
                   created_at: str) -> dict[str, Any]:
    return seal("replay_receipt", {
        "replay_id": _s(replay_id, "replay_id"), "world_id": world_id, "seed_digest": seed_digest,
        "receipts_tip": receipts_tip, "event_count": int(event_count),
        "replayed_state_digest": replayed_state_digest, "expected_state_digest": expected_state_digest,
        "match": replayed_state_digest == expected_state_digest, "gaps": list(gaps),
        "authority": "NONE", "created_at": created_at,
    }, id_field="replay_id")


# ------------------------------------------------------------------ the contract graph
def contract_graph() -> dict[str, Any]:
    """Machine-readable graph: every organism contract, its home, disposition and edges."""
    n = {}

    def node(name, schema, home, disposition, produced_by, consumed_by, notes=""):
        n[name] = {"schema_version": schema, "home": home, "disposition": disposition,
                   "produced_by": produced_by, "consumed_by": consumed_by, "notes": notes}

    node("AgentIdentity", SCHEMA["agent_identity"], "organism (new envelope)", "NEW_WRAPPER",
         ["World.register_agent"], ["Intent", "CapabilityGrant", "AuthorityDecision"],
         "agent_id also feeds run manifest actor_id (009)")
    node("ActorIdentity", SCHEMA["actor_identity"], "organism; authority_class from governance trust.mjs",
         "ADAPT", ["World.instantiate"], ["CapabilityGrant.issuer", "033 actor_id"])
    node("WorldIdentity", SCHEMA["world_identity"], "organism; world_mode from recipe_engine WorldMode",
         "MERGE_CONTRACT", ["seeder.instantiate"], ["everything"],
         "converges cockpit world-registry.js entries + EventIdentity.world + T44 World Pack world_id")
    node("Intent", SCHEMA["intent"], "organism", "NEW_WRAPPER", ["agent"], ["AuthorityDecision", "ActionRequest"],
         "distinct from ExecutionContext by construction")
    node("Capability", ESTABLISHED["capability"], "neuruh-capability-registry (007)", "KEEP",
         ["WorldSeedSpec.capability_manifest"], ["AuthorityDecision.capability_registered"])
    node("CapabilityGrant", SCHEMA["capability_grant"], "organism; modelled on governance gov.grant.v1",
         "ADAPT", ["World.grant"], ["AuthorityDecision.capability_granted"])
    node("PolicyDecision", SCHEMA["policy_decision"] + " wrapping " + ESTABLISHED["policy_record"],
         "neuruh-policy-gate (006)", "WRAP", ["PolicyGate.evaluate"], ["AuthorityDecision.policy_allows"])
    node("AuthorityDecision", SCHEMA["authority_decision"],
         "organism; projects gov.decision.request.v1 for autonomous-governance-core", "NEW_WRAPPER",
         ["authority.decide"], ["ActionRequest", "governed exec gate"],
         "six separate facts: tool_exists, capability_registered, capability_granted, policy_allows, authority_present, action_executed")
    node("ActionRequest", SCHEMA["action_request"], "organism; projects AXON TaskRequest", "ADAPT",
         ["lifecycle"], ["neuruh-governed-exec (005)"])
    node("ExecutionContext", SCHEMA["execution_context"], "organism", "NEW_WRAPPER", ["lifecycle"], ["governed exec"],
         "never an intent")
    node("ExecutionReceipt", ESTABLISHED["execution_receipt"], "agent-receipt (001)", "KEEP",
         ["lifecycle"], ["OutcomeRecord.run_receipt_digest", "WorldSnapshot", "Replay"])
    node("EvidenceReference", SCHEMA["evidence_reference"], "recipe_engine EvidenceRef names + 009 state",
         "MERGE_CONTRACT", ["lifecycle"], ["OutcomeRecord.evidence_refs", "WorldSnapshot"])
    node("OutcomeRecord", ESTABLISHED["outcome_record"], "neuruh-outcome-record", "KEEP",
         ["lifecycle.observe_outcome"], ["CalibrationRecord"], "AUTHORITY=NONE; synthetic never calibration_eligible")
    node("CalibrationRecord", SCHEMA["calibration_record"] + " wrapping " + ESTABLISHED["calibration_entry"],
         "neuruh-outcome-calibration-ledger (017) via outcome-record S1", "WRAP",
         ["learning.calibrate"], ["LearningProposal"], "fixture-mode fold is quarantined; live uses real S1")
    node("LearningProposal", SCHEMA["learning_proposal"] + " wrapping " + ESTABLISHED["learning_update_proposal"],
         "neuruh-learning-update-proposal (019) via outcome-record S2", "WRAP",
         ["learning.propose"], ["CanonicalRevisionProposal", "governance request"], "is_canonical=False always")
    node("CanonicalRevisionProposal", SCHEMA["canonical_revision_proposal"],
         "organism; 030 reconciliation-proposal shape (030 custody: wave16 deps only)", "ADAPT",
         ["learning.revision_proposal"], ["033"])
    node("CanonicalRevisionAuthorization", ESTABLISHED["canonical_revision_authorization"],
         "neuruh-canonical-state-revision-authorization-contract (033)", "KEEP", ["learning.authorize"], ["020", "034"])
    node("CanonicalRevisionReceipt", ESTABLISHED["canonical_revision_receipt"],
         "neuruh-canonical-state-revision-receipt (034)", "KEEP", ["learning.apply_revision"], ["035"])
    node("PromotionDecision", SCHEMA["promotion_decision"] + " wrapping " + ESTABLISHED["promotion"],
         "neuruh-promotion-gate (020)", "WRAP", ["learning.promote"], ["034 gate"],
         "fixture evidence ceiling = sandbox")
    node("EffectiveCanonicalState", SCHEMA["effective_canonical_state"] + " wrapping " + ESTABLISHED["effective_resolution"],
         "neuruh-effective-canonical-state-resolver (036) over 035 lineage", "WRAP",
         ["learning.resolve"], ["World.canonical_state", "WorldSnapshot"], "first consumer of 036 resolution_digest")
    node("ReplayReceipt", SCHEMA["replay_receipt"], "organism", "NEW_WRAPPER", ["world.replay"], ["lock", "courts"])
    node("WorldSeedSpec", SCHEMA["world_seed_spec"], "organism; genome fields from neuruh-world-engine-alpha + T44 World Pack",
         "MERGE_CONTRACT", ["operator"], ["World.instantiate"])
    node("WorldManifest", SCHEMA["world_manifest"], "organism", "NEW_WRAPPER", ["World.instantiate"], ["all"])
    node("WorldSnapshot", SCHEMA["world_snapshot"], "organism", "NEW_WRAPPER", ["World.snapshot"], ["fork", "replay"])
    node("WorldBranch", SCHEMA["world_branch"], "organism", "NEW_WRAPPER", ["World.fork"], ["lineage"])
    node("WorldEvent", SCHEMA["world_event"] + " over " + ESTABLISHED["execution_receipt"],
         "agent-receipt chain; event_type vocabulary = T24D EVENT_GRAMMAR + organism extension", "MERGE_CONTRACT",
         ["World.record"], ["replay", "projection"])
    node("MemoryNamespace", SCHEMA["memory_namespace"], "organism", "NEW_WRAPPER", ["World.instantiate"], ["storage contracts"])
    node("ProductWorldAdapter", SCHEMA["product_world_adapter"], "organism", "NEW_WRAPPER", ["product owners"], ["WorldSeedSpec"])
    node("GovernanceRequest", ESTABLISHED["governance_request"], "autonomous-governance-core (live :8848)", "ADAPT",
         ["AuthorityDecision.governance_request"], ["live governance organ (not called in courts)"])
    edges = []
    for name, meta in n.items():
        for c in meta["consumed_by"]:
            edges.append({"from": name, "to": c})
    return {"schema_version": "neuruh.organism.contract-graph.v0.1", "nodes": n, "edges": edges,
            "vocabularies": {"world_modes": WORLD_MODES, "evidence_classes": EVIDENCE_CLASSES, "stages": STAGES,
                             "authority_classes": AUTHORITY_CLASSES, "risk_tiers": RISK_TIERS,
                             "mutation_classes": MUTATION_CLASSES,
                             "world_engine_authority_levels": WORLD_ENGINE_AUTHORITY_LEVELS,
                             "action_class_tiers": ACTION_CLASS_TIERS,
                             "stage_ceiling_for_evidence": STAGE_CEILING_FOR_EVIDENCE},
            "invariants": ["NO_AUTHORITY_NO_ACTION", "NO_ACTION_NO_RECEIPT", "NO_RECEIPT_NO_OUTCOME_CLAIM",
                           "NO_OUTCOME_NO_CALIBRATION", "NO_APPROVAL_NO_CANONICAL_REVISION",
                           "CHILD_WORLD_CANNOT_MUTATE_PARENT_DIRECTLY", "UNKNOWN_IS_NOT_FALSE",
                           "PROPOSAL_IS_NOT_CANONICAL", "CONTEXT_IS_NOT_INTENT", "TOOL_EXISTENCE_IS_NOT_AUTHORITY",
                           "SAME_SEED_SAME_FIXTURE_SAME_INITIAL_HASH", "REPLAY_RECONSTRUCTS_EFFECTIVE_STATE"]}
