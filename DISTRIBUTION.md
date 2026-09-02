# Distribution matrix

This repository is the public-safe distribution edge for Neuruh agent-operations utilities. It is not Neuruh Core and contains no private runtime authority, customer data, proprietary scoring, production connectors, or private prompts.

## Current release target

- Package: `neuruh-sovereign-agent-starter`
- Plugin identity: `neuruh-public-micro-plugins`
- Release target: `v0.1.9-alpha`
- Runtime: offline stdio MCP after install; no account or API key
- MCP tools: `context_pack`, `cheap_route`, `proof_card`
- Additional CLIs: `neuruh-state-diff`, `neuruh-handoff-pack`
- Skills: `neuruh-context-pack`, `neuruh-cheap-route`, `neuruh-proof-card`, `neuruh-handoff-pack`

## Platform status

| Platform | Repo surface | Distribution path | State |
| --- | --- | --- | --- |
| Agent Plugins / Cursor | `plugin.json` + `mcp.json` + `skills/` | Public repo can be submitted at `https://cursor.com/marketplace/publish` | READY_FOR_FORM |
| xAI / Grok | `.grok-plugin/plugin.json` + `.mcp.json` | Official marketplace PR `xai-org/plugin-marketplace#503` pins `c40fcd4dd763a14ee9b3601a8315fef58a66a40a` | SUBMITTED_EXTERNAL_REVIEW — DO NOT DUPLICATE |
| Claude Code | `.claude-plugin/plugin.json` + `.mcp.json` + `skills/` | Direct/plugin compatibility; community directory submission is an external form | READY_FOR_FORM |
| OpenAI / Codex workspace import | `.claude-plugin/plugin.json` and public Git repository | Import GitHub plugin/marketplace into a workspace | READY_FOR_IMPORT |
| GitHub Copilot CLI | root `plugin.json` | `copilot plugin install NeuruhAI/neuruh-sovereign-agent-starter` | READY_DIRECT |
| Generic MCP clients | `mcp.json` / `.mcp.json` | stdio `python3 -m neuruh_sovereign_agent_starter.mcp_server` after install | READY_DIRECT |
| Official MCP Registry | package-backed server registration | Requires a registry-verifiable package or remote server; GitHub-only pip dependency path is not enough for the public registry | BLOCKED_ON_PACKAGE_PUBLICATION |
| PyPI | `pyproject.toml` | Publish package, ideally with trusted publishing | NOT_PUBLISHED |

## Submission packet — Cursor Marketplace

Use the public repository URL:

`https://github.com/NeuruhAI/neuruh-sovereign-agent-starter`

Recommended listing copy:

**Name:** Neuruh Public Micro-Plugins

**Short description:** Agent-operations utilities for bounded context, economical routing, clean handoffs, and public-safe proof.

**Long description:** Neuruh Public Micro-Plugins gives coding and agent environments a small public-safe operating layer: compile bounded context instead of replaying chat, choose the cheapest capable route above a success floor, project internal-looking receipts through an explicit public allowlist, compute structural state changes, and create bounded continuation handoffs. Offline stdio MCP after install. No account or API key. No private Neuruh runtime.

**Category:** Developer Tools / Productivity, whichever the form exposes.

**Repository / homepage:** `https://github.com/NeuruhAI/neuruh-sovereign-agent-starter`

**License:** Apache-2.0

**Runtime credentials:** None

**Runtime network:** None after install

## Submission packet — Claude plugin directory

Repository:

`https://github.com/NeuruhAI/neuruh-sovereign-agent-starter`

Suggested copy:

**Plugin name:** `neuruh-public-micro-plugins`

**Description:** Public-safe agent operations utilities for bounded context, economic route selection, proof projection, state diffs, and clean handoffs. Offline stdio MCP; no account or API key.

**Publisher:** Jeramie Hicks / Neuruh

**License:** Apache-2.0

**Credentials:** None

**Network at runtime:** None

## xAI marketplace rule

Do not create a second submission while `xai-org/plugin-marketplace#503` is open. That PR already points to the official `NeuruhAI` source and pins the reviewed `0.1.7-alpha` compatibility commit. New public releases can proceed independently without moving the source SHA under an active external review.

## Release discipline

The GitHub release workflow is allowed to publish only after a successful `push`-triggered `ci` run from this repository's own `main`. Successful CI on an untrusted pull-request head is not release authority.

Every distribution change must keep plugin identity and release version aligned across `pyproject.toml`, `plugin.json`, `.grok-plugin/plugin.json`, `.claude-plugin/plugin.json`, and `mcp_server.SERVER_VERSION`. Historical proof cards and historical release notes remain immutable evidence for the release they describe.

## Next packaging gate: PyPI + official MCP Registry

Do not claim MCP Registry publication until a verifiable distribution route exists. The next clean path is:

1. make the Python package publishable without relying on unsupported direct-VCS dependencies for the target index, or separately package the MCP server in a registry-supported form;
2. configure package publishing credentials / trusted publishing;
3. publish and verify a clean-room install;
4. add the official MCP registry `server.json` metadata and ownership proof;
5. publish through the registry's authenticated publisher flow;
6. record the package version, registry identity, checks and public URL in a release receipt.

That lane is intentionally separate from the already-submitted xAI marketplace PR.
