"""Agent authority model — six separate facts, one decision, single use.

    TOOL EXISTS  ->  CAPABILITY REGISTERED  ->  CAPABILITY GRANTED  ->  POLICY ALLOWS
                 ->  AUTHORITY PRESENT      ->  ACTION EXECUTED

Each fact is tri-state (True | False | "unknown"). An agent never gains authority
because a tool exists or because a capability is registered; authority is
present only when every fact is positively True, the risk tier is admitted by
the grant's hard floors, and the decision has not expired or been consumed.

The decision also carries a `gov.decision.request.v1` projection so the LIVE
governance organ (autonomous-governance-core :8848) can evaluate the same
request later. Nothing here contacts a network.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence

from neuruh_agent_run_manifest import canonical_json, sha256_ref
from neuruh_capability_registry import CapabilityError

from . import contracts as C

TIER_TO_MUTATION = {"R0": "read_only", "R1": "reversible_write", "R2": "persistent_write",
                    "R3": "persistent_write", "R4": "persistent_write", "R5": "destructive"}
# Hard floors of a grant map to tiers that no grant may admit (external consequence and destructive).
FLOOR_BLOCKED_TIERS = {"R4", "R5"}
DECISIONS = ("granted", "denied", "approval_required")


class AuthorityError(C.ContractError):
    pass


def tool_exists(tools_available: Sequence[str], tool: str | None) -> bool | str:
    if tool is None:
        return C.UNKNOWN
    return tool in set(tools_available)


def grant_admits(grant: Mapping[str, Any] | None, *, agent_id: str, operation: str, spend_usd: float,
                 at: str) -> tuple[bool | str, list[str]]:
    """Does this grant admit this agent doing this operation now? Unknown stays unknown."""
    if grant is None:
        return False, ["no capability grant presented"]
    reasons: list[str] = []
    try:
        C.verify(grant)
    except C.ContractError as exc:
        return C.UNKNOWN, [f"grant unverifiable: {exc}"]
    if grant["schema_version"] != C.SCHEMA["capability_grant"]:
        return False, ["object is not a capability grant"]
    if grant["subject"] != agent_id:
        reasons.append("grant subject is a different agent (grants are non-transferable)")
    if operation in grant["forbidden_operations"]:
        reasons.append(f"operation {operation!r} is explicitly forbidden by the grant")
    elif operation not in grant["operations"]:
        reasons.append(f"operation {operation!r} is not granted")
    if not (grant["issued_at"] <= at < grant["expires_at"]):
        reasons.append("grant is not valid at this time")
    if float(spend_usd) > float(grant["max_spend_usd"]):
        reasons.append("spend exceeds grant ceiling")
    return (not reasons), reasons


def risk_tier(action_class: str | None) -> tuple[str | None, str | None]:
    if action_class is None:
        return None, "action class undeclared (fails closed)"
    tier = C.ACTION_CLASS_TIERS.get(action_class)
    if tier is None:
        return None, f"unknown action class {action_class!r} (fails closed)"
    return tier, None


def decide(*, world_id: str, run_id: str, agent_id: str, intent: Mapping[str, Any], registry, policy_record: Mapping[str, Any],
           grant: Mapping[str, Any] | None, tools_available: Sequence[str], tool: str | None,
           action_class: str | None, actor_authority_class: str, spend_usd: float, at: str, expires_at: str,
           evidence_class: str, source_sha: str, target: Mapping[str, str], nonce_salt: str = "") -> dict[str, Any]:
    """Compute the authority decision from separately established facts."""
    C.verify(intent)
    operation = intent["requested_operation"]
    facts: dict[str, Any] = {}
    reasons: list[str] = []

    facts["tool_exists"] = tool_exists(tools_available, tool)
    if facts["tool_exists"] is not True:
        reasons.append("tool not present in world tool catalogue" if facts["tool_exists"] is False else "tool identity unknown")

    try:
        registry.validate_args(operation, intent["args"])
        registry.resolve(operation)
        facts["capability_registered"] = True
    except CapabilityError as exc:
        facts["capability_registered"] = False
        reasons.append(f"capability not registered/valid: {exc}")

    admitted, grant_reasons = grant_admits(grant, agent_id=agent_id, operation=operation, spend_usd=spend_usd, at=at)
    facts["capability_granted"] = C.tri(admitted, "capability_granted")
    reasons.extend(grant_reasons)

    pol = policy_record["decision"]
    facts["policy_allows"] = True if pol == "allow" else (False if pol == "deny" else C.UNKNOWN)
    if pol != "allow":
        reasons.append(f"policy gate returned {pol}: " + "; ".join(policy_record.get("reasons", [])))

    tier, tier_err = risk_tier(action_class)
    if tier_err:
        reasons.append(tier_err)
    elif tier in FLOOR_BLOCKED_TIERS:
        reasons.append(f"risk tier {tier} is outside every grant's hard floors (external/destructive consequence)")

    hard = [facts["tool_exists"], facts["capability_registered"], facts["capability_granted"]]
    if all(f is True for f in hard) and tier is not None and tier not in FLOOR_BLOCKED_TIERS and at < expires_at:
        if pol == "allow":
            decision = "granted"
        elif pol == "escalate":
            decision = "approval_required"
        else:
            decision = "denied"
    else:
        decision = "denied"
    facts["authority_present"] = decision == "granted"
    facts["action_executed"] = False   # only an execution receipt can turn this true, and never here
    if decision == "granted" and not reasons:
        reasons.append("all authority facts positively established")

    nonce = sha256(f"{world_id}|{run_id}|{intent['digest']}|{nonce_salt}".encode()).hexdigest()[:32]
    mutation_class = TIER_TO_MUTATION.get(tier or "", "destructive")
    governance_request = {
        "schema_version": C.ESTABLISHED["governance_request"], "request_id": f"req-{nonce[:16]}",
        "mission_id": f"world:{world_id}", "plan_id": intent["intent_id"], "step_id": operation,
        "correlation_id": run_id, "causation_id": intent["intent_id"], "authority_class": actor_authority_class,
        "operation": operation, "tool": tool or "unknown", "mutation_class": mutation_class,
        "evidence_class": evidence_class, "repository": "neuruh-sovereign-agent-starter", "domain": target.get("domain", "sandbox"),
        "summary": intent["objective"], "requested_capability": operation,
        "policy_version": policy_record["policy_version"], "precondition_hash": intent["digest"][7:],
        "nonce": nonce, "issued_at": at,
        "requester": {"component": "neuruh-sovereign-agent-starter/organism", "source_sha": source_sha},
        "target": {"type": target.get("type", "path"), "id": target.get("id", "unknown")},
        "args": dict(intent["args"]), "tags": list(target.get("tags", [])), "spend_usd": float(spend_usd),
    }
    body = {
        "authority_id": f"auth-{nonce[:24]}", "world_id": world_id, "run_id": run_id, "agent_id": agent_id,
        "intent_id": intent["intent_id"], "intent_digest": intent["digest"], "operation": operation,
        "facts": facts, "decision": decision, "reasons": reasons, "risk_tier": tier,
        "world_engine_level": C.TIER_TO_WORLD_ENGINE_LEVEL.get(tier or "", None),
        "mutation_class": mutation_class, "authority_class": actor_authority_class,
        "grant_digest": grant.get("digest") if grant else None, "policy_decision": dict(policy_record),
        "policy_version": policy_record["policy_version"], "nonce": nonce, "max_uses": 1,
        "issued_at": at, "expires_at": expires_at, "created_at": at, "evidence_class": evidence_class,
        "governance_request": governance_request, "governance_submitted": False,
        "execution_authority": decision == "granted", "deployment_authority": False, "canonical_state_authority": False,
    }
    return C.seal("authority_decision", body, id_field="authority_id")


def assert_usable(decision: Mapping[str, Any], *, at: str, uses_so_far: int) -> None:
    """NO_AUTHORITY_NO_ACTION: only a granted, unexpired, unconsumed decision releases an action."""
    C.verify(decision)
    if decision["decision"] != "granted" or decision["facts"]["authority_present"] is not True:
        raise AuthorityError("authority not present: " + "; ".join(decision["reasons"]))
    if not (decision["issued_at"] <= at < decision["expires_at"]):
        raise AuthorityError("authority decision expired or not yet valid")
    if uses_so_far >= decision["max_uses"]:
        raise AuthorityError("authority decision already consumed (single use)")


# ------------------------------------------------------------------ projections to live organs
def to_axon_task_request(action: Mapping[str, Any], *, tenant_id: str, operator_id: str, case_id: str,
                         session_id: str, govern_only: bool = True) -> dict[str, Any]:
    """neuruh-axon gateway TaskRequest shape (src/gateway/types.ts). Built, never sent."""
    return {
        "task": f"{action['operation']} in world {action['world_id']}", "agentId": action["agent_id"],
        "context": {"tenantId": tenant_id, "operatorId": operator_id, "caseId": case_id, "sessionId": session_id,
                    "note": f"authority:{action['authority_digest']}"},
        "action": {"action_id": action["action_id"], "domain": "sandbox", "tool": action["operation"],
                   "tags": [], "spend_usd": 0, "description": "organism action request projection"},
        "govern_only": bool(govern_only),
    }


def to_world_engine_decision_receipt(decision: Mapping[str, Any], *, issued_at: str) -> dict[str, Any]:
    """neuruh-world-engine-alpha decision-receipt schema (0.2.0) projection with checksum."""
    body = {
        "schema_version": "0.2.0", "receipt_id": decision["authority_id"], "world_id": decision["world_id"],
        "receipt_type": "authority-decision", "issued_at": issued_at,
        "authority": decision.get("world_engine_level") or "L0_OBSERVE",
        "evidence_refs": [f"intent:{decision['intent_digest']}", f"policy:{decision['policy_version']}"],
        "decision": {"result": decision["decision"].upper(), "reasons": list(decision["reasons"])},
        "outcome_status": "VERIFIED" if decision["decision"] == "granted" else "BLOCKED",
        "reversibility": {"class": "reversible" if decision["mutation_class"] in ("read_only", "reversible_write") else "release",
                          "rollback": "sandbox discard"},
        "proof_tags": ["authority_policy_conformance"],
    }
    body["checksum"] = sha256(canonical_json(body).encode("utf-8")).hexdigest()
    return body
