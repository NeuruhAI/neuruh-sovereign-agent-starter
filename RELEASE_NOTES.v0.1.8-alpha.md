# Neuruh Sovereign Agent Starter — v0.1.8-alpha

Distribution convergence release. No private Neuruh runtime is added.

## What changed

- Adds `.claude-plugin/plugin.json` while preserving the existing Agent Plugin, xAI/Grok, and MCP surfaces around one implementation.
- Repositions the public package around five concrete agent-operations jobs: bounded context, economic routing, public-safe proof, explicit state diff, and clean handoff.
- Adds `DISTRIBUTION.md` with exact Cursor and Claude submission packets, xAI PR #503 custody, Codex/Copilot compatibility notes, and the PyPI/MCP Registry next gate.
- Aligns package, Agent Plugin, xAI manifest, Claude manifest, and MCP server versions at `0.1.8-alpha` / `0.1.8a0`.
- Adds a distribution court that fails on version/identity drift or mismatched MCP scanner config.
- Hardens GitHub release authority: only a successful same-repository `push` CI run on `main` can trigger a release. Pull-request CI is never release authority.
- Refreshes README and Quickstart so the public repo no longer tells users to install an older release or claims Cursor packaging is local-only.

## Explicit non-claims

- xAI marketplace PR #503 remains a separate external review pinned to `c40fcd4dd763a14ee9b3601a8315fef58a66a40a`; this release does not duplicate or silently move that submission.
- No Cursor or Claude web submission form is claimed complete by this GitHub release.
- PyPI is not published.
- Official MCP Registry publication is not claimed.
- No production Neuruh, DeedSonar, AXON, Governance, Mother, IAR, JGI, customer-data, or private-authority surface is included.
