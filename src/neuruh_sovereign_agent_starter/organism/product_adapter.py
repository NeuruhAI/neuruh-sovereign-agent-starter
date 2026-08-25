"""Product World Adapter contract — how a commercial system becomes a bounded agent domain (a World).

A product declares WHAT it observes, WHAT it wants, and WHAT it costs. It never
declares how much authority that deserves: consequence is classified centrally
(governance risk tiers), identity is bound centrally (world_id inside every
binding key), learning is measured centrally (one calibration grammar).
(T44 §07 World Pack rule, T45 §01 world contract, carried here as data.)

Nothing in this module touches a live product. Every adapter is
`adapter_status: DECLARED_NOT_WIRED`; protected builds are declared from
identity evidence only. The DeedSonar/NC example shows why the governance rail
matters: researching a property never implies seller-contact authority, phone
evidence never implies consent, a signal never implies transaction authority.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import contracts as C
from .world import world_seed_spec

ADAPTER_STATUSES = ("DECLARED_NOT_WIRED", "FIXTURE_PROVEN", "LIVE_PROVEN")


def product_world_adapter(*, product_id: str, display_name: str, world_type: str, custody: str, protected: bool,
                          subject_types: Sequence[Mapping[str, Any]], sources: Sequence[Mapping[str, Any]],
                          recipes: Sequence[Mapping[str, Any]], capabilities: Sequence[Mapping[str, Any]],
                          agents: Sequence[Mapping[str, Any]], outcome_sensors: Sequence[Mapping[str, Any]],
                          economics: Mapping[str, Any], policy: Mapping[str, Any], created_at: str,
                          adapter_status: str = "DECLARED_NOT_WIRED", notes: str = "") -> dict[str, Any]:
    C._in(adapter_status, ADAPTER_STATUSES, "adapter_status")
    caps = {c["operation"]: c for c in capabilities}
    for c in caps.values():
        if c["action_class"] not in C.ACTION_CLASS_TIERS:
            raise C.ContractError(f"{product_id}: unknown action class {c['action_class']!r} for {c['operation']!r}")
        c["risk_tier"] = C.ACTION_CLASS_TIERS[c["action_class"]]
    for a in agents:
        unknown = sorted(set(a["operations"]) - set(caps))
        if unknown:
            raise C.ContractError(f"{product_id}: agent {a['role']} references undeclared capabilities {unknown}")
    return C.seal("product_world_adapter", {
        "product_id": product_id, "display_name": display_name, "world_type": world_type, "custody": custody,
        "protected": bool(protected), "adapter_status": adapter_status, "subject_types": [dict(s) for s in subject_types],
        "sources": [dict(s) for s in sources], "recipes": [dict(r) for r in recipes],
        "capabilities": [dict(c) for c in caps.values()], "agents": [dict(a) for a in agents],
        "outcome_sensors": [dict(o) for o in outcome_sensors], "economics": dict(economics), "policy": dict(policy),
        "shared_organs_never_reimplemented": ["memory", "inference(IAR)", "governance", "execution(AXON/governed-exec)",
                                             "receipts", "learning(017/019/020)", "command(cockpit)"],
        "declares_authority": False, "notes": notes, "created_at": created_at,
    }, id_field="product_id")


def authorizes(adapter: Mapping[str, Any], *, role: str, operation: str) -> bool | str:
    """Does the adapter's roster give this role this operation? Unknown role -> unknown."""
    for a in adapter["agents"]:
        if a["role"] == role:
            return operation in a["operations"]
    return C.UNKNOWN


def consent_fact(evidence: Sequence[Mapping[str, Any]]) -> bool | str:
    """Phone evidence never implies consent. Only an explicit consent evidence record can make it True."""
    kinds = {e.get("source_type") for e in evidence}
    if "consent_record" in kinds:
        return True
    if "consent_revoked" in kinds or "dnc_match" in kinds:
        return False
    return C.UNKNOWN


def seed_for_adapter(adapter: Mapping[str, Any], *, seed_id: str, seed_version: str, clock_start: str,
                     world_mode: str = "synthetic") -> dict[str, Any]:
    """Compile an adapter into a WorldSeedSpec (synthetic by default; no connectors, no live data)."""
    manifest = {"schema_version": "neuruh.capability-registry.v0.1", "capabilities": [
        {"operation": c["operation"], "kind": c.get("kind", "other"), "requires_receipt": True,
         "requires_precondition": c["risk_tier"] in ("R3", "R4", "R5"), "allowed_target_types": [c.get("target_type", "subject")],
         "arg_schema": c.get("arg_schema", {"subject_id": {"type": "string", "required": True, "max_length": 128}})}
        for c in adapter["capabilities"]]}
    return world_seed_spec(
        seed_id=seed_id, seed_version=seed_version, world_type=adapter["world_type"], world_mode=world_mode,
        purpose=f"{adapter['display_name']} as a bounded agent domain (adapter {adapter['adapter_status']})",
        policy=adapter["policy"], capability_manifest=manifest,
        agent_roster=[{"agent_id": f"{adapter['product_id']}-{a['role']}", "roles": [a["role"]]} for a in adapter["agents"]],
        grant_templates=[{"subject": f"{adapter['product_id']}-{a['role']}", "operations": a["operations"],
                          "forbidden_operations": sorted({c["operation"] for c in adapter["capabilities"]} - set(a["operations"])),
                          "max_spend_usd": 0} for a in adapter["agents"]],
        capability_budget={"max_spend_usd": 0, "max_actions": 100}, memory_namespace=f"mem/{adapter['product_id']}",
        evidence_namespace=f"ev/{adapter['product_id']}", fixtures={"clock_start": clock_start, "adapter_digest": adapter["digest"]},
        initial_canonical_state={"stage": "sandbox", "state": {"product": adapter["product_id"], "version": 1}},
        tools_available=sorted({c.get("tool", c["operation"]) for c in adapter["capabilities"]}),
        action_class_map={c["operation"]: c["action_class"] for c in adapter["capabilities"]},
        signal_registry=[s["source_id"] for s in adapter["sources"]], recipe_registry=[r["recipe_id"] for r in adapter["recipes"]])


# ------------------------------------------------------------------ the nine product worlds (declarations only)
_AT = "2026-08-24T00:00:00Z"
_POLICY = {"policy_id": "product-default", "blocked_domains": ["production"],
           "approval_tags": ["external_message", "spend", "production_write", "personal_data"], "max_spend": 0}


def _cap(op, cls, **kw):
    return {"operation": op, "action_class": cls, **kw}


def deedsonar_nc_adapter() -> dict[str, Any]:
    """WORLD: DeedSonar / NC — seven agents, separated capabilities. Synthetic declaration only."""
    caps = [
        _cap("source.observe", "read", kind="network", tool="web_fetch", target_type="public_record"),
        _cap("identity.resolve", "query", kind="data", tool="resolver"),
        _cap("signal.generate", "artifact_write", kind="data", tool="signal_writer"),
        _cap("recipe.evaluate", "query", kind="data", tool="recipe_engine"),
        _cap("research.property", "retrieval", kind="data", tool="laric"),
        _cap("phone.enrich", "query", kind="network", tool="enrichment"),
        _cap("seller.contact", "external_message", kind="network", tool="twilio_send"),
        _cap("offer.draft", "report_write", kind="data", tool="doc_writer"),
        _cap("transaction.execute", "spend", kind="network", tool="esign_send"),
    ]
    agents = [
        {"role": "source", "operations": ["source.observe"]},
        {"role": "identity", "operations": ["identity.resolve"]},
        {"role": "signal", "operations": ["signal.generate", "recipe.evaluate"]},
        {"role": "recipe", "operations": ["recipe.evaluate"]},
        {"role": "research", "operations": ["research.property", "phone.enrich"]},
        {"role": "acquisition", "operations": ["offer.draft", "seller.contact"]},
        {"role": "transaction", "operations": ["transaction.execute"]},
    ]
    return product_world_adapter(
        product_id="deedsonar-nc", display_name="DeedSonar / NC", world_type="real-estate-acquisition",
        custody="NeuruhAI/deedsonar main 8d1a31a (PRODUCTION; PROTECTED — declared from identity evidence only)",
        protected=True, subject_types=[{"type": "property", "identity": "parcel_apn", "resolver": "county_fips+apn"},
                                       {"type": "party", "identity": "party_key", "resolver": "name+county+evidence"}],
        sources=[{"source_id": "nc_public_records", "kind": "bulk_file", "access_mode": "automated", "cadence": "weekly"},
                 {"source_id": "ncsbe_voter", "kind": "bulk_file", "access_mode": "bulk_dua", "cadence": "weekly"}],
        recipes=[{"recipe_id": "stalled_tax_foreclosure_heirship", "version": "1.4.0"}],
        capabilities=caps, agents=agents,
        outcome_sensors=[{"metric_key": "owner_response", "tier": "BUSINESS", "unit": "boolean", "observation_window_days": 30}],
        economics={"value_unit": "resolved_acquirable_parcel", "calibration_key_template": "{world}:{recipe_id}:{owner_class}"},
        policy={**_POLICY, "policy_id": "deedsonar-nc", "allowed_tools": [c["operation"] for c in caps]}, created_at=_AT,
        notes="research.property never implies seller.contact; phone.enrich evidence never implies consent; signal.generate never implies transaction.execute")


def _simple(product_id, name, world_type, custody, protected, caps, agents, notes=""):
    return product_world_adapter(
        product_id=product_id, display_name=name, world_type=world_type, custody=custody, protected=protected,
        subject_types=[{"type": "subject", "identity": "subject_id", "resolver": "per-world"}], sources=[], recipes=[],
        capabilities=caps, agents=agents, outcome_sensors=[{"metric_key": "process_ok", "tier": "PROCESS", "unit": "boolean"}],
        economics={"value_unit": "per-world", "calibration_key_template": "{world}:{recipe_id}"},
        policy={**_POLICY, "policy_id": product_id, "allowed_tools": [c["operation"] for c in caps]}, created_at=_AT, notes=notes)


def all_adapters() -> dict[str, dict[str, Any]]:
    a = {}
    a["deedsonar-nc"] = deedsonar_nc_adapter()
    a["property-intelligence"] = _simple(
        "property-intelligence", "Property Intelligence", "real-estate-intelligence",
        "~/neuruh-worktrees/deedsonar-property-intelligence-20260824 feat/property-intelligence-engine-20260824 (PROTECTED, active Grok lane)", True,
        [_cap("query.compile", "query", tool="property_query"), _cap("resultset.read", "retrieval", tool="result_set"),
         _cap("report.render", "report_write", tool="renderer")],
        [{"role": "query", "operations": ["query.compile", "resultset.read"]}, {"role": "reporter", "operations": ["report.render"]}],
        "one engine / three shells; adapter waits for the Grok lane to close")
    a["findsellprofit"] = _simple("findsellprofit", "FindSellProfit", "resale-merchant-os", "NeuruhAI/findsellprofit codex/autonomous-merchant-os-20260821 771527a", False,
        [_cap("listing.observe", "read", tool="marketplace_read"), _cap("valuation.score", "query", tool="valuer"),
         _cap("buy.decide", "artifact_write", tool="decision_writer"), _cap("purchase.execute", "spend", tool="checkout")],
        [{"role": "scout", "operations": ["listing.observe", "valuation.score"]}, {"role": "buyer", "operations": ["buy.decide"]},
         {"role": "treasurer", "operations": ["purchase.execute"]}], "buy.decide never implies purchase.execute")
    a["bookeit"] = _simple("bookeit", "Bookeit", "agentic-commerce", "Jeramie-Hicks/bookeit codex/agentic-commerce-20260821 8390532", False,
        [_cap("need.structure", "query", tool="structurer"), _cap("supply.qualify", "retrieval", tool="supply_index"),
         _cap("hold.request", "artifact_write", tool="hold_writer"), _cap("dispatch.execute", "external_message", tool="dispatch")],
        [{"role": "concierge", "operations": ["need.structure", "supply.qualify", "hold.request"]}, {"role": "dispatcher", "operations": ["dispatch.execute"]}],
        "holds a human authorization before dispatch; outcome feeds the calibration seam")
    a["neuruh-factory"] = _simple("neuruh-factory", "Neuruh Factory", "software-manufacturing", "NeuruhAI/neuruh-factory (main ambiguity UA-02)", False,
        [_cap("contract.compile", "artifact_write", tool="factory"), _cap("repo.scaffold", "repo_edit", tool="factory"),
         _cap("verify.run", "test_run", tool="verifier"), _cap("release.package", "build", tool="packager")],
        [{"role": "architect", "operations": ["contract.compile"]}, {"role": "builder", "operations": ["repo.scaffold", "verify.run"]},
         {"role": "releaser", "operations": ["release.package"]}])
    a["venture-factory"] = _simple("venture-factory", "Venture Factory", "venture-creation", "~/neuruh-worktrees/neuruh-autonomous-venture-factory-20260821 (ACTIVE_DEVELOPMENT)", False,
        [_cap("opportunity.scan", "read", tool="scanner"), _cap("venture.blueprint", "artifact_write", tool="blueprinter"),
         _cap("venture.spawn", "qualified_adoption", tool="factory")],
        [{"role": "scout", "operations": ["opportunity.scan"]}, {"role": "planner", "operations": ["venture.blueprint"]}, {"role": "founder-proxy", "operations": ["venture.spawn"]}],
        "venture.spawn is R3: founder qualification required")
    a["liquidity-engine"] = _simple("liquidity-engine", "Liquidity Engine + Signal Market", "liquidity-routing", "NeuruhAI/neuruh-liquidity-engine 7f2af00 (V1 proven, local)", False,
        [_cap("signal.verify", "query", tool="verifier"), _cap("opportunity.underwrite", "artifact_write", tool="underwriter"),
         _cap("route.rank", "query", tool="router"), _cap("offer.authorize", "qualified_adoption", tool="desk"), _cap("close.synthetic", "temp_write", tool="court")],
        [{"role": "verifier", "operations": ["signal.verify"]}, {"role": "underwriter", "operations": ["opportunity.underwrite", "route.rank"]},
         {"role": "desk", "operations": ["offer.authorize", "close.synthetic"]}], "V1 moves no money by construction")
    a["curbclaim"] = _simple("curbclaim", "CurbClaim", "hyperlocal-recovery", "NeuruhAI/curbclaim codex/hyperlocal-recovery-20260821 c73d5ac", False,
        [_cap("item.observe", "read", tool="intake"), _cap("route.value", "query", tool="router"), _cap("claim.dispatch", "external_message", tool="dispatch")],
        [{"role": "intake", "operations": ["item.observe", "route.value"]}, {"role": "dispatcher", "operations": ["claim.dispatch"]}])
    a["proofos"] = _simple("proofos", "ProofOS", "commercial-twin", "NeuruhAI/neuruh-proof-os codex/autonomous-proof-os-20260821 c53cc3f", False,
        [_cap("evidence.tape", "read", tool="tape"), _cap("twin.build", "artifact_write", tool="twin"), _cap("offer.compile", "report_write", tool="composer")],
        [{"role": "analyst", "operations": ["evidence.tape", "twin.build"]}, {"role": "composer", "operations": ["offer.compile"]}],
        "compiles an offer draft then STOPS")
    return a
