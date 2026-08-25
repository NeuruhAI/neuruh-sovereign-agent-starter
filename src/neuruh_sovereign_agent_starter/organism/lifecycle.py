"""One governed agent turn inside a World:

    INTENT -> CAPABILITY REQUEST -> CAPABILITY REGISTRY -> POLICY GATE -> AUTHORITY DECISION
           -> GOVERNED EXEC -> EXECUTION RECEIPT (+ evidence) -> RUN MANIFEST

Composed from the Public Commons primitives the starter already pins
(007 registry, 006 policy gate, 005 governed exec, 001 receipts, 009 manifest)
plus the organism's authority model. Execution is impossible without a granted,
unexpired, unconsumed AuthorityDecision (NO_AUTHORITY_NO_ACTION) and every
execution leaves a chained receipt before anything is returned (NO_ACTION_NO_RECEIPT).
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence

from neuruh_agent_run_manifest import (
    ArtifactRef, ComponentRef, DecisionRef, EvidenceRef, ExecutionRef, InferenceRef, PolicyRef, ReceiptRef,
    RunManifest, canonical_json, sha256_ref,
)
from neuruh_governed_exec import CommandAllowlist, CommandSpec, GovernedExecutor, WorktreeGuard
from neuruh_policy_gate import Action, PolicyGate

from . import authority as A
from . import contracts as C
from .world import World

COMPONENT_DISTRIBUTIONS = (
    "neuruh-agent-run-manifest", "neuruh-agent-receipt", "neuruh-governed-exec", "neuruh-policy-gate",
    "neuruh-capability-registry", "neuruh-inference-health", "neuruh-outcome-record",
    "neuruh-outcome-calibration-ledger", "neuruh-learning-update-proposal", "neuruh-promotion-gate",
    "neuruh-canonical-state-revision-authorization-contract", "neuruh-canonical-state-revision-receipt",
    "neuruh-canonical-state-revision-ledger", "neuruh-effective-canonical-state-resolver",
    "neuruh-sovereign-agent-starter",
)


def _component_version(name: str) -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version
        return version(name)
    except Exception:  # noqa: BLE001 - running from source trees is the expected mode here
        return "source"


class LifecycleError(C.ContractError):
    pass


@dataclass(frozen=True)
class Turn:
    world_id: str
    agent_id: str
    run_id: str
    intent: dict[str, Any]
    context: dict[str, Any]
    authority: dict[str, Any]
    action: dict[str, Any]
    decision_receipt: dict[str, Any]
    execution_receipt: dict[str, Any]
    evidence: tuple[dict[str, Any], ...]
    manifest: RunManifest
    status: str


# ------------------------------------------------------------------ steps
def request_capability(world: World, *, agent_id: str, run_id: str, objective: str, operation: str,
                       args: Mapping[str, Any], at: str, evidence_refs: Sequence[str] = ()) -> dict[str, Any]:
    if agent_id not in world.agents:
        raise LifecycleError(f"agent {agent_id!r} is not registered in world {world.world_id!r}")
    it = C.intent(intent_id=f"intent-{sha256(f'{run_id}|{operation}|{canonical_json(dict(args))}'.encode()).hexdigest()[:24]}",
                  world_id=world.world_id, agent_id=agent_id, run_id=run_id, objective=objective,
                  requested_operation=operation, args=args, created_at=at, source=f"agent:{agent_id}",
                  evidence_refs=evidence_refs)
    world.record("intent_created", {"intent": it}, observed_at=at, run_id=run_id, causation_id=agent_id)
    return it


def evaluate_policy(world: World, *, run_id: str, intent: Mapping[str, Any], domain: str, tags: Sequence[str],
                    spend: float, at: str) -> dict[str, Any]:
    """006 policy gate over the intent. Evaluates; never executes."""
    C.verify(intent)
    record = PolicyGate(world.policy()).evaluate(
        Action.create(intent["intent_id"], domain, intent["requested_operation"], tags=tags, spend=spend)).to_dict()
    pd = C.policy_decision(world_id=world.world_id, run_id=run_id, intent_id=intent["intent_id"], record=record, decided_at=at)
    world.record("decision_proposed", {"policy_decision": pd, "domain": domain, "tags": list(tags), "spend": float(spend)},
                 observed_at=at, run_id=run_id, causation_id=intent["intent_id"])
    return pd


def decide_authority(world: World, *, run_id: str, agent_id: str, intent: Mapping[str, Any],
                     policy_decision: Mapping[str, Any], grant: Mapping[str, Any] | None, tool: str | None,
                     at: str, expires_at: str, actor_authority_class: str, spend_usd: float, source_sha: str,
                     target: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Authority is a separate fact from policy, registry and grant. Returns (decision, receipt)."""
    C.verify(policy_decision)
    action_class = world.seed["action_class_map"].get(intent["requested_operation"])
    decision = A.decide(world_id=world.world_id, run_id=run_id, agent_id=agent_id, intent=intent, registry=world.registry(),
                        policy_record=policy_decision["record"], grant=grant, tools_available=world.tools_available, tool=tool,
                        action_class=action_class, actor_authority_class=actor_authority_class, spend_usd=spend_usd, at=at,
                        expires_at=expires_at, evidence_class=world.evidence_class, source_sha=source_sha, target=target)
    event = "authority_granted" if decision["decision"] == "granted" else "authority_denied"
    receipt = world.record(event, {"authority_decision": decision}, observed_at=at, run_id=run_id,
                           causation_id=policy_decision["digest"])
    return decision, receipt


def seal_forecast(world: World, *, run_id: str, intent: Mapping[str, Any], metric_id: str, probability: float,
                  at: str) -> dict[str, Any]:
    """A pre-outcome forecast, sealed on the chain BEFORE execution (calibration needs recorded_at < observed_at)."""
    body = {"forecast_version": "organism-fc-v0.1", "metric_id": metric_id, "probability": float(probability),
            "recorded_at": at, "intent_digest": intent["digest"]}
    fd = sha256(canonical_json(body).encode("utf-8")).hexdigest()
    forecast = {"forecast_digest": fd, "forecast_version": body["forecast_version"],
                "predicted": [{"metric_id": metric_id, "scale": "unit", "unit": "prob", "value": str(float(probability))}],
                "probability": float(probability), "recorded_at": at}
    world.record("forecast_sealed", {"forecast": forecast}, observed_at=at, run_id=run_id, causation_id=intent["intent_id"])
    return forecast


def execute(world: World, *, run_id: str, agent_id: str, intent: Mapping[str, Any], authority: Mapping[str, Any],
            context: Mapping[str, Any], execution_binding: Mapping[str, Any], started_at: str, ended_at: str,
            evidence_paths: Sequence[str] = (), dry_run: bool = False) -> Turn:
    """Governed execution of the exact predeclared tuple. Refuses without usable authority."""
    C.verify(context)
    if context["world_id"] != world.world_id or context["run_id"] != run_id:
        raise LifecycleError("execution context belongs to another world/run")
    A.assert_usable(authority, at=started_at, uses_so_far=world.authority_uses.get(authority["authority_id"], 0))
    if authority["intent_digest"] != intent["digest"]:
        raise LifecycleError("authority was granted for a different intent")
    action = C.action_request(action_id=f"action-{authority['nonce'][:16]}", world_id=world.world_id, run_id=run_id,
                              agent_id=agent_id, intent_id=intent["intent_id"], authority_digest=authority["digest"],
                              operation=intent["requested_operation"], args=intent["args"],
                              execution_binding=execution_binding, created_at=started_at)
    world.record("action_intent_created", {"action_request": action}, observed_at=started_at, run_id=run_id,
                 causation_id=authority["authority_id"])
    # The binding's cwd is declared RELATIVE to the context sandbox root, so receipts are
    # location-independent (same seed + same fixtures => byte-identical chains anywhere).
    if Path(execution_binding["cwd"]).is_absolute():
        raise LifecycleError("execution_binding.cwd must be relative to the execution context sandbox_root")
    allowlist = CommandAllowlist([CommandSpec.from_parts(execution_binding["bin"], execution_binding["argv"])])
    guard = WorktreeGuard([context["sandbox_root"]])
    result = GovernedExecutor(allowlist, guard).run(execution_binding["bin"], execution_binding["argv"],
                                                    cwd=str(Path(context["sandbox_root"]) / execution_binding["cwd"]), dry_run=dry_run)
    payload = {
        "action_id": action["action_id"], "authority_id": authority["authority_id"], "operation": action["operation"],
        "code": result.code, "returncode": result.returncode, "ok": result.ok,
        "stdout_sha256": sha256_ref(result.stdout), "stderr_sha256": sha256_ref(result.stderr), "dry_run": bool(dry_run),
        "governance_decision_sha256": authority["digest"], "bin": result.bin, "argv": list(result.args), "cwd": execution_binding["cwd"],
    }
    exec_receipt = world.record("action_executed" if result.ok else "action_failed", payload, observed_at=ended_at,
                                run_id=run_id, causation_id=action["action_id"])
    evidence: list[dict[str, Any]] = []
    if result.ok and not dry_run:
        for rel in evidence_paths:
            p = Path(context["sandbox_root"]) / rel
            if not p.is_file():
                raise LifecycleError(f"declared evidence path missing after execution: {rel}")
            ref = C.evidence_reference(evidence_id=f"ev-{action['action_id']}-{sha256(rel.encode()).hexdigest()[:8]}",
                                       world_id=world.world_id, source_type="sandbox_file", pointer=rel,
                                       observed_at=ended_at, content_digest=sha256(p.read_bytes()).hexdigest())
            world.record("evidence_recorded", {"evidence": ref, "action_id": action["action_id"]}, observed_at=ended_at,
                         run_id=run_id, causation_id=exec_receipt["entry_hash"])
            evidence.append(ref)
    decision_receipt = next(r for r in world.receipts if r["correlation_id"] == run_id and r["receipt_type"] == "decision"
                            and r["payload"]["event_type"] == "authority_granted")
    status = "dry_run" if dry_run and result.ok else ("completed" if result.ok else "failed")
    manifest = _manifest(world, run_id=run_id, agent_id=agent_id, intent=intent, authority=authority, action=action,
                         exec_receipt=exec_receipt, evidence=evidence, result_code=result.code, status=status,
                         started_at=started_at, ended_at=ended_at, stdout_sha=payload["stdout_sha256"])
    return Turn(world.world_id, agent_id, run_id, dict(intent), dict(context), dict(authority), action, decision_receipt,
                exec_receipt, tuple(evidence), manifest, status)


def _manifest(world: World, *, run_id: str, agent_id: str, intent: Mapping[str, Any], authority: Mapping[str, Any],
              action: Mapping[str, Any], exec_receipt: Mapping[str, Any], evidence: Sequence[Mapping[str, Any]],
              result_code: str, status: str, started_at: str, ended_at: str, stdout_sha: str) -> RunManifest:
    """009 run manifest. Receipt refs are the run's receipts in run-local order (009 requires seq contiguous
    from zero); receipt_id keeps the world-chain sequence so the two orders stay reconcilable."""
    run_receipts = [r for r in world.receipts if r["correlation_id"] == run_id]
    refs = tuple(ReceiptRef(f"receipt-{r['seq']}", i, r["entry_hash"]) for i, r in enumerate(run_receipts))
    pol = authority["policy_decision"]
    exec_status = "dry_run" if result_code == "DRY_RUN" else ("executed" if status == "completed" else "failed")
    manifest = RunManifest(
        run_id=run_id, actor_id=agent_id, mission=intent["objective"], started_at=started_at, ended_at=ended_at, status=status,
        components=tuple(ComponentRef(n, _component_version(n)) for n in COMPONENT_DISTRIBUTIONS),
        policy=PolicyRef(pol["policy_id"], pol["policy_version"]), inference=InferenceRef(None, None, "not_used"),
        inputs=(), evidence=tuple(EvidenceRef(e["evidence_id"], "sha256:" + e["content_digest"], "observed") for e in evidence),
        decisions=(DecisionRef(action["action_id"], "allow" if authority["decision"] == "granted" else "deny",
                               pol["policy_version"], authority["digest"]),),
        executions=(ExecutionRef("execution-1", action["operation"], exec_status, action["action_id"],
                                 f"receipt-{exec_receipt['seq']}", sha256_ref(canonical_json(dict(exec_receipt["payload"])))),),
        receipts=refs, outputs=(ArtifactRef("execution-stdout", stdout_sha, "text/plain"),),
    ).seal()
    RunManifest.from_mapping(manifest.to_dict())      # independent verifier pass
    return manifest
