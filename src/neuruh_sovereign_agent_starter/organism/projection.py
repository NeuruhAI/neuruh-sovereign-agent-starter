"""Reversible Markdown projection of a World (Obsidian / vault authoring surface).

    Worlds/<world-id>/{WORLD,MANIFEST,AGENTS,POLICIES,EVIDENCE,RECIPES,TASKS,RECEIPTS,OUTCOMES,LEARNING,STATE}.md

Markdown is a PROJECTION of canonical machine-readable state, never the state
itself. Each file carries a human-readable summary followed by exactly one
fenced ```json block holding the canonical JSON of that section, so
`parse(project(world)) == sections(world)` — the projection is reversible
without Obsidian and without any YAML/Markdown library.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

from neuruh_agent_run_manifest import canonical_json, sha256_ref

from .world import MEMORY_CLASSES, World

SECTIONS = ("WORLD", "MANIFEST", "AGENTS", "POLICIES", "EVIDENCE", "RECIPES", "TASKS", "RECEIPTS", "OUTCOMES",
            "LEARNING", "STATE")
PROJECTION_SCHEMA = "neuruh.organism.markdown-projection.v0.1"


def sections(world: World) -> dict[str, dict[str, Any]]:
    m = world.manifest
    intents = [r["payload"]["intent"] for r in world.receipts if r["payload"].get("event_type") == "intent_created"]
    return {
        "WORLD": {"world_id": m["world_id"], "world_type": m["world_type"], "world_mode": m["world_mode"],
                  "parent_world_id": m["parent_world_id"], "lineage": m["lineage"], "seed_id": m["seed_id"],
                  "seed_version": m["seed_version"], "seed_digest": m["seed_digest"], "purpose": m["purpose"],
                  "created_at": m["created_at"], "creator": m["creator"]},
        "MANIFEST": dict(m),
        "AGENTS": {"agents": [world.agents[k] for k in sorted(world.agents)]},
        "POLICIES": {"policy": world.seed["policy"], "grants": [world.grants[k] for k in sorted(world.grants)],
                     "capability_manifest": world.seed["capability_manifest"], "action_class_map": world.seed["action_class_map"]},
        "EVIDENCE": {"evidence": list(world.evidence), "evidence_namespace": m["evidence_namespace"]},
        "RECIPES": {"recipe_registry": world.seed["recipe_registry"], "signal_registry": world.seed["signal_registry"]},
        "TASKS": {"intents": intents},
        "RECEIPTS": {"tip": world.receipts_tip, "count": len(world.receipts),
                     "receipts": [{"seq": r["seq"], "receipt_type": r["receipt_type"], "event_type": r["payload"]["event_type"],
                                   "observed_at": r["observed_at"], "entry_hash": r["entry_hash"]} for r in world.receipts]},
        "OUTCOMES": {"outcomes": list(world.outcomes), "calibration": list(world.calibration)},
        "LEARNING": {"proposals": list(world.proposals), "authorizations": list(world.authorizations),
                     "promotions": list(world.promotions), "revisions": list(world.revisions)},
        "STATE": {"canonical": dict(world.canonical), "effective": world.effective, "state_summary": world.state_summary(),
                  "state_digest": world.state_digest(), "memory_classes": list(MEMORY_CLASSES)},
    }


def _human(name: str, data: Mapping[str, Any], world_id: str) -> str:
    lines = [f"# {name} — {world_id}", "", f"> projection: `{PROJECTION_SCHEMA}` · canonical JSON follows; edit the JSON block, not the prose.", ""]
    if name == "WORLD":
        lines += [f"- **world_id**: `{data['world_id']}`", f"- **mode**: {data['world_mode']}", f"- **type**: {data['world_type']}",
                  f"- **parent**: {data['parent_world_id']}", f"- **lineage**: {' → '.join(data['lineage']) or '(root)'}",
                  f"- **seed**: {data['seed_id']}@{data['seed_version']}", f"- **purpose**: {data['purpose']}"]
    elif name == "AGENTS":
        lines += ["| agent | roles |", "|---|---|"] + [f"| `{a['agent_id']}` | {', '.join(a['roles'])} |" for a in data["agents"]]
    elif name == "POLICIES":
        p = data["policy"]
        lines += [f"- policy `{p['policy_id']}` · blocked domains: {p.get('blocked_domains')} · allowed tools: {p.get('allowed_tools')}",
                  "", "| grant | subject | operations | forbidden | expires |", "|---|---|---|---|---|"]
        lines += [f"| `{g['grant_id']}` | {g['subject']} | {', '.join(g['operations'])} | {', '.join(g['forbidden_operations'])} | {g['expires_at']} |" for g in data["grants"]]
    elif name == "RECEIPTS":
        lines += [f"- chain tip `{data['tip']}` · {data['count']} receipts", "", "| seq | type | event | at |", "|---|---|---|---|"]
        lines += [f"| {r['seq']} | {r['receipt_type']} | {r['event_type']} | {r['observed_at']} |" for r in data["receipts"]]
    elif name == "STATE":
        c = data["canonical"]
        lines += [f"- canonical target `{c['target_id']}` · stage **{c['stage']}** · state digest `{c['state_digest']}`",
                  f"- effective state digest: `{(data['effective'] or {}).get('effective_state_digest')}`",
                  f"- world state digest: `{data['state_digest']}`"]
    elif name == "LEARNING":
        lines += [f"- proposals: {len(data['proposals'])} · authorizations: {len(data['authorizations'])} · promotions: {len(data['promotions'])} · revisions: {len(data['revisions'])}",
                  "- every proposal here is `is_canonical: false`; canonical state moves only through 033→020→034→035→036"]
    elif name == "OUTCOMES":
        lines += [f"- outcomes: {len(data['outcomes'])} · calibration records: {len(data['calibration'])}"]
    return "\n".join(lines) + "\n"


def project(world: World) -> dict[str, str]:
    out = {}
    secs = sections(world)
    for name in SECTIONS:
        data = secs[name]
        md = _human(name, data, world.world_id) + "\n```json\n" + json.dumps(data, indent=2, sort_keys=True) + "\n```\n"
        out[f"Worlds/{world.world_id}/{name}.md"] = md
    index = {"schema_version": PROJECTION_SCHEMA, "world_id": world.world_id,
             "files": {p: sha256_ref(v) for p, v in sorted(out.items())}, "state_digest": world.state_digest()}
    out[f"Worlds/{world.world_id}/PROJECTION.json"] = json.dumps(index, indent=2, sort_keys=True) + "\n"
    return out


def parse(files: Mapping[str, str]) -> dict[str, dict[str, Any]]:
    """Reverse projection: recover the canonical JSON of every section."""
    out = {}
    for path, text in files.items():
        if not path.endswith(".md"):
            continue
        name = path.rsplit("/", 1)[-1][:-3]
        start = text.index("\n```json\n") + len("\n```json\n")
        end = text.index("\n```\n", start)
        out[name] = json.loads(text[start:end])
    return out


def roundtrip_ok(world: World) -> bool:
    return canonical_json(parse(project(world))) == canonical_json(sections(world))
