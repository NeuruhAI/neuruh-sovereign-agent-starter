# Neuruh Micro Plugins

Five standalone, deterministic utilities extracted for public use. They do not connect to the private Neuruh runtime and contain no production authority, private policies, recipes, prompts, customer data, or internal topology.

This package is **not** AXON, Mother, IAR, DeedSonar, JGI, or Governance Core. The Agent Plugin wraps the three functions in sections 1–3 only. State-diff stays a CLI utility. Handoff-pack is CLI plus skill, not an MCP tool.

Stranger copy-paste: [`QUICKSTART.md`](QUICKSTART.md).

## 1. Context Pack

Compile a small execution packet instead of replaying an entire chat or transcript.

```bash
neuruh-context-pack examples/demos/bloated-mission.synthetic.json
```

Accepted fields are intentionally narrow: mission ID, parent mission ID, objective, current state, delta, canonical refs, known failures, blockers, authority, budget, acceptance test, and next action. Unknown keys are dropped. Raw chat/transcript keys are **refused** (CLI prints one stderr line, exit 1). Default output ceiling is 4096 bytes.

Expected spine: `mission_id`, `objective`, `next_action`; keys such as `ignored_blob` are absent.

## 2. Cheap Route

Choose the highest net-value execution route above a minimum success threshold.

```bash
neuruh-cheap-route examples/demos/three-routes.synthetic.json --min-success 0.8
```

The public scoring primitive is deliberately generic:

```text
p(success) * expected_value
- execution_cost
- model_cost
- risk_cost
- founder_time_cost
- latency_cost
```

It is not the private Neuruh economic policy. It is a standalone reference utility for preferring competent deterministic/cheap routes over unnecessary model calls.

Expected shape: `{"candidate_id": "deterministic-l0", "layer": "L0", ...}`.

## 3. Proof Card

Project an internal-looking JSON record through an explicit public allowlist.

```bash
neuruh-proof-card examples/demos/internal-receipt-junk.synthetic.json
```

Only a small set of proof fields are emitted by default: mission/artifact/version/status/outcome/commit/tests/public URL/limitations/timestamp. Unexpected private fields — including `transcript` — are **omitted**, not refused. That is an allowlist, not the context-pack refusal policy.

Expected shape: `{"status": "PASS", ...}` with `private_recipe` / `prompt` / `transcript` absent.

## 4. State Diff

Compute a deterministic structural delta between two JSON objects.

```bash
neuruh-state-diff examples/demos/state-before.synthetic.json examples/demos/state-after.synthetic.json
```

Output is path-sorted added/removed/changed entries plus an `unchanged` flag. Nested objects and list indexes are walked. Private or conversational keys (`prompt`, `recipe`, `weights`, `transcript`, customer fields, and private-runtime names) are refused rather than projected. Default output ceiling is 4096 bytes. This helper reports differences only; it grants no authority.

## 5. Handoff Pack

Compile a bounded agent-to-agent continuation packet from previous and current public state (Form A, from `v0.1.6-alpha`).

```bash
neuruh-handoff-pack examples/demos/state-before.synthetic.json examples/demos/state-after.synthetic.json [--max-bytes N]
```

This is a thin composition of `diff_public_state` and `compile_context_packet`. It does not reimplement packing or diffing. `parent_mission_id` is required and taken from `previous.mission_id` (or `previous.mission`). `changed_since_last_run` is derived as pointer-heavy added/changed/removed path strings; a caller-supplied delta is ignored. Transcript/chat keys are refused. Nested private keys are refused by state-diff. The result is then packed so the existing size bound and unknown-field drop still apply.

```text
previous + current -> derived path delta + spine -> bounded handoff packet
```

This helper grants no authority. It is not an MCP tool. Skill: `skills/neuruh-handoff-pack/SKILL.md`.

`v0.1.5-alpha` used an envelope CLI (`STATE.json [--before] [--after] [--receipt]`). Do not use that form on `v0.1.6-alpha` or later.

## Why these exist

They are intentionally small enough to use outside Neuruh. One sentence each is in [`QUICKSTART.md`](QUICKSTART.md). The picture:

```text
big context -> bounded packet
candidate routes -> cheapest capable route
internal receipt -> public-safe proof card
before/after state -> public-safe delta
previous + current -> bounded handoff packet
```

They are edge utilities, not a second orchestration system.

## CLI

After a tagged `pip install .` from a checkout:

```bash
neuruh-context-pack examples/demos/bloated-mission.synthetic.json
neuruh-cheap-route examples/demos/three-routes.synthetic.json --min-success 0.8
neuruh-proof-card examples/demos/internal-receipt-junk.synthetic.json
neuruh-state-diff examples/demos/state-before.synthetic.json examples/demos/state-after.synthetic.json
neuruh-handoff-pack examples/demos/state-before.synthetic.json examples/demos/state-after.synthetic.json
```

`python -m neuruh_sovereign_agent_starter.plugin_demo` needs a git checkout: `examples/` is not in the wheel. Prefer the demos above.

Or stdin:

```bash
neuruh-context-pack - < examples/demos/bloated-mission.synthetic.json
```

## Agent Plugin (local load)

This repo root is an Agent Plugin:

- name: `neuruh-public-micro-plugins`
- skills: `neuruh-context-pack`, `neuruh-cheap-route`, `neuruh-proof-card`, `neuruh-handoff-pack`
- MCP tools: `context_pack`, `cheap_route`, `proof_card`

The MCP server is a stdio JSON-RPC adapter. It imports the three functions above. It does not reimplement them and does not talk to a network. `neuruh-state-diff` is CLI-only. `neuruh-handoff-pack` is CLI plus skill and is not an MCP tool.

Copy the repo as a **real directory** into Cursor local plugins. A symlink that points outside `~/.cursor/plugins/local` is rejected. `mcp.json` sets `PYTHONPATH=${PLUGIN_ROOT}/src` so this uninstalled source copy can import the package:

```bash
mkdir -p ~/.cursor/plugins/local
rm -rf ~/.cursor/plugins/local/neuruh-public-micro-plugins
cp -R . ~/.cursor/plugins/local/neuruh-public-micro-plugins
```

Then reload the Cursor window. Customize should show plugin name `neuruh-public-micro-plugins`, four skills, and three MCP tools. This is not a Cursor Marketplace submission.

After `pip install`, Claude Desktop / generic MCP should launch the same module **without** PYTHONPATH, cwd anywhere:

```text
python3 -m neuruh_sovereign_agent_starter.mcp_server
```
