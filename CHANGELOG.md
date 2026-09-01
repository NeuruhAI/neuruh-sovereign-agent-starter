# Changelog

## 0.1.4a0 — v0.1.4-alpha

- Package the existing public micro-plugins as an Agent Plugin (`plugin.json` + `mcp.json` + three skills).
- Add a stdio MCP server that imports and calls `compile_context_packet`, `choose_cheapest_capable_route`, and `public_proof_card`. No second implementation.
- MCP tools: `context_pack`, `cheap_route`, `proof_card`.
- Add JSON Schemas, synthetic fixtures, a tiny fixture demo, and MCP protocol tests.
- The primitives and the governed-exec starter path are unchanged. `neuruh-state-diff` remains a CLI utility and is not added as a fourth MCP tool.

## 0.1.3a0 — v0.1.3-alpha

- Add `neuruh-state-diff`: deterministic public-safe structural delta of two JSON objects.
- Refuse private/conversational fields instead of projecting them.
- Add tests covering added/removed/changed paths, nested list indexes, private-field refusal, and oversized-delta refusal.
- This utility is a standalone public edge tool; it does not connect to or expose the private Neuruh production runtime.

## 0.1.2a0 — v0.1.2-alpha

- Add `neuruh-context-pack`: deterministic <=4 KiB execution-context compiler that refuses raw transcript/chat fields.
- Add `neuruh-cheap-route`: generic cheapest-capable route selector using expected value, success probability, model/execution/risk cost, founder time, and latency.
- Add `neuruh-proof-card`: explicit-allowlist projection for public-safe proof records.
- Add tests covering bounded context, transcript refusal, capability floors, deterministic-vs-frontier routing, and private-field omission.
- These utilities are standalone public edge tools; they do not connect to or expose the private Neuruh production runtime.

## 0.1.1a0 — v0.1.1-alpha

- Every dependency now resolves to an immutable public tag. The `neuruh-agent-receipt`
  dependency previously pinned a raw commit SHA.
- The sealed manifest records the version of each component that actually ran, read from
  installed distribution metadata, instead of a hard-coded component list that had drifted
  from the released versions. Covered by a new test.
- `__version__` is read from installed distribution metadata.
- Packaging metadata: PEP 639 `license`/`license-files`, project URLs; the public
  composition moved from an optional extra to required dependencies.
- README documents the pinned component matrix, the run and both verification steps with
  expected output, the public API, and the safety boundary.
- Continuous integration on Python 3.11, 3.12, and 3.13.
- Source formatting throughout. Enforcement behavior is unchanged.

## 0.1.0a0 — v0.1.0-alpha

- Initial public extraction: runnable governed-agent reference composition.
