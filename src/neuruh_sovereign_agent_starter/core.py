from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import uuid

from importlib.metadata import PackageNotFoundError, version as metadata_version

from neuruh_agent_run_manifest import (
    ArtifactRef,
    ComponentRef,
    DecisionRef,
    EvidenceRef,
    ExecutionRef,
    InferenceRef,
    PolicyRef,
    ReceiptRef,
    RunManifest,
    canonical_json,
    sha256_ref,
)
from neuruh_agent_receipt import (
    GENESIS,
    seal_entry,
    verify_ledger,
)
from neuruh_capability_registry import CapabilityError, CapabilityRegistry
from neuruh_governed_exec import (
    CommandAllowlist,
    CommandSpec,
    GovernedExecutor,
    WorktreeGuard,
)
from neuruh_inference_health import Backend, InferenceHealthAdapter, http_probe
from neuruh_policy_gate import Action, Decision, Policy, PolicyGate

COMPONENT_DISTRIBUTIONS = (
    "neuruh-agent-run-manifest",
    "neuruh-agent-receipt",
    "neuruh-governed-exec",
    "neuruh-policy-gate",
    "neuruh-capability-registry",
    "neuruh-inference-health",
    "neuruh-sovereign-agent-starter",
)


def _component_version(distribution: str) -> str:
    """Report the installed version so the manifest records what actually ran."""
    try:
        return metadata_version(distribution)
    except PackageNotFoundError:
        return "unknown"


SCHEMA_VERSION = "neuruh.sovereign-agent-starter.v0.1"


class StarterError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _exact_keys(
    raw: Mapping[str, Any], required: set[str], optional: set[str], context: str
) -> None:
    missing = sorted(required - set(raw))
    unknown = sorted(set(raw) - required - optional)
    if missing:
        raise StarterError(
            "E_CONFIG", f"{context} missing field(s): {', '.join(missing)}"
        )
    if unknown:
        raise StarterError(
            "E_CONFIG", f"{context} contains unknown field(s): {', '.join(unknown)}"
        )


def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StarterError("E_CONFIG", f"{name} must be a non-empty string")
    return value


def _bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise StarterError("E_CONFIG", f"{name} must be boolean")
    return value


def _float(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StarterError("E_CONFIG", f"{name} must be numeric")
    return float(value)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _loopback_only(base_url: str) -> None:
    p = urlparse(base_url)
    if p.scheme not in {"http", "https"}:
        raise StarterError(
            "E_INFERENCE_ENDPOINT", "inference endpoint must use http/https"
        )
    if p.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise StarterError(
            "E_INFERENCE_ENDPOINT", "starter inference is loopback-only in v0.1"
        )


@dataclass(frozen=True)
class InferenceConfig:
    backends: tuple[Backend, ...]
    required: bool
    prompt: str | None
    timeout_seconds: float


@dataclass(frozen=True)
class ActionConfig:
    action_id: str
    domain: str
    operation: str
    args: Mapping[str, Any]
    tags: tuple[str, ...]
    spend: float


@dataclass(frozen=True)
class ExecutionBinding:
    operation: str
    bin: str
    argv: tuple[str, ...]
    cwd: str


@dataclass(frozen=True)
class StarterConfig:
    agent_id: str
    mission: str
    sandbox_root: str
    policy: Mapping[str, Any]
    capability_manifest: Mapping[str, Any]
    inference: InferenceConfig
    action: ActionConfig
    execution_binding: ExecutionBinding
    dry_run: bool

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "StarterConfig":
        _exact_keys(
            raw,
            {
                "schema_version",
                "agent_id",
                "mission",
                "sandbox_root",
                "policy",
                "capability_manifest",
                "inference",
                "action",
                "execution_binding",
                "dry_run",
            },
            set(),
            "config",
        )
        if raw["schema_version"] != SCHEMA_VERSION:
            raise StarterError("E_CONFIG", "unsupported schema_version")
        for k in (
            "policy",
            "capability_manifest",
            "inference",
            "action",
            "execution_binding",
        ):
            if not isinstance(raw[k], Mapping):
                raise StarterError("E_CONFIG", f"{k} must be an object")

        inf = raw["inference"]
        _exact_keys(
            inf,
            {"backends", "required", "prompt", "timeout_seconds"},
            set(),
            "inference",
        )
        if not isinstance(inf["backends"], list) or not inf["backends"]:
            raise StarterError(
                "E_CONFIG", "inference.backends must be a non-empty array"
            )
        backends = []
        for item in inf["backends"]:
            if not isinstance(item, Mapping):
                raise StarterError("E_CONFIG", "backend must be an object")
            _exact_keys(
                item,
                {"name", "kind", "base_url", "model", "health_paths"},
                set(),
                "backend",
            )
            if not isinstance(item["health_paths"], list) or not all(
                isinstance(x, str) for x in item["health_paths"]
            ):
                raise StarterError(
                    "E_CONFIG", "health_paths must be an array of strings"
                )
            kind = _nonempty(item["kind"], "backend kind")
            base_url = _nonempty(item["base_url"], "base_url")
            if kind != "local":
                raise StarterError(
                    "E_INFERENCE_ENDPOINT",
                    "sovereign starter v0.1 accepts local inference backends only",
                )
            _loopback_only(base_url)
            backends.append(
                Backend.create(
                    _nonempty(item["name"], "backend name"),
                    kind,
                    base_url,
                    model=item["model"],
                    health_paths=item["health_paths"],
                )
            )
        prompt = inf["prompt"]
        if prompt is not None:
            prompt = _nonempty(prompt, "prompt")
        timeout = _float(inf["timeout_seconds"], "inference.timeout_seconds")
        if timeout <= 0 or timeout > 30:
            raise StarterError(
                "E_CONFIG", "inference.timeout_seconds must be > 0 and <= 30"
            )
        inference = InferenceConfig(
            tuple(backends),
            _bool(inf["required"], "inference.required"),
            prompt,
            timeout,
        )

        action_raw = raw["action"]
        _exact_keys(
            action_raw,
            {"action_id", "domain", "operation", "args", "tags", "spend"},
            set(),
            "action",
        )
        if not isinstance(action_raw["args"], Mapping):
            raise StarterError("E_CONFIG", "action.args must be an object")
        if not isinstance(action_raw["tags"], list) or not all(
            isinstance(x, str) for x in action_raw["tags"]
        ):
            raise StarterError("E_CONFIG", "action.tags must be an array of strings")
        action = ActionConfig(
            _nonempty(action_raw["action_id"], "action_id"),
            _nonempty(action_raw["domain"], "domain"),
            _nonempty(action_raw["operation"], "operation"),
            dict(action_raw["args"]),
            tuple(action_raw["tags"]),
            _float(action_raw["spend"], "spend"),
        )

        binding_raw = raw["execution_binding"]
        _exact_keys(
            binding_raw, {"operation", "bin", "argv", "cwd"}, set(), "execution_binding"
        )
        if not isinstance(binding_raw["argv"], list) or not all(
            isinstance(x, str) for x in binding_raw["argv"]
        ):
            raise StarterError(
                "E_CONFIG", "execution_binding.argv must be an array of strings"
            )
        binding = ExecutionBinding(
            _nonempty(binding_raw["operation"], "binding operation"),
            _nonempty(binding_raw["bin"], "binding bin"),
            tuple(binding_raw["argv"]),
            _nonempty(binding_raw["cwd"], "binding cwd"),
        )
        if binding.operation != action.operation:
            raise StarterError(
                "E_BINDING",
                "execution binding operation must exactly match action operation",
            )

        policy_raw = raw["policy"]
        _exact_keys(
            policy_raw,
            {
                "policy_id",
                "blocked_domains",
                "allowed_tools",
                "approval_tags",
                "max_spend",
            },
            set(),
            "policy",
        )
        for k in ("blocked_domains", "allowed_tools", "approval_tags"):
            if not isinstance(policy_raw[k], list) or not all(
                isinstance(x, str) for x in policy_raw[k]
            ):
                raise StarterError(
                    "E_CONFIG", f"policy.{k} must be an array of strings"
                )
        _float(policy_raw["max_spend"], "policy.max_spend")

        return cls(
            agent_id=_nonempty(raw["agent_id"], "agent_id"),
            mission=_nonempty(raw["mission"], "mission"),
            sandbox_root=_nonempty(raw["sandbox_root"], "sandbox_root"),
            policy=dict(policy_raw),
            capability_manifest=dict(raw["capability_manifest"]),
            inference=inference,
            action=action,
            execution_binding=binding,
            dry_run=_bool(raw["dry_run"], "dry_run"),
        )


@dataclass(frozen=True)
class StarterRunResult:
    manifest: RunManifest
    receipts: tuple[dict[str, Any], ...]
    decision: Mapping[str, Any]
    execution: Mapping[str, Any] | None
    inference_output: str | None


InferenceCall = Callable[[Backend, str, float], str]
Probe = Callable[[str, float], bool]


def openai_compatible_infer(
    backend: Backend, prompt: str, timeout_seconds: float
) -> str:
    _loopback_only(backend.base_url)
    if not backend.model:
        raise StarterError("E_INFERENCE", "active backend must declare a model")
    payload = json.dumps(
        {
            "model": backend.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
    ).encode("utf-8")
    req = Request(
        backend.base_url + "/v1/chat/completions",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "neuruh-sovereign-agent/0.1",
        },
    )
    try:
        with urlopen(req, timeout=timeout_seconds) as response:
            raw = json.loads(response.read().decode("utf-8"))
        text = raw["choices"][0]["message"]["content"]
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise StarterError("E_INFERENCE", f"local inference failed: {exc}") from exc
    return _nonempty(text, "inference output")


def _health_dict(report) -> dict[str, Any]:
    return {
        "enabled": report.enabled,
        "active_backend": report.active_backend,
        "active_model": report.active_model,
        "degraded_reason": report.degraded_reason,
        "backends": [
            {"name": x.name, "healthy": x.healthy, "checked_path": x.checked_path}
            for x in report.backends
        ],
    }


def _decision_receipt(
    run_id: str, observed_at: str, decision: Mapping[str, Any], action_digest: str
) -> dict[str, Any]:
    return {
        "schema_version": "neuruh.agent-receipt.v1alpha1",
        "receipt_type": "decision",
        "authority": "governance-decision",
        "observed_at": observed_at,
        "subject": run_id,
        "correlation_id": run_id,
        "causation_id": decision["action_id"],
        "payload": {"decision": dict(decision), "action_digest": action_digest},
    }


def _observation_receipt(
    run_id: str, observed_at: str, payload: Mapping[str, Any], causation_id: str
) -> dict[str, Any]:
    return {
        "schema_version": "neuruh.agent-receipt.v1alpha1",
        "receipt_type": "observation",
        "authority": "observation",
        "observed_at": observed_at,
        "subject": run_id,
        "correlation_id": run_id,
        "causation_id": causation_id,
        "payload": dict(payload),
    }


def _execution_receipt(
    run_id: str, observed_at: str, action_id: str, payload: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": "neuruh.agent-receipt.v1alpha1",
        "receipt_type": "execution",
        "authority": "execution-evidence",
        "observed_at": observed_at,
        "subject": run_id,
        "correlation_id": run_id,
        "causation_id": action_id,
        "payload": dict(payload),
    }


def _seal_receipts(unsealed: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    prev = GENESIS
    out = []
    for seq, item in enumerate(unsealed):
        sealed = seal_entry(item, prev_hash=prev, seq=seq)
        out.append(sealed)
        prev = sealed["entry_hash"]
    verify_ledger(out)
    return tuple(out)


def run(
    config: StarterConfig,
    *,
    probe: Probe = http_probe,
    infer: InferenceCall | None = None,
    run_id: str | None = None,
    now: Callable[[], str] = utc_now,
) -> StarterRunResult:
    started = now()
    run_id = run_id or "run-" + uuid.uuid4().hex

    # Capability declaration is evaluated before any policy or execution.
    try:
        registry = CapabilityRegistry.from_manifest(config.capability_manifest)
        registry.validate_args(config.action.operation, config.action.args)
        capability = registry.resolve(config.action.operation)
    except CapabilityError as exc:
        raise StarterError(exc.code, str(exc)) from exc
    if capability.kind != "process":
        raise StarterError(
            "E_CAPABILITY_KIND",
            "starter v0.1 execution binding requires a process capability",
        )

    policy = Policy.create(
        config.policy["policy_id"],
        blocked_domains=config.policy["blocked_domains"],
        allowed_tools=config.policy["allowed_tools"],
        approval_tags=config.policy["approval_tags"],
        max_spend=config.policy["max_spend"],
    )
    decision_record = PolicyGate(policy).evaluate(
        Action.create(
            config.action.action_id,
            config.action.domain,
            config.action.operation,
            tags=config.action.tags,
            spend=config.action.spend,
        )
    )
    decision = decision_record.to_dict()
    decision_digest = sha256_ref(canonical_json(decision))
    action_digest = sha256_ref(
        canonical_json(
            {
                "action_id": config.action.action_id,
                "domain": config.action.domain,
                "operation": config.action.operation,
                "args": config.action.args,
                "tags": list(config.action.tags),
                "spend": config.action.spend,
            }
        )
    )

    # DENY / ESCALATE are terminal before any model/network probe. This keeps
    # policy refusal side-effect free.
    unsealed = [_decision_receipt(run_id, started, decision, action_digest)]
    inference_output = None
    execution_data = None
    outputs = []
    execution_refs = []
    status = None
    health = None
    health_payload = {
        "enabled": False,
        "active_backend": None,
        "active_model": None,
        "degraded_reason": "not_used_by_policy",
        "backends": [],
    }
    health_digest = sha256_ref(canonical_json(health_payload))
    inf_health = "not_used"

    if decision_record.decision == Decision.DENY:
        status = "denied"
    elif decision_record.decision == Decision.ESCALATE:
        status = "escalated"
    else:
        health = InferenceHealthAdapter(
            config.inference.backends,
            probe=probe,
            timeout_seconds=config.inference.timeout_seconds,
        ).report()
        health_payload = _health_dict(health)
        health_digest = sha256_ref(canonical_json(health_payload))
        inf_health = (
            "unavailable"
            if health.active_backend is None
            else ("degraded" if health.degraded_reason else "healthy")
        )
        unsealed.append(
            _observation_receipt(
                run_id,
                started,
                {"inference_health": health_payload, "sha256": health_digest},
                config.action.action_id,
            )
        )
        if config.inference.required and health.active_backend is None:
            status = "failed"
        if config.inference.prompt is not None:
            if health.active_backend is None:
                if config.inference.required:
                    status = "failed"
            else:
                active = next(
                    b
                    for b in config.inference.backends
                    if b.name == health.active_backend
                )
                inference_output = (infer or openai_compatible_infer)(
                    active, config.inference.prompt, config.inference.timeout_seconds
                )
                inf_digest = sha256_ref(inference_output)
                unsealed.append(
                    _observation_receipt(
                        run_id,
                        now(),
                        {
                            "inference_output_sha256": inf_digest,
                            "backend": active.name,
                            "model": active.model,
                        },
                        config.action.action_id,
                    )
                )
                outputs.append(
                    ArtifactRef("inference-output", inf_digest, "text/plain")
                )

        if status is None:
            allowlist = CommandAllowlist(
                [
                    CommandSpec.from_parts(
                        config.execution_binding.bin, config.execution_binding.argv
                    )
                ]
            )
            guard = WorktreeGuard([config.sandbox_root])
            executor = GovernedExecutor(allowlist, guard)
            result = executor.run(
                config.execution_binding.bin,
                config.execution_binding.argv,
                cwd=config.execution_binding.cwd,
                dry_run=config.dry_run,
            )
            execution_data = {
                "ok": result.ok,
                "returncode": result.returncode,
                "code": result.code,
                "bin": result.bin,
                "args": list(result.args),
                "cwd": result.cwd,
                "stdout_sha256": sha256_ref(result.stdout),
                "stderr_sha256": sha256_ref(result.stderr),
            }
            execution_digest = sha256_ref(canonical_json(execution_data))
            exec_receipt_payload = {
                "code": result.code,
                "returncode": result.returncode,
                "stdout_sha256": execution_data["stdout_sha256"],
                "stderr_sha256": execution_data["stderr_sha256"],
                "dry_run": config.dry_run,
                "governance_decision_sha256": decision_digest,
            }
            unsealed.append(
                _execution_receipt(
                    run_id, now(), config.action.action_id, exec_receipt_payload
                )
            )
            status = (
                "dry_run"
                if config.dry_run and result.ok
                else ("completed" if result.ok else "failed")
            )
            if result.stdout:
                outputs.append(
                    ArtifactRef(
                        "execution-stdout", sha256_ref(result.stdout), "text/plain"
                    )
                )
            # receipt id is assigned after sealing; current execution receipt is last item.
            execution_refs.append((execution_digest, result.code, status))

    receipts = _seal_receipts(unsealed)
    receipt_refs = tuple(
        ReceiptRef(f"receipt-{r['seq']}", r["seq"], r["entry_hash"]) for r in receipts
    )

    executions = []
    if execution_refs:
        digest, code, run_status = execution_refs[0]
        receipt_id = f"receipt-{receipts[-1]['seq']}"
        exec_status = (
            "dry_run"
            if config.dry_run and code == "DRY_RUN"
            else ("executed" if execution_data and execution_data["ok"] else "failed")
        )
        executions.append(
            ExecutionRef(
                "execution-1",
                config.action.operation,
                exec_status,
                config.action.action_id,
                receipt_id,
                digest,
            )
        )

    components = tuple(
        ComponentRef(name, _component_version(name)) for name in COMPONENT_DISTRIBUTIONS
    )
    evidence = []
    if inf_health != "not_used":
        evidence.append(EvidenceRef("inference-health", health_digest, "observed"))
    if inference_output is not None:
        evidence.append(
            EvidenceRef("inference-output", sha256_ref(inference_output), "observed")
        )

    manifest = RunManifest(
        run_id=run_id,
        actor_id=config.agent_id,
        mission=config.mission,
        started_at=started,
        ended_at=now(),
        status=status,
        components=components,
        policy=PolicyRef(policy.policy_id, policy.version),
        inference=InferenceRef(
            health.active_backend if health else None,
            health.active_model if health else None,
            inf_health,
        ),
        inputs=(),
        evidence=tuple(evidence),
        decisions=(
            DecisionRef(
                config.action.action_id,
                decision["decision"],
                decision["policy_version"],
                decision_digest,
            ),
        ),
        executions=tuple(executions),
        receipts=receipt_refs,
        outputs=tuple(outputs),
    ).seal()
    # Independent manifest verifier pass before anything is returned.
    RunManifest.from_mapping(manifest.to_dict())
    return StarterRunResult(
        manifest, receipts, decision, execution_data, inference_output
    )
