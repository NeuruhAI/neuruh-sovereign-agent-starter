"""Multi-world seeder: WorldSeedSpec -> World (manifest, receipts, state) -> snapshot / fork / replay.

A World is a versioned, isolated operational context. Its only durable memory
is an append-only Agent Receipt chain (Public Commons 001); every state change
is a receipt payload, so `replay(seed, receipts)` reconstructs the effective
state without the original process. Determinism: the initial state digest is a
function of the immutable seed (fixtures included) and the explicitly inherited
state only — never of wall-clock time.

Vocabulary provenance: event types = neuruh-ledgers T24D EVENT_GRAMMAR
(`neuruh.closed-loop.event.v1`) plus an organism extension; forbidden payload
keys are the grammar's; lifecycle anchor = a 026-shaped genesis entry
(`lifecycle_anchor_digest = "sha256:" + entry_hash`, the Wave-16 E-1 convention).
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence

from neuruh_agent_receipt import GENESIS, seal_entry, verify_ledger
from neuruh_agent_run_manifest import canonical_json, sha256_ref
from neuruh_capability_registry import CapabilityRegistry
from neuruh_policy_gate import Policy

from . import contracts as C

T24D_EVENT_TYPES = (
    "source_observed", "signal_normalized", "recipe_evaluated", "opportunity_created", "opportunity_updated",
    "decision_proposed", "decision_approved", "decision_blocked", "action_intent_created", "action_executed",
    "action_failed", "forecast_sealed", "outcome_observed", "outcome_attributed", "calibration_recorded",
    "learning_proposed", "promotion_eligible", "promotion_held", "promotion_blocked", "version_promoted",
    "state_drift_observed",
)
ORGANISM_EVENT_TYPES = (
    "world_seeded", "agent_registered", "capability_registered", "capability_granted", "intent_created",
    "authority_granted", "authority_denied", "evidence_recorded", "revision_proposed", "revision_authorized",
    "revision_recorded", "effective_state_resolved", "snapshot_taken", "world_forked", "replay_verified",
)
EVENT_TYPES = T24D_EVENT_TYPES + ORGANISM_EVENT_TYPES
FORBIDDEN_PAYLOAD_KEYS = ("chain_of_thought", "cot", "hidden_reasoning", "inner_monologue", "raw_model_output",
                          "reasoning_trace", "scratchpad", "thoughts")
# agent-receipt (001) receipt_type -> required authority class
RECEIPT_AUTHORITY = {"decision": "governance-decision", "execution": "execution-evidence",
                     "observation": "observation", "outcome": "outcome-evidence"}
EVENT_RECEIPT_TYPE = {
    "decision_proposed": "decision", "decision_approved": "decision", "decision_blocked": "decision",
    "authority_granted": "decision", "authority_denied": "decision", "revision_authorized": "decision",
    "promotion_eligible": "decision", "promotion_held": "decision", "promotion_blocked": "decision",
    "action_executed": "execution", "action_failed": "execution",
    "outcome_observed": "outcome", "outcome_attributed": "outcome",
}
NEVER_INHERITED = ("credentials", "production_write_permissions", "private_external_connectors", "connectors",
                   "authority_outside_parent_grant")
INHERITABLE = ("canonical_state", "policy", "capability_manifest", "agent_roster", "grant_templates", "fixtures",
               "memory.world_state", "memory.semantic", "memory.evidence", "recipe_registry", "signal_registry")
MEMORY_CLASSES = ("ephemeral_run_context", "world_state", "semantic_memory", "evidence", "receipts", "outcomes",
                  "canonical_state", "human_notes")


class WorldError(C.ContractError):
    pass


# ------------------------------------------------------------------ seed
def world_seed_spec(*, seed_id: str, seed_version: str, world_type: str, world_mode: str, purpose: str,
                    policy: Mapping[str, Any], capability_manifest: Mapping[str, Any],
                    agent_roster: Sequence[Mapping[str, Any]], grant_templates: Sequence[Mapping[str, Any]],
                    capability_budget: Mapping[str, Any], memory_namespace: str, evidence_namespace: str,
                    fixtures: Mapping[str, Any], initial_canonical_state: Mapping[str, Any],
                    tools_available: Sequence[str], action_class_map: Mapping[str, str],
                    connectors: Sequence[Mapping[str, Any]] = (), signal_registry: Sequence[Any] = (),
                    recipe_registry: Sequence[Any] = (), immutable: bool = True) -> dict[str, Any]:
    C._in(world_mode, C.WORLD_MODES, "world_mode")
    CapabilityRegistry.from_manifest(capability_manifest)               # fail closed on a bad manifest
    Policy.create(policy["policy_id"], blocked_domains=policy.get("blocked_domains", ()),
                  allowed_tools=policy.get("allowed_tools", ()), approval_tags=policy.get("approval_tags", ()),
                  max_spend=policy.get("max_spend", 0))
    if "clock_start" not in fixtures:
        raise WorldError("fixtures.clock_start is required so the initial state hash never depends on wall-clock")
    C._in(initial_canonical_state.get("stage"), C.STAGES, "initial_canonical_state.stage")
    if not isinstance(initial_canonical_state.get("state"), Mapping):
        raise WorldError("initial_canonical_state.state must be an object")
    for op, cls in action_class_map.items():
        if cls not in C.ACTION_CLASS_TIERS:
            raise WorldError(f"action class {cls!r} for {op!r} is unknown (fails closed)")
    if world_mode == "synthetic" and connectors:
        raise WorldError("a synthetic world declares no connectors")
    body = {
        "seed_id": seed_id, "seed_version": seed_version, "world_type": world_type, "world_mode": world_mode,
        "purpose": purpose, "policy": dict(policy), "capability_manifest": dict(capability_manifest),
        "agent_roster": [dict(a) for a in agent_roster], "grant_templates": [dict(g) for g in grant_templates],
        "capability_budget": dict(capability_budget), "memory_namespace": memory_namespace,
        "evidence_namespace": evidence_namespace, "connectors": [dict(c) for c in connectors],
        "signal_registry": list(signal_registry), "recipe_registry": list(recipe_registry),
        "fixtures": dict(fixtures), "initial_canonical_state": dict(initial_canonical_state),
        "tools_available": sorted(set(tools_available)), "action_class_map": dict(action_class_map),
        "immutable": bool(immutable), "created_at": fixtures["clock_start"],
    }
    return C.seal("world_seed_spec", body, id_field="seed_id")


def initial_state_digest(seed: Mapping[str, Any], inherited: Mapping[str, Any] | None = None) -> str:
    """Deterministic: seed digest (which covers fixtures) + explicitly inherited state only."""
    return sha256_ref(canonical_json({"seed_digest": seed["digest"], "inherited": dict(inherited or {})}))


def _lifecycle_anchor(world_id: str, target_id: str, stage: str, state_digest: str, observed_at: str) -> dict[str, Any]:
    """026-shaped genesis entry (neuruh.lifecycle-state-ledger.v0.1 field names)."""
    entry = {
        "schema_version": "neuruh.lifecycle-state-ledger.v0.1", "ledger_id": f"lifecycle:{world_id}",
        "entry_id": "genesis", "sequence": 0, "target_id": target_id, "kind": "genesis", "from_stage": None,
        "to_stage": stage, "pre_state_digest": None, "post_state_digest": state_digest, "observed_at": observed_at,
        "source_evidence_digest": sha256_ref(canonical_json({"seed_target": target_id})),
        "stage_transition_receipt_digest": None, "rollback_receipt_digest": None,
        "authorization_consumption_digest": None, "previous_entry_hash": None, "execution_authority": False,
    }
    entry["entry_hash"] = sha256(canonical_json(entry).encode("utf-8")).hexdigest()
    return entry


def canonical_state_digest(state: Mapping[str, Any]) -> str:
    return sha256_ref(canonical_json(dict(state)))


# ------------------------------------------------------------------ world
class World:
    """One isolated operational context. All mutation goes through `record`."""

    def __init__(self, manifest: dict[str, Any], seed: dict[str, Any], *, inherited: Mapping[str, Any] | None = None):
        self.manifest = manifest
        self.seed = seed
        self.world_id = manifest["world_id"]
        self.receipts: list[dict[str, Any]] = []
        self._prev = GENESIS
        self.agents: dict[str, dict[str, Any]] = {}
        self.grants: dict[str, dict[str, Any]] = {}
        self.authority_uses: dict[str, int] = {}
        self.evidence: list[dict[str, Any]] = []
        self.outcomes: list[dict[str, Any]] = []
        self.calibration: list[dict[str, Any]] = []
        self.proposals: list[dict[str, Any]] = []
        self.authorizations: list[dict[str, Any]] = []
        self.promotions: list[dict[str, Any]] = []
        self.revisions: list[dict[str, Any]] = []
        self.effective: dict[str, Any] | None = None
        self.children: list[str] = []
        self.counts: dict[str, int] = {}
        inh = dict(inherited or {})
        state = dict(inh.get("canonical_state", seed["initial_canonical_state"]["state"]))
        self.canonical = {"target_id": manifest["canonical_target_id"],
                          "stage": inh.get("canonical_stage", seed["initial_canonical_state"]["stage"]),
                          "state": state, "state_digest": canonical_state_digest(state)}
        self.anchor = _lifecycle_anchor(self.world_id, self.canonical["target_id"], self.canonical["stage"],
                                        self.canonical["state_digest"], seed["fixtures"]["clock_start"])
        self.memory: dict[str, Any] = {
            "ephemeral_run_context": {}, "world_state": dict(inh.get("memory.world_state", {})),
            "semantic_memory": list(inh.get("memory.semantic", [])), "evidence": [], "receipts": "chain",
            "outcomes": [], "canonical_state": "resolved-by-036", "human_notes": [],
        }

    # ---- identity helpers
    @property
    def lifecycle_anchor_digest(self) -> str:
        return "sha256:" + self.anchor["entry_hash"]

    def registry(self) -> CapabilityRegistry:
        return CapabilityRegistry.from_manifest(self.seed["capability_manifest"])

    def policy(self) -> Policy:
        p = self.seed["policy"]
        return Policy.create(p["policy_id"], blocked_domains=p.get("blocked_domains", ()),
                             allowed_tools=p.get("allowed_tools", ()), approval_tags=p.get("approval_tags", ()),
                             max_spend=p.get("max_spend", 0))

    @property
    def tools_available(self) -> tuple[str, ...]:
        return tuple(self.seed["tools_available"])

    @property
    def world_mode(self) -> str:
        return self.seed["world_mode"]

    @property
    def evidence_class(self) -> str:
        return "live" if self.world_mode == "live" else "fixture"

    def run_id(self, agent_id: str, sequence: int) -> str:
        """Deterministic run id: same seed + agent + sequence -> same run id."""
        return "run-" + sha256(f"{self.seed['digest']}|{self.world_id}|{agent_id}|{sequence}".encode()).hexdigest()[:24]

    # ---- the only write path
    def record(self, event_type: str, payload: Mapping[str, Any], *, observed_at: str, run_id: str,
               causation_id: str) -> dict[str, Any]:
        if event_type not in EVENT_TYPES:
            raise WorldError(f"unknown event_type {event_type!r} (fails closed)")
        for name, value in (("run_id", run_id), ("causation_id", causation_id), ("observed_at", observed_at)):
            if not isinstance(value, str) or not value.strip():
                raise WorldError(f"{name} must be a non-empty string (a receipt without correlation is not a receipt)")
        for k in payload:
            if k in FORBIDDEN_PAYLOAD_KEYS:
                raise WorldError(f"forbidden payload key {k!r}")
        rtype = EVENT_RECEIPT_TYPE.get(event_type, "observation")
        entry = {
            "schema_version": "neuruh.agent-receipt.v1alpha1", "receipt_type": rtype,
            "authority": RECEIPT_AUTHORITY[rtype], "observed_at": observed_at, "subject": self.world_id,
            "correlation_id": run_id, "causation_id": causation_id,
            "payload": {"event_type": event_type, "world_id": self.world_id, **dict(payload)},
        }
        sealed = seal_entry(entry, prev_hash=self._prev, seq=len(self.receipts))
        self._fold(event_type, sealed["payload"])
        self.receipts.append(sealed)
        self._prev = sealed["entry_hash"]
        return sealed

    def _fold(self, event_type: str, payload: Mapping[str, Any]) -> list[str]:
        """Apply one event to state. Returns replay gaps (unknown/incomplete payloads) instead of guessing."""
        gaps: list[str] = []
        self.counts[event_type] = self.counts.get(event_type, 0) + 1
        try:
            if event_type == "agent_registered":
                self.agents[payload["identity"]["agent_id"]] = payload["identity"]
            elif event_type == "capability_granted":
                self.grants[payload["grant"]["grant_id"]] = payload["grant"]
            elif event_type == "evidence_recorded":
                self.evidence.append(payload["evidence"])
            elif event_type == "outcome_observed":
                self.outcomes.append(payload["outcome_record"])
            elif event_type == "calibration_recorded":
                self.calibration.append(payload["calibration_record"])
            elif event_type in ("learning_proposed", "revision_proposed"):
                self.proposals.append(payload["proposal"])
            elif event_type == "revision_authorized":
                self.authorizations.append(payload["authorization"])
            elif event_type in ("promotion_eligible", "promotion_held", "promotion_blocked"):
                self.promotions.append(payload["promotion_decision"])
            elif event_type == "revision_recorded":
                entry = payload["revision_entry"]
                self.revisions.append(entry)
                self.canonical["state"] = dict(payload["post_state"])
                self.canonical["state_digest"] = entry["to_canonical_state_digest"]
                if self.canonical["state_digest"] != canonical_state_digest(self.canonical["state"]):
                    raise WorldError("post_state does not hash to the revision's to_canonical_state_digest")
            elif event_type == "effective_state_resolved":
                self.effective = payload["effective_canonical_state"]
            elif event_type == "world_forked":
                self.children.append(payload["child_world_id"])
            elif event_type == "authority_granted":
                self.authority_uses[payload["authority_decision"]["authority_id"]] = 0
            elif event_type == "action_executed":
                aid = payload.get("authority_id")
                if aid is not None:
                    self.authority_uses[aid] = self.authority_uses.get(aid, 0) + 1
        except KeyError as exc:
            gaps.append(f"{event_type}: payload missing {exc}")
        return gaps

    # ---- convenience recorders
    def register_agent(self, agent_id: str, roles: Sequence[str], *, at: str, creator: str) -> dict[str, Any]:
        ident = C.agent_identity(agent_id=agent_id, world_id=self.world_id, roles=roles, created_at=at,
                                 creator=creator, provenance_=C.provenance("world.register_agent", seed=self.seed["seed_id"]))
        self.record("agent_registered", {"identity": ident}, observed_at=at, run_id=self.run_id(agent_id, 0),
                    causation_id=f"seed:{self.seed['seed_id']}")
        return ident

    def grant(self, grant: Mapping[str, Any], *, at: str) -> dict[str, Any]:
        C.verify(grant)
        if grant["world_id"] != self.world_id:
            raise WorldError("grant belongs to a different world")
        if grant["subject"] not in self.agents:
            raise WorldError("grant subject is not a registered agent of this world")
        self.record("capability_granted", {"grant": dict(grant)}, observed_at=at,
                    run_id=self.run_id(grant["subject"], 0), causation_id=grant["issuer"])
        return dict(grant)

    # ---- state identity
    def state_summary(self) -> dict[str, Any]:
        return {
            "manifest_digest": self.manifest["digest"], "initial_state_digest": self.manifest["initial_state_digest"],
            "lifecycle_anchor_digest": self.lifecycle_anchor_digest,
            "canonical": {"target_id": self.canonical["target_id"], "stage": self.canonical["stage"],
                          "state_digest": self.canonical["state_digest"]},
            "effective_state_digest": (self.effective or {}).get("effective_state_digest"),
            "effective_resolution_digest": ((self.effective or {}).get("resolution") or {}).get("resolution_digest"),
            "revision_ledger": [e["entry_hash"] for e in self.revisions],
            "agents": sorted(self.agents), "grants": sorted(g["digest"] for g in self.grants.values()),
            "evidence": [e["digest"] for e in self.evidence],
            "outcomes": [o["content_sha256"] for o in self.outcomes],
            "calibration": [c["digest"] for c in self.calibration],
            "proposals": [p["digest"] for p in self.proposals],
            "authorizations": [a["authorization_digest"] for a in self.authorizations],
            "promotions": [p["digest"] for p in self.promotions],
            "children": list(self.children), "counts": dict(sorted(self.counts.items())),
        }

    def state_digest(self) -> str:
        return sha256_ref(canonical_json(self.state_summary()))

    @property
    def receipts_tip(self) -> str:
        return self._prev

    def snapshot(self, *, taken_at: str, run_id: str) -> dict[str, Any]:
        snap = C.seal("world_snapshot", {
            "snapshot_id": f"snap-{self.world_id}-{len(self.receipts)}", "world_id": self.world_id,
            "manifest_digest": self.manifest["digest"], "seed_digest": self.seed["digest"],
            "receipts_tip": self.receipts_tip, "receipt_count": len(self.receipts),
            "state_digest": self.state_digest(), "state_summary": self.state_summary(),
            "canonical_state": dict(self.canonical), "created_at": taken_at,
        }, id_field="snapshot_id")
        self.record("snapshot_taken", {"snapshot_digest": snap["digest"], "state_digest": snap["state_digest"],
                                       "receipt_count": snap["receipt_count"]},
                    observed_at=taken_at, run_id=run_id, causation_id=snap["snapshot_id"])
        return snap

    # ---- fork
    def fork(self, *, child_world_id: str, created_at: str, creator: str, purpose: str,
             inherit: Sequence[str], run_id: str) -> tuple["World", dict[str, Any]]:
        refused = sorted(set(inherit) & set(NEVER_INHERITED))
        if refused:
            raise WorldError(f"fork refused: {refused} can never be inherited")
        unknown = sorted(set(inherit) - set(INHERITABLE))
        if unknown:
            raise WorldError(f"fork refused: unknown inheritance items {unknown}")
        snap = self.snapshot(taken_at=created_at, run_id=run_id)
        inherited: dict[str, Any] = {"forked_from_snapshot": snap["digest"]}
        if "canonical_state" in inherit:
            inherited["canonical_state"] = dict(self.canonical["state"])
            inherited["canonical_stage"] = self.canonical["stage"]
        if "memory.world_state" in inherit:
            inherited["memory.world_state"] = dict(self.memory["world_state"])
        if "memory.semantic" in inherit:
            inherited["memory.semantic"] = list(self.memory["semantic_memory"])
        child_seed = dict(self.seed)
        child = instantiate(child_seed, world_id=child_world_id, created_at=created_at, creator=creator,
                            parent_world_id=self.world_id, lineage=[*self.manifest["lineage"], self.world_id],
                            inherited=inherited, purpose=purpose)
        # grants are never copied across worlds: a child grant must be re-derived via
        # derive_child_grant (subset of the parent grant) and issued to a registered child agent.
        branch = C.seal("world_branch", {
            "branch_id": f"branch-{self.world_id}-{child_world_id}", "parent_world_id": self.world_id,
            "child_world_id": child_world_id, "snapshot_digest": snap["digest"], "inherited": sorted(inherit),
            "never_inherited": list(NEVER_INHERITED), "purpose": purpose, "created_at": created_at,
        }, id_field="branch_id")
        self.record("world_forked", {"child_world_id": child_world_id, "branch": branch},
                    observed_at=created_at, run_id=run_id, causation_id=snap["snapshot_id"])
        return child, branch

    def derive_child_grant(self, parent_grant: Mapping[str, Any], child: "World", *, grant_id: str,
                           subject: str, created_at: str) -> dict[str, Any]:
        """A child grant is a subset of a parent grant: never wider, never longer, never more spend."""
        C.verify(parent_grant)
        if parent_grant["world_id"] != self.world_id:
            raise WorldError("parent grant is not from this world")
        return C.capability_grant(
            grant_id=grant_id, world_id=child.world_id, issuer=f"world:{self.world_id}", subject=subject,
            operations=parent_grant["operations"], forbidden_operations=parent_grant["forbidden_operations"],
            max_spend_usd=parent_grant["max_spend_usd"], issued_at=parent_grant["issued_at"],
            expires_at=parent_grant["expires_at"], evidence_class_ceiling=parent_grant["evidence_class_ceiling"],
            stage_ceiling=parent_grant["stage_ceiling"], created_at=created_at,
            derived_from_grant=parent_grant["digest"])

    def to_dict(self) -> dict[str, Any]:
        return {"manifest": self.manifest, "seed_digest": self.seed["digest"], "receipts": list(self.receipts),
                "state_summary": self.state_summary(), "state_digest": self.state_digest(),
                "canonical": dict(self.canonical), "effective": self.effective, "memory_classes": list(MEMORY_CLASSES)}


# ------------------------------------------------------------------ instantiate / replay
def instantiate(seed: Mapping[str, Any], *, world_id: str, created_at: str, creator: str,
                parent_world_id: str | None = None, lineage: Sequence[str] = (),
                inherited: Mapping[str, Any] | None = None, purpose: str | None = None) -> World:
    C.verify(seed)
    if seed["schema_version"] != C.SCHEMA["world_seed_spec"]:
        raise WorldError("not a world seed spec")
    inh = dict(inherited or {})
    isd = initial_state_digest(seed, inh)
    manifest = C.seal("world_manifest", {
        "world_id": world_id, "world_type": seed["world_type"], "world_mode": seed["world_mode"],
        "parent_world_id": parent_world_id, "lineage": list(lineage), "seed_id": seed["seed_id"],
        "seed_version": seed["seed_version"], "seed_digest": seed["digest"], "initial_state_digest": isd,
        "purpose": purpose or seed["purpose"], "creator": creator, "created_at": created_at,
        "policy_id": seed["policy"]["policy_id"], "capability_budget": seed["capability_budget"],
        "agent_roster": seed["agent_roster"], "memory_namespace": f"{seed['memory_namespace']}/{world_id}",
        "evidence_namespace": f"{seed['evidence_namespace']}/{world_id}", "connectors": seed["connectors"],
        "signal_registry": seed["signal_registry"], "recipe_registry": seed["recipe_registry"],
        "canonical_target_id": f"{world_id}:canonical", "tools_available": seed["tools_available"],
        "inherited": sorted(k for k in inh if k != "forked_from_snapshot"),
        "forked_from_snapshot": inh.get("forked_from_snapshot"), "never_inherited": list(NEVER_INHERITED),
        "memory_classes": list(MEMORY_CLASSES),
    }, id_field="world_id")
    world = World(manifest, dict(seed), inherited=inh)
    world.record("world_seeded", {"manifest": manifest, "initial_state_digest": isd,
                                  "lifecycle_anchor": world.anchor, "creator": creator, "created_at": created_at,
                                  "inherited": inh},
                 observed_at=created_at, run_id=world.run_id("seeder", 0), causation_id=f"seed:{seed['seed_id']}")
    return world


def replay(seed: Mapping[str, Any], receipts: Sequence[Mapping[str, Any]]) -> tuple[World, list[str]]:
    """Reconstruct a world from seed + receipt chain only. Gaps are reported, never bridged."""
    verify_ledger(list(receipts))
    if not receipts or receipts[0]["payload"].get("event_type") != "world_seeded":
        raise WorldError("replay requires a world_seeded receipt at sequence 0")
    first = receipts[0]["payload"]
    m = first["manifest"]
    world = instantiate(seed, world_id=m["world_id"], created_at=first["created_at"], creator=first["creator"],
                        parent_world_id=m["parent_world_id"], lineage=m["lineage"], inherited=first.get("inherited"),
                        purpose=m["purpose"])
    if world.manifest["digest"] != m["digest"]:
        raise WorldError("replayed manifest digest differs from the recorded manifest (seed/receipt mismatch)")
    if world.receipts[0]["entry_hash"] != receipts[0]["entry_hash"]:
        raise WorldError("replayed genesis receipt differs from the recorded one")
    gaps: list[str] = []
    for r in receipts[1:]:
        payload = r["payload"]
        et = payload.get("event_type")
        if et not in EVENT_TYPES:
            gaps.append(f"seq {r['seq']}: unknown event_type {et!r}")
            continue
        gaps.extend(world._fold(et, payload))
        world.receipts.append(dict(r))
        world._prev = r["entry_hash"]
    return world, gaps
