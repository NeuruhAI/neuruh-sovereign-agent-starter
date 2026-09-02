# Changelog

## 0.1.7a0 — v0.1.7-alpha

- Docs and adoption only. No new primitive.
- Add `QUICKSTART.md`, `examples/demos/` fixtures for A/B/C plus optional state-diff/handoff, architecture-neutral diagram, and tagged pip-from-git install.
- Lead README with the five public CLIs. Pin stranger clone commands to a Git tag.
- Sync `plugin.json` and `mcp_server.SERVER_VERSION` from `0.1.4-alpha` to `0.1.7-alpha`.
- Document local plugin copy (`PYTHONPATH=${PLUGIN_ROOT}/src`) versus pip-installed `python3 -m neuruh_sovereign_agent_starter.mcp_server` with no PYTHONPATH.
- CLI UX: `ValueError` / `TypeError` from the five CLIs print one stderr line and exit 1. Refusal policy unchanged. Proof-card remains an allowlist (drops unknown keys, including `transcript`).
- Public proof card: `PUBLIC_PROOF_CARD.v0.1.7-alpha.json` (packaging/docs, not a production receipt).

## 0.1.6a0 — v0.1.6-alpha

- Replace the 0.1.5-alpha handoff envelope with Form A: `compile_handoff_packet(previous, current)` is a thin composition of `diff_public_state` and `compile_context_packet`. No second packing or diffing implementation.
- `parent_mission_id` is required (from `previous.mission_id`, or `previous.mission` if that is all that is present) and is allowed through context pack.
- `changed_since_last_run` is derived as pointer-heavy added/changed/removed path strings. Caller-supplied deltas are ignored.
- CLI: `neuruh-handoff-pack previous.json current.json [--max-bytes]`. Add skill `neuruh-handoff-pack`. Still not a fourth MCP tool.
- Refuse raw chat/transcript keys and inherit state-diff private-key refusal for nested state. Oversize fails with the existing refs-not-blobs error.
- Add synthetic previous/current fixtures and tests covering composition identity, transcript refusal, private refs, derived delta, bounded size, and no network.

## 0.1.5a0 — v0.1.5-alpha

- Add `neuruh-handoff-pack`: portable continuation envelope assembled from caller-supplied public pieces.
- Compose `compile_context_packet`, optional `diff_public_state` (only when before+after are supplied), and optional `public_proof_card` (only when a receipt is supplied). No second implementation.
- CLI only. Not a fourth MCP tool and not a fourth Agent Plugin skill. PR #4's public contract remains exactly three MCP tools (`context_pack`, `cheap_route`, `proof_card`).
- Refuse private/conversational fields. Bundle ceiling 4096 bytes; refuse rather than truncate the spine. No invented mission, objective, next-action, cost, proof, or timestamp fields.
- Add tests covering context spine, unknown/private-key refusal, transcript refusal, optional delta/proof identity, oversized-bundle refusal, composition identity, and non-JSON rejection.

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
