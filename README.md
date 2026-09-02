# Neuruh Sovereign Agent Starter

[![ci](https://github.com/NeuruhAI/neuruh-sovereign-agent-starter/actions/workflows/ci.yml/badge.svg)](https://github.com/NeuruhAI/neuruh-sovereign-agent-starter/actions/workflows/ci.yml)

**Public-safe agent operations utilities for bounded context, economical routing, clean handoffs, and proof you can verify.**

AI workers are useful. The missing layer is everything around the worker: what context it receives, what route deserves resources, what changed since the last run, what gets handed to the next worker, and what evidence is safe to publish afterward.

This repository exposes a small public subset of that operating layer. It is **not Neuruh Core** and contains no private runtime authority, customer data, proprietary scoring, production connectors, private prompts, or internal topology.

## The five utilities

| CLI | Job |
| --- | --- |
| `neuruh-context-pack` | Compile a bounded execution packet instead of replaying an entire chat. Unknown keys drop; transcript/chat keys refuse. |
| `neuruh-cheap-route` | Choose the cheapest capable route above a declared success floor. |
| `neuruh-proof-card` | Project an internal-looking record through an explicit public allowlist. |
| `neuruh-state-diff` | Compute deterministic added / removed / changed paths between two public states. |
| `neuruh-handoff-pack` | Create a bounded continuation packet from previous + current state with a derived delta. |

Three functions are also exposed as stdio MCP tools:

`context_pack` · `cheap_route` · `proof_card`

Handoff is a CLI + skill. State diff remains CLI-only.

## Why this exists

```text
bloated state      -> context-pack  -> bounded packet
candidate routes   -> cheap-route   -> selected route
internal receipt   -> proof-card    -> public-safe proof
before / after     -> state-diff    -> explicit delta
previous + current -> handoff-pack  -> next-worker packet
```

The point is deliberately boring: **the model should not also be your memory format, routing policy, handoff protocol, and proof system.**

## Install
### Claude Code

```
/plugin marketplace add NeuruhAI/neuruh-sovereign-agent-starter
/plugin install neuruh-public-micro-plugins@neuruh
```

Adds the three MCP tools (`context_pack`, `cheap_route`, `proof_card`) and four skills. Offline
stdio after install. No account, no API key, no network at runtime.


Python 3.11+.

Tagged source install:

```bash
git clone --branch v0.1.9-alpha --depth 1 https://github.com/NeuruhAI/neuruh-sovereign-agent-starter.git
cd neuruh-sovereign-agent-starter
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

Pip directly from the immutable Git tag:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install "neuruh-sovereign-agent-starter @ git+https://github.com/NeuruhAI/neuruh-sovereign-agent-starter.git@v0.1.9-alpha"
```

No account or API key is required. Install needs network access for the pinned public GitHub dependencies; the micro-plugin transforms and default example run make no runtime network calls.

PyPI is not yet the canonical install path.

## 60-second proof

A tagged checkout contains synthetic demo files:

```bash
neuruh-context-pack examples/demos/bloated-mission.synthetic.json
# bounded packet; ignored_blob absent

neuruh-cheap-route examples/demos/three-routes.synthetic.json --min-success 0.8
# deterministic-l0 wins over unnecessary higher layers

neuruh-proof-card examples/demos/internal-receipt-junk.synthetic.json
# PASS; private_recipe / prompt / transcript omitted

neuruh-state-diff examples/handoff-previous.synthetic.json examples/handoff-current.synthetic.json

neuruh-handoff-pack examples/handoff-previous.synthetic.json examples/handoff-current.synthetic.json
# parent_mission_id + derived changed_since_last_run
```

For exact expected shapes and refusal cases, use [`QUICKSTART.md`](QUICKSTART.md).

## Plugin / agent-environment compatibility

The repository carries multiple public manifests around one implementation rather than cloning the logic per platform:

| Environment | Surface |
| --- | --- |
| Agent Plugins / Cursor | `plugin.json`, `mcp.json`, `skills/` |
| xAI / Grok | `.grok-plugin/plugin.json`, `.mcp.json` |
| Claude-compatible plugin consumers | `.claude-plugin/plugin.json`, `.mcp.json`, `skills/` |
| OpenAI / Codex workspace GitHub import | public repository + Claude-compatible plugin surface |
| GitHub Copilot CLI | root Agent Plugin manifest |
| Generic MCP clients | stdio `python3 -m neuruh_sovereign_agent_starter.mcp_server` |

See [`DISTRIBUTION.md`](DISTRIBUTION.md) for current submission state, exact marketplace copy, external-review boundaries, and the package/registry next gates.

### Generic stdio MCP

After installation:

```json
{
  "mcpServers": {
    "neuruh-public-micro-plugins": {
      "command": "python3",
      "args": ["-m", "neuruh_sovereign_agent_starter.mcp_server"]
    }
  }
}
```

The source-tree plugin copies use `PYTHONPATH=${PLUGIN_ROOT}/src`; a normal pip-installed invocation does not.

## Four skills

- `neuruh-context-pack`
- `neuruh-cheap-route`
- `neuruh-proof-card`
- `neuruh-handoff-pack`

There is intentionally no `neuruh-state-diff` skill. State diff stays a direct utility.

## Governed-exec reference starter

The repository also includes a bounded reference composition showing a larger principle: **model output is evidence, not command authority.**

```text
mission
  -> capability registry
  -> policy gate
  -> inference health / optional loopback observation
  -> exact predeclared execution binding
  -> governed exec
  -> hash-chained receipts
  -> sealed run manifest
```

Run the synthetic example:

```bash
neuruh-sovereign-agent examples/starter.synthetic.json --out-dir run-output
```

Then independently verify the artifacts:

```bash
neuruh-agent-run-manifest validate run-output/manifest.json
neuruh-agent-receipt verify run-output/receipts.jsonl
```

The example uses an exact operator-declared `/usr/bin/printf` binding. A model is not required. If local inference is enabled, its output is recorded as an observation and still cannot choose the command.

## What the starter enforces

- capability and argument validation before policy or execution;
- `DENY` / `ESCALATE` stop before execution;
- exact executable + argument binding;
- working-directory containment inside the configured sandbox;
- model output cannot rewrite the execution binding;
- hash-chained receipt evidence;
- a sealed run manifest with the installed component versions that actually ran.

This is a reference composition, not a container or general sandbox. An operator who explicitly configures a dangerous command has declared that command. Read [`PUBLIC_PRIVATE_BOUNDARY.md`](PUBLIC_PRIVATE_BOUNDARY.md) and [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Release and evidence discipline

`main` CI tests Python 3.11 / 3.12 / 3.13. Release automation only publishes after successful same-repository **push** CI on `main`; a successful pull-request run is not release authority.

Historical proof cards remain bound to the releases they describe. Do not rewrite a historical proof card simply because the package advances.

## Safety boundary

Public package only. No AXON internals, Mother internals, private Governance rules, Recipe Engine logic, DeedSonar data, customer information, proprietary ranking weights, private prompts, credentials, or production authority.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
