# Neuruh Micro Plugins

Three standalone, deterministic utilities extracted for public use. They do not connect to the private Neuruh runtime and contain no production authority, private policies, recipes, prompts, customer data, or internal topology.

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

## Why these exist

They are intentionally small enough to use outside Neuruh:

```text
big context -> bounded packet
candidate routes -> cheapest capable route
internal receipt -> public-safe proof card
```

They are edge utilities, not a second orchestration system.
