# Quickstart

Public micro-plugin CLIs plus a local Agent Plugin / stdio MCP package. This repository is **not Neuruh Core, AXON, Mother, IAR, DeedSonar, or JGI**.

Release line: `v0.1.8-alpha`.

PyPI is not yet the canonical install path. Install from the immutable GitHub tag.

## 30-second why

Five small public-safe transforms. No model required. No API key. No runtime network after install.

```text
bloated state      -> context-pack  -> bounded packet
candidates         -> cheap-route   -> selected route
internal receipt   -> proof-card    -> public card
before / after     -> state-diff    -> public delta
previous + current -> handoff-pack  -> bounded handoff packet
```

| CLI | Why it exists |
| --- | --- |
| `neuruh-context-pack` | Compile a bounded execution packet instead of replaying chat. Unknown keys drop; transcript/chat keys refuse. |
| `neuruh-cheap-route` | Choose a capable route without wasting expensive reasoning where a cheaper layer clears the success floor. |
| `neuruh-proof-card` | Project a record through a public allowlist. Private/unknown fields are omitted. |
| `neuruh-state-diff` | Report deterministic added / removed / changed paths between two public JSON objects. |
| `neuruh-handoff-pack` | Pack previous + current into a continuation packet with required parent mission identity and derived path delta. |

## Install

Python 3.11+.

Tagged clone, including demo fixtures:

```bash
git clone --branch v0.1.8-alpha --depth 1 https://github.com/NeuruhAI/neuruh-sovereign-agent-starter.git
cd neuruh-sovereign-agent-starter
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

CLI-only pip-from-git install:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install "neuruh-sovereign-agent-starter @ git+https://github.com/NeuruhAI/neuruh-sovereign-agent-starter.git@v0.1.8-alpha"
```

Confirm:

```bash
python -c "import importlib.metadata as m; print(m.version('neuruh-sovereign-agent-starter'))"
```

Expected distribution version: `0.1.8a0`.

## Demo A — bounded context

```bash
neuruh-context-pack examples/demos/bloated-mission.synthetic.json
```

The result retains the mission spine and omits unrelated bloat such as `ignored_blob`. The packet stays within its configured byte ceiling.

Refusal case:

```bash
neuruh-context-pack examples/demos/bloated-mission.transcript-refuse.synthetic.json
```

Expected: one-line refusal naming `transcript`, exit 1. Raw conversational history is not accepted as durable execution context.

## Demo B — economic routing

```bash
neuruh-cheap-route examples/demos/three-routes.synthetic.json --min-success 0.8
```

The deterministic L0 route wins when it clears the declared success floor and has better net economics than unnecessary higher layers.

## Demo C — public-safe proof

```bash
neuruh-proof-card examples/demos/internal-receipt-junk.synthetic.json
```

Expected public fields include `mission_id`, `status`, `version`, and other allowlisted evidence. Fields such as `private_recipe`, `prompt`, and `transcript` are omitted.

Proof-card is an **allowlist projection**. That is intentionally different from context-pack's transcript/chat refusal.

## Demo D — state change + clean handoff

```bash
neuruh-state-diff examples/handoff-previous.synthetic.json examples/handoff-current.synthetic.json
neuruh-handoff-pack examples/handoff-previous.synthetic.json examples/handoff-current.synthetic.json
```

State diff prints explicit path changes. Handoff pack derives `changed_since_last_run`, binds `parent_mission_id` to the previous mission, and refuses to trust a caller-supplied fake delta.

## MCP

Exactly three MCP tools:

- `context_pack`
- `cheap_route`
- `proof_card`

State diff is CLI-only. Handoff pack is CLI + skill, not a fourth MCP tool.

### Generic stdio / pip-installed

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

Use the virtual environment's Python if the package is not installed on the system interpreter.

### Cursor / Agent Plugin source copy

The root `plugin.json` follows the Agent Plugins schema and `mcp.json` uses `PYTHONPATH=${PLUGIN_ROOT}/src` for a source-tree plugin copy.

```bash
mkdir -p ~/.cursor/plugins/local
rm -rf ~/.cursor/plugins/local/neuruh-public-micro-plugins
cp -R . ~/.cursor/plugins/local/neuruh-public-micro-plugins
```

Reload Cursor. The plugin should expose the four skills and MCP tools `context_pack`, `cheap_route`, `proof_card`.

### Other clients

The same implementation is projected through platform manifests instead of duplicated:

- xAI / Grok: `.grok-plugin/plugin.json` + `.mcp.json`
- Claude-compatible plugin consumers: `.claude-plugin/plugin.json` + `.mcp.json`
- OpenAI / Codex workspace GitHub import: public repository + compatible plugin manifest
- GitHub Copilot CLI: root Agent Plugin manifest

See [`DISTRIBUTION.md`](DISTRIBUTION.md) for submission status and exact marketplace packets.

## Skills

| Skill | Execution surface |
| --- | --- |
| `neuruh-context-pack` | MCP `context_pack` |
| `neuruh-cheap-route` | MCP `cheap_route` |
| `neuruh-proof-card` | MCP `proof_card` |
| `neuruh-handoff-pack` | CLI `neuruh-handoff-pack previous.json current.json` |

There is no `neuruh-state-diff` skill.

## Governed-exec starter

A separate example in this repository demonstrates a bounded governed run where model output is evidence rather than command authority. See [`README.md`](README.md#governed-exec-reference-starter).

## Test

```bash
python -m unittest discover -s tests -v
```

The distribution court also checks that package/plugin/server versions stay aligned, root and scanner MCP configs describe the same server, and the active xAI marketplace submission is not duplicated.
