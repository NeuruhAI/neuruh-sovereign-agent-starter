"""Tiny public-safe utilities that do not depend on the private Neuruh runtime.

The functions in this module are deliberately boring, deterministic, and
standalone.  They are useful at the edges of an agent system without exposing
private orchestration, policy, recipes, prompts, or production topology.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


MAX_CONTEXT_BYTES = 4096
MAX_STATE_DIFF_BYTES = 4096
MAX_STATE_DIFF_DEPTH = 12
DEFAULT_FOUNDER_MINUTE_COST_USD = 2.0
DEFAULT_LATENCY_MINUTE_COST_USD = 0.05

_CONTEXT_FIELDS = (
    "mission_id",
    "parent_mission_id",
    "objective",
    "current_state",
    "changed_since_last_run",
    "canonical_refs",
    "known_failures",
    "blockers",
    "authority",
    "budget",
    "acceptance_test",
    "next_action",
)
_FORBIDDEN_CONTEXT_KEYS = {
    "chat",
    "chats",
    "conversation",
    "messages",
    "prompt_history",
    "raw_transcript",
    "transcript",
}
_PUBLIC_PROOF_FIELDS = (
    "mission",
    "mission_id",
    "artifact",
    "version",
    "status",
    "outcome",
    "commit_sha",
    "tests",
    "public_url",
    "limitations",
    "generated_at",
)
_FORBIDDEN_STATE_KEYS = _FORBIDDEN_CONTEXT_KEYS | {
    "aegis",
    "axon",
    "customer_data",
    "customer_records",
    "deedsonar",
    "father",
    "governance_core",
    "iar",
    "landos",
    "mother",
    "private_memory",
    "private_policy",
    "private_url",
    "prompt",
    "prompts",
    "recipe",
    "recipes",
    "weights",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compile_context_packet(state: Mapping[str, Any], *, max_bytes: int = MAX_CONTEXT_BYTES) -> dict[str, Any]:
    """Return a bounded pointer-heavy execution packet.

    Unknown fields are ignored rather than copied.  Transcript/chat fields are
    explicitly refused so this helper cannot accidentally become a raw-context
    replay mechanism.
    """
    if not isinstance(state, Mapping):
        raise TypeError("state must be an object")
    if not isinstance(max_bytes, int) or max_bytes < 256:
        raise ValueError("max_bytes must be an integer >= 256")
    forbidden = sorted(k for k in state if str(k).lower() in _FORBIDDEN_CONTEXT_KEYS)
    if forbidden:
        raise ValueError(f"raw conversational context is not accepted: {', '.join(forbidden)}")

    packet: dict[str, Any] = {}
    for key in _CONTEXT_FIELDS:
        if key in state and state[key] not in (None, "", [], {}):
            packet[key] = state[key]

    encoded = _canonical_json(packet).encode("utf-8")
    if len(encoded) <= max_bytes:
        return packet

    # Preserve the execution spine first.  Trim only list-like detail fields.
    trimmable = ["canonical_refs", "known_failures", "changed_since_last_run", "blockers"]
    for key in trimmable:
        value = packet.get(key)
        if isinstance(value, list):
            while value and len(_canonical_json(packet).encode("utf-8")) > max_bytes:
                value.pop()
            if not value:
                packet.pop(key, None)
        if len(_canonical_json(packet).encode("utf-8")) <= max_bytes:
            return packet

    if len(_canonical_json(packet).encode("utf-8")) > max_bytes:
        raise ValueError("essential context fields exceed max_bytes; store large payloads externally and pass refs")
    return packet


@dataclass(frozen=True)
class RouteDecision:
    candidate_id: str
    layer: str
    score: float
    expected_value_usd: float
    total_cost_usd: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "layer": self.layer,
            "score": round(self.score, 6),
            "expected_value_usd": round(self.expected_value_usd, 6),
            "total_cost_usd": round(self.total_cost_usd, 6),
        }


def choose_cheapest_capable_route(
    candidates: Sequence[Mapping[str, Any]],
    *,
    minimum_success_probability: float = 0.8,
    founder_minute_cost_usd: float = DEFAULT_FOUNDER_MINUTE_COST_USD,
    latency_minute_cost_usd: float = DEFAULT_LATENCY_MINUTE_COST_USD,
) -> RouteDecision:
    """Choose the highest net-value candidate above the capability floor.

    Net score = p(success) * expected value - execution/model/risk/founder/latency costs.
    Deterministic tie-breaking prefers lower total cost, then lexical layer/id.
    """
    if not 0 <= minimum_success_probability <= 1:
        raise ValueError("minimum_success_probability must be between 0 and 1")
    decisions: list[RouteDecision] = []
    for item in candidates:
        cid = str(item.get("candidate_id", "")).strip()
        layer = str(item.get("layer", "")).strip().upper()
        if not cid or layer not in {"L0", "L1", "L2", "L3", "L4"}:
            raise ValueError("every candidate needs candidate_id and layer L0..L4")
        p = float(item.get("success_probability", 0.0))
        if not 0 <= p <= 1:
            raise ValueError(f"{cid}: success_probability must be between 0 and 1")
        if p < minimum_success_probability:
            continue
        ev = float(item.get("expected_value_usd", 0.0))
        execution = float(item.get("execution_cost_usd", 0.0))
        model = float(item.get("model_cost_usd", 0.0))
        risk = float(item.get("risk_cost_usd", 0.0))
        founder_minutes = float(item.get("founder_minutes", 0.0))
        latency_minutes = float(item.get("latency_minutes", 0.0))
        if min(ev, execution, model, risk, founder_minutes, latency_minutes) < 0:
            raise ValueError(f"{cid}: numeric inputs cannot be negative")
        total_cost = (
            execution
            + model
            + risk
            + founder_minutes * founder_minute_cost_usd
            + latency_minutes * latency_minute_cost_usd
        )
        score = p * ev - total_cost
        decisions.append(RouteDecision(cid, layer, score, ev, total_cost))

    if not decisions:
        raise ValueError("no candidate meets the capability floor")
    decisions.sort(key=lambda d: (-d.score, d.total_cost_usd, d.layer, d.candidate_id))
    return decisions[0]


def public_proof_card(record: Mapping[str, Any], *, extra_allow: Iterable[str] = ()) -> dict[str, Any]:
    """Project a record through an explicit public allowlist.

    This is an allowlist, not a blacklist.  Private implementation details are
    therefore omitted by default even when callers add unexpected fields.
    """
    if not isinstance(record, Mapping):
        raise TypeError("record must be an object")
    allowed = set(_PUBLIC_PROOF_FIELDS) | {str(k) for k in extra_allow}
    card = {key: record[key] for key in _PUBLIC_PROOF_FIELDS if key in record}
    for key in sorted(set(record) & allowed - set(_PUBLIC_PROOF_FIELDS)):
        card[key] = record[key]
    return card


def _collect_forbidden_keys(value: Any, found: set[str]) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN_STATE_KEYS:
                found.add(str(key))
            _collect_forbidden_keys(item, found)
    elif isinstance(value, list):
        for item in value:
            _collect_forbidden_keys(item, found)


def _format_path(parts: Sequence[str]) -> str:
    return ".".join(parts)


def _diff_nodes(
    before: Any,
    after: Any,
    parts: list[str],
    added: list[dict[str, Any]],
    removed: list[dict[str, Any]],
    changed: list[dict[str, Any]],
    depth: int,
) -> None:
    if depth > MAX_STATE_DIFF_DEPTH:
        raise ValueError("state nesting exceeds max depth; flatten or pass refs")
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        for key in sorted(set(before) | set(after), key=lambda k: str(k)):
            child = parts + [str(key)]
            if key not in before:
                added.append({"path": _format_path(child), "value": after[key]})
            elif key not in after:
                removed.append({"path": _format_path(child), "value": before[key]})
            else:
                _diff_nodes(before[key], after[key], child, added, removed, changed, depth + 1)
        return
    if isinstance(before, list) and isinstance(after, list):
        for index in range(max(len(before), len(after))):
            child = parts + [str(index)]
            if index >= len(before):
                added.append({"path": _format_path(child), "value": after[index]})
            elif index >= len(after):
                removed.append({"path": _format_path(child), "value": before[index]})
            else:
                _diff_nodes(before[index], after[index], child, added, removed, changed, depth + 1)
        return
    if _canonical_json(before) != _canonical_json(after):
        changed.append({
            "path": _format_path(parts),
            "before": before,
            "after": after,
        })


def diff_public_state(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    max_bytes: int = MAX_STATE_DIFF_BYTES,
) -> dict[str, Any]:
    """Return a deterministic structural delta of two JSON objects.

    Private/conversational keys are refused rather than projected.  The helper
    reports added, removed, and changed paths only.  It grants no authority and
    performs no I/O.
    """
    if not isinstance(before, Mapping) or not isinstance(after, Mapping):
        raise TypeError("before and after must be objects")
    if not isinstance(max_bytes, int) or max_bytes < 256:
        raise ValueError("max_bytes must be an integer >= 256")
    forbidden: set[str] = set()
    _collect_forbidden_keys(before, forbidden)
    _collect_forbidden_keys(after, forbidden)
    if forbidden:
        raise ValueError(
            "private or conversational fields are not accepted: "
            + ", ".join(sorted(forbidden))
        )

    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    _diff_nodes(before, after, [], added, removed, changed, 0)
    delta = {
        "added": added,
        "changed": changed,
        "removed": removed,
        "unchanged": not (added or removed or changed),
    }
    if len(_canonical_json(delta).encode("utf-8")) > max_bytes:
        raise ValueError("state delta exceeds max_bytes; store large payloads externally and pass refs")
    return delta


def _refuse_raw_conversation(obj: Mapping[str, Any]) -> None:
    forbidden = sorted(k for k in obj if str(k).lower() in _FORBIDDEN_CONTEXT_KEYS)
    if forbidden:
        raise ValueError(f"raw conversational context is not accepted: {', '.join(forbidden)}")


def _required_parent_mission_id(previous: Mapping[str, Any]) -> str:
    for key in ("mission_id", "mission"):
        value = previous.get(key)
        if isinstance(value, str) and value.strip():
            return value
    raise ValueError(
        "parent_mission_id is required for a true handoff; previous must include mission_id or mission"
    )


def _state_for_diff(obj: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = obj.get("current_state")
    if isinstance(nested, Mapping):
        return nested
    skip = {"changed_since_last_run", "parent_mission_id"}
    return {key: value for key, value in obj.items() if key not in skip}


def _pointer_paths(delta: Mapping[str, Any]) -> list[str]:
    paths: list[str] = []
    for kind in ("added", "changed", "removed"):
        for item in delta.get(kind) or []:
            path = item.get("path")
            if path:
                paths.append(f"{kind}:{path}")
    return paths


def compile_handoff_packet(
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
    *,
    max_bytes: int = MAX_CONTEXT_BYTES,
) -> dict[str, Any]:
    """Compile a continuation packet from previous and current public state.

    Thin composition: ``changed_since_last_run`` is derived as pointer-heavy
    paths from ``diff_public_state``, then the spine is packed with
    ``compile_context_packet``.  Caller-supplied deltas are ignored.  Does not
    invent mission fields.  ``parent_mission_id`` is required.
    """
    if not isinstance(previous, Mapping) or not isinstance(current, Mapping):
        raise TypeError("previous and current must be objects")
    _refuse_raw_conversation(previous)
    _refuse_raw_conversation(current)
    parent_mission_id = _required_parent_mission_id(previous)
    delta = diff_public_state(
        _state_for_diff(previous),
        _state_for_diff(current),
        max_bytes=max_bytes,
    )
    composed: dict[str, Any] = {"parent_mission_id": parent_mission_id}
    for key in _CONTEXT_FIELDS:
        if key in {"parent_mission_id", "changed_since_last_run"}:
            continue
        if key in current and current[key] not in (None, "", [], {}):
            composed[key] = current[key]
    paths = _pointer_paths(delta)
    if paths:
        composed["changed_since_last_run"] = paths
    return compile_context_packet(composed, max_bytes=max_bytes)


def _load_json(path: str) -> Any:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def context_pack_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile a bounded execution-context packet")
    parser.add_argument("input", help="JSON file or - for stdin")
    parser.add_argument("--max-bytes", type=int, default=MAX_CONTEXT_BYTES)
    args = parser.parse_args(argv)
    _write(compile_context_packet(_load_json(args.input), max_bytes=args.max_bytes))
    return 0


def cheap_route_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Choose the cheapest capable execution route")
    parser.add_argument("input", help="JSON array of candidate routes or - for stdin")
    parser.add_argument("--min-success", type=float, default=0.8)
    args = parser.parse_args(argv)
    candidates = _load_json(args.input)
    if not isinstance(candidates, list):
        raise SystemExit("input must be a JSON array")
    _write(choose_cheapest_capable_route(candidates, minimum_success_probability=args.min_success).as_dict())
    return 0


def proof_card_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Project a record into a public-safe proof card")
    parser.add_argument("input", help="JSON file or - for stdin")
    parser.add_argument("--allow", action="append", default=[], help="additional top-level field to allow")
    args = parser.parse_args(argv)
    _write(public_proof_card(_load_json(args.input), extra_allow=args.allow))
    return 0


def state_diff_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute a public-safe structural state delta")
    parser.add_argument("before", help="JSON object file or - for stdin")
    parser.add_argument("after", help="JSON object file")
    parser.add_argument("--max-bytes", type=int, default=MAX_STATE_DIFF_BYTES)
    args = parser.parse_args(argv)
    if args.before == "-" and args.after == "-":
        raise SystemExit("before and after cannot both read stdin")
    before = _load_json(args.before)
    after = _load_json(args.after)
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise SystemExit("before and after must be JSON objects")
    _write(diff_public_state(before, after, max_bytes=args.max_bytes))
    return 0


def handoff_pack_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile a public-safe agent-to-agent handoff packet")
    parser.add_argument("previous", help="JSON object file or - for stdin")
    parser.add_argument("current", help="JSON object file")
    parser.add_argument("--max-bytes", type=int, default=MAX_CONTEXT_BYTES)
    args = parser.parse_args(argv)
    if args.previous == "-" and args.current == "-":
        raise SystemExit("previous and current cannot both read stdin")
    previous = _load_json(args.previous)
    current = _load_json(args.current)
    if not isinstance(previous, dict) or not isinstance(current, dict):
        raise SystemExit("previous and current must be JSON objects")
    _write(compile_handoff_packet(previous, current, max_bytes=args.max_bytes))
    return 0
