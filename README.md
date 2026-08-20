# Neuruh Sovereign Agent Starter

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
