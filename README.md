# Neuruh Sovereign Agent Starter

[![ci](https://github.com/NeuruhAI/neuruh-sovereign-agent-starter/actions/workflows/ci.yml/badge.svg)](https://github.com/NeuruhAI/neuruh-sovereign-agent-starter/actions/workflows/ci.yml)

A runnable reference agent composed from the Neuruh Public Commons libraries.

It demonstrates a governed run in which model output is evidence, never command authority:

```text
mission
  -> capability registry
  -> policy gate
  -> inference health / optional loopback model call
  -> exact predeclared execution binding
  -> governed exec
  -> evidence + Agent Receipt chain
  -> sealed Agent Run Manifest
```

## Requirements

Python 3.11 or newer. No API key, no account, and no model server.

Installing needs network access to fetch the pinned dependencies from GitHub. The example run itself makes no network calls.

## Install

```bash
git clone https://github.com/NeuruhAI/neuruh-sovereign-agent-starter.git
cd neuruh-sovereign-agent-starter
python -m venv .venv
source .venv/bin/activate
pip install .
```

Installing pulls each dependency from an immutable public tag; nothing resolves to a
branch or a local path.

| Component | Pinned release |
| --- | --- |
| [`neuruh-capability-registry`](https://github.com/NeuruhAI/neuruh-capability-registry) | `v0.1.2-alpha` |
| [`neuruh-policy-gate`](https://github.com/NeuruhAI/neuruh-policy-gate) | `v0.1.2-alpha` |
| [`neuruh-inference-health`](https://github.com/NeuruhAI/neuruh-inference-health) | `v0.1.2-alpha` |
| [`neuruh-governed-exec`](https://github.com/NeuruhAI/neuruh-governed-exec) | `v0.1.2-alpha` |
| [`neuruh-agent-receipt`](https://github.com/NeuruhAI/agent-receipt) | `v0.1.2-alpha` |
| [`neuruh-agent-run-manifest`](https://github.com/NeuruhAI/neuruh-agent-run-manifest) | `v0.1.2-alpha` |

## Run the local example

The example does not require a model or API key. It executes one exact `/usr/bin/printf`
command declared in the configuration:

```bash
neuruh-sovereign-agent examples/starter.synthetic.json --out-dir run-output
```

Expected output:

```text
RUN COMPLETED: run-...
MANIFEST: run-output/manifest.json
RECEIPTS: run-output/receipts.jsonl
```

Independently verify the artifacts with the two verifiers, which know nothing about this
starter:

```bash
neuruh-agent-run-manifest validate run-output/manifest.json
neuruh-agent-receipt verify run-output/receipts.jsonl
```

Expected output:

```text
VALID run-... sha256:...
PASS: 3 receipts
TIP: ...
```

The sealed manifest records the version of every component that actually ran, read from
installed distribution metadata rather than hard-coded, so a manifest can be matched back
to the exact releases that produced it.

For local inference, set `inference.required` to `true`, provide a loopback
OpenAI-compatible backend, and add a prompt. Remote inference endpoints are rejected at the
configuration boundary — see `examples/ollama-openai-local.synthetic.json`.

## What just happened

The run produced two artifacts. Both are readable, and neither depends on trusting the
agent that wrote them.

`receipts.jsonl` is a hash-chained ledger, one JSON object per line:

| `seq` | `receipt_type` | `authority` | Records |
| --- | --- | --- | --- |
| 0 | `decision` | `governance-decision` | the policy gate returned `allow`, with the policy version derived from the policy content itself |
| 1 | `observation` | `observation` | the inference health probe result — here `unavailable`, because nothing was listening on the loopback backend |
| 2 | `execution` | `execution-evidence` | the exact command that ran and the digest of its output |

Each entry carries `prev_hash` and `entry_hash`. Entry 0 chains from a fixed genesis
constant, entry 1 chains from entry 0, entry 2 from entry 1. That is what `verify` walks.

`manifest.json` seals the run: mission, inputs, decisions, executions, evidence, the
receipt tip, and a `manifest_digest` over the whole thing. Its `components` list is read
from installed distribution metadata rather than hard-coded, so it records the exact
released version of everything that actually ran:

```json
[
  {"name": "neuruh-agent-run-manifest",      "version": "0.1.2a0"},
  {"name": "neuruh-agent-receipt",           "version": "0.1.2a0"},
  {"name": "neuruh-governed-exec",           "version": "0.1.2a0"},
  {"name": "neuruh-policy-gate",             "version": "0.1.2a0"},
  {"name": "neuruh-capability-registry",     "version": "0.1.2a0"},
  {"name": "neuruh-inference-health",        "version": "0.1.2a0"},
  {"name": "neuruh-sovereign-agent-starter", "version": "0.1.1a0"}
]
```

The tamper evidence is not a claim. Change one field in the ledger and re-verify:

```bash
python - <<'EOF'
from pathlib import Path
p = Path("run-output/receipts.jsonl")
p.write_text(p.read_text().replace('"decision": "allow"', '"decision": "deny"', 1))
EOF
neuruh-agent-receipt verify run-output/receipts.jsonl
```

```text
FAIL: entry hash mismatch
```

Exit status 1. Re-run the agent to regenerate a clean ledger.

Note what the model did *not* do. `inference.required` is `false` in this example, so no
model was consulted at all — and the run still completed, because the command came from
`execution_binding` in the configuration, not from a model. Turning inference on adds an
observation receipt. It does not add a way to choose the command.

## What the run enforces

- capability and argument validation happens before policy or execution;
- `DENY` and `ESCALATE` return before any model probe or command;
- only an exact operator-declared executable and argument tuple can run;
- working directories must resolve inside the configured sandbox;
- model output is recorded as evidence and cannot alter the command;
- the run writes a tamper-evident receipt ledger and sealed manifest.

## API

| Name | Purpose |
| --- | --- |
| `StarterConfig.from_mapping(raw)` | Parse and fail-closed validate a run configuration. |
| `run(config, *, probe=..., infer=..., run_id=..., now=...)` | Execute one governed run; returns a `StarterRunResult`. |
| `StarterRunResult` | `manifest`, `receipts`, `decision`, `execution`, `inference_output`. |
| `openai_compatible_infer` | Optional loopback-only inference callable. |
| `StarterError(code, message)` | `E_CONFIG`, `E_CAPABILITY_KIND`, `E_BINDING`, `E_INFERENCE`, `E_INFERENCE_ENDPOINT`. |
| `SCHEMA_VERSION` | `neuruh.sovereign-agent-starter.v0.1`. |

## Test

```bash
python -m unittest discover -s tests -v
```

## Public micro-plugins

Public-safe utilities shipped as CLIs. Three of them (`context_pack`, `cheap_route`, `proof_card`) are also a local Agent Plugin that imports the existing functions. `neuruh-state-diff` and `neuruh-handoff-pack` stay CLI-only. Not a second orchestrator. See [`MICRO_PLUGINS.md`](MICRO_PLUGINS.md).

```bash
neuruh-context-pack examples/mission-packet.synthetic.json
neuruh-cheap-route examples/route-candidates.synthetic.json
neuruh-proof-card examples/internal-receipt.synthetic.json
neuruh-handoff-pack examples/mission-packet.synthetic.json --receipt examples/internal-receipt.synthetic.json
```

To load the plugin locally, copy this repo as a real directory to `~/.cursor/plugins/local/neuruh-public-micro-plugins` (not a symlink out). Cursor should show `neuruh-public-micro-plugins`, three skills, and MCP tools `context_pack`, `cheap_route`, and `proof_card`.

## Safety boundary

This is a bounded reference composition, not the Neuruh production runtime. It is not AXON,
AEGIS/IAR, Governance Core, Mother/Father, LandOS, Recipe Engine or DeedSonar. It contains
no production authority topology, private policies, proprietary scoring, production
connectors, private prompts, customer data or Neuruh routing intelligence.

The starter enforces its guarantees at the configuration and composition boundary. It is
not a sandbox or a container: an operator who declares a dangerous command in the config
gets that command. See [`PUBLIC_PRIVATE_BOUNDARY.md`](PUBLIC_PRIVATE_BOUNDARY.md),
[`ARCHITECTURE.md`](ARCHITECTURE.md), and the
[Neuruh Public Commons boundary](https://github.com/NeuruhAI/public-commons/blob/main/PUBLIC_PRIVATE_BOUNDARY.md).

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
