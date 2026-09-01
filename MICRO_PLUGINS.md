# Neuruh Micro Plugins

Four standalone, deterministic utilities extracted for public use. They do not connect to the private Neuruh runtime and contain no production authority, private policies, recipes, prompts, customer data, or internal topology.

This package is **not** AXON, Mother, IAR, DeedSonar, JGI, or Governance Core. The Agent Plugin wraps the three functions in sections 1–3 only. State-diff stays a CLI utility.

## 1. Context Pack

Compile a small execution packet instead of replaying an entire chat or transcript.

```bash
neuruh-context-pack mission.json
```

Accepted fields are intentionally narrow: mission ID, objective, current state, delta, canonical refs, known failures, blockers, authority, budget, acceptance test, and next action. Raw chat/transcript keys are rejected. Default output ceiling is 4096 bytes.

## 2. Cheap Route

Choose the highest net-value execution route above a minimum success threshold.

```bash
neuruh-cheap-route candidates.json --min-success 0.8
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

## 3. Proof Card

Project an internal-looking JSON record through an explicit public allowlist.

```bash
neuruh-proof-card receipt.json
```

Only a small set of proof fields are emitted by default: mission/artifact/version/status/outcome/commit/tests/public URL/limitations/timestamp. Unexpected private fields are omitted unless explicitly allowlisted by the caller.

## 4. State Diff

Compute a deterministic structural delta between two JSON objects.

```bash
neuruh-state-diff before.json after.json
```

Output is path-sorted added/removed/changed entries plus an `unchanged` flag. Nested objects and list indexes are walked. Private or conversational keys (`prompt`, `recipe`, `weights`, `transcript`, customer fields, and private-runtime names) are refused rather than projected. Default output ceiling is 4096 bytes. This helper reports differences only; it grants no authority.

## Why these exist

They are intentionally small enough to use outside Neuruh:

```text
big context -> bounded packet
candidate routes -> cheapest capable route
internal receipt -> public-safe proof card
before/after state -> public-safe delta
```

They are edge utilities, not a second orchestration system.

## CLI

After `pip install .`:

```bash
neuruh-context-pack examples/mission-packet.synthetic.json
neuruh-cheap-route examples/route-candidates.synthetic.json --min-success 0.8
neuruh-proof-card examples/internal-receipt.synthetic.json
python -m neuruh_sovereign_agent_starter.plugin_demo
```

Or stdin:

```bash
neuruh-context-pack - < examples/mission-packet.synthetic.json
```

## Agent Plugin (local load)

This repo root is an Agent Plugin:

- name: `neuruh-public-micro-plugins`
- skills: `neuruh-context-pack`, `neuruh-cheap-route`, `neuruh-proof-card`
- MCP tools: `context_pack`, `cheap_route`, `proof_card`

The MCP server is a stdio JSON-RPC adapter. It imports the three functions above. It does not reimplement them and does not talk to a network.

Copy the repo as a **real directory** into Cursor local plugins. A symlink that points outside `~/.cursor/plugins/local` is rejected:

```bash
mkdir -p ~/.cursor/plugins/local
rm -rf ~/.cursor/plugins/local/neuruh-public-micro-plugins
cp -R . ~/.cursor/plugins/local/neuruh-public-micro-plugins
```

Then reload the Cursor window. Customize should show plugin name `neuruh-public-micro-plugins`, three skills, and three MCP tools. This is not a Cursor Marketplace submission.
