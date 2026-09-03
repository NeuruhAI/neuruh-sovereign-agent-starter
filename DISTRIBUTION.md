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

Each state below was re-proven on 2026-09-02 against `v0.1.9-alpha`, not inherited from a previous
receipt. "Manifest exists" is never treated as "submitted" or "installable".

| Platform | Repo surface | Distribution path | State |
| --- | --- | --- | --- |
| Generic MCP clients | `mcp.json` / `.mcp.json` | stdio `python3 -m neuruh_sovereign_agent_starter.mcp_server` after install | **LIVE** — clean-room install from the published tag completes `initialize` → `tools/list` → `tools/call` over MCP's newline-delimited stdio framing |
| Claude Code | `.claude-plugin/marketplace.json` + `.claude-plugin/plugin.json` + `.mcp.json` + `skills/` | `/plugin marketplace add NeuruhAI/neuruh-sovereign-agent-starter` | **INSTALLABLE — SKILLS IMMEDIATELY, MCP TOOLS AFTER `pip install`.** Verified 2026-09-03: `marketplace add` then `plugin install` registers four skills and one MCP server. The skills work on install. The MCP server does not: `.mcp.json` launches `python3 -m neuruh_sovereign_agent_starter.mcp_server`, and the plugin install does not install the package, so on an interpreter without the six pinned dependencies it exits at import with `ModuleNotFoundError: No module named 'neuruh_agent_run_manifest'` and the plugin lists zero tools. Run `pip install "neuruh-sovereign-agent-starter @ git+https://github.com/NeuruhAI/neuruh-sovereign-agent-starter.git@v0.1.9-alpha"` into the interpreter that `python3` resolves to first. Removing that prerequisite depends on the PyPI blocker below |
| xAI / Grok | `.grok-plugin/plugin.json` + `.mcp.json` | Official marketplace PR [`xai-org/plugin-marketplace#503`](https://github.com/xai-org/plugin-marketplace/pull/503), pinned to `9a9a5329805f94ca5f8833f17873e87f076cb4f0` | **SUBMITTED — AWAITING EXTERNAL REVIEW.** Not accepted, not live. **DO NOT DUPLICATE** |
| Agent Plugins / Cursor | `plugin.json` + `mcp.json` + `skills/` | Public repo submitted at `https://cursor.com/marketplace/publish` | **BLOCKED_EXTERNAL_FORM** — a web form under a founder account; nothing in this repo can complete it |
| OpenAI / Codex workspace import | `.claude-plugin/plugin.json` + public Git repository | Import the public GitHub repo into a workspace | **READY_FOR_IMPORT** — repo is public and manifest-complete; the import happens in the consumer's workspace, so there is nothing here to submit |
| GitHub Copilot CLI | root `plugin.json` | `copilot plugin install NeuruhAI/neuruh-sovereign-agent-starter` | **READY_UNVERIFIED** — the manifest is in place, but the Copilot CLI is not installed on the build host, so this repo has never actually run that command. Do not claim it works until someone runs it |
| PyPI | `pyproject.toml` | Publish the package | **BLOCKED_ON_PACKAGE_RESTRUCTURE** — see below. Not merely "unpublished" |
| Official MCP Registry | package-backed server registration | Registry publisher flow | **BLOCKED_ON_PACKAGE_PUBLICATION** — the registry wants a registry-verifiable package or remote server, which depends on the PyPI blocker below |

### Why PyPI is blocked by structure, not by credentials

All six dependencies are declared as direct VCS URLs:

```
Requires-Dist: neuruh-agent-run-manifest @ git+https://github.com/NeuruhAI/...
Requires-Dist: neuruh-agent-receipt      @ git+https://github.com/NeuruhAI/...
Requires-Dist: neuruh-governed-exec      @ git+https://github.com/NeuruhAI/...
Requires-Dist: neuruh-policy-gate        @ git+https://github.com/NeuruhAI/...
Requires-Dist: neuruh-capability-registry @ git+https://github.com/NeuruhAI/...
Requires-Dist: neuruh-inference-health   @ git+https://github.com/NeuruhAI/...
```

PyPI refuses any distribution whose metadata declares a direct URL dependency, so a built wheel of
this package cannot be uploaded as-is even with valid credentials. None of the six dependencies is
on PyPI either (all return 404), so the unblock path is:

1. publish the six Neuruh Public Commons dependencies to PyPI, then
2. replace the `git+https` pins with ordinary version specifiers, then
3. publish this package and verify a clean-room `pip install` from the index.

An API token alone does not unblock it. Getting a token first would only produce a rejected upload.

## Submission packet — Cursor Marketplace

Use the public repository URL:

`https://github.com/NeuruhAI/neuruh-sovereign-agent-starter`

Recommended listing copy:

**Name:** Neuruh Public Micro-Plugins

**Short description:** Agent-operations utilities for bounded context, economical routing, clean handoffs, and public-safe proof.

**Long description:** Neuruh Public Micro-Plugins gives coding and agent environments a small public-safe operating layer: compile bounded context instead of replaying chat, choose the cheapest capable route above a success floor, project internal-looking receipts through an explicit public allowlist, compute structural state changes, and create bounded continuation handoffs. Three of these are exposed as stdio MCP tools — `context_pack`, `cheap_route`, `proof_card`. State diff and handoff pack are CLIs; handoff pack is also a skill. Offline after install. No account or API key. No private Neuruh runtime.

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

Do not create a second submission while [`xai-org/plugin-marketplace#503`](https://github.com/xai-org/plugin-marketplace/pull/503)
is open. That PR points at the official `NeuruhAI` source and is the single entry for this plugin.

It is currently pinned to `9a9a5329805f94ca5f8833f17873e87f076cb4f0` (`v0.1.9-alpha`). The pin was
moved from `c40fcd4` on 2026-09-02 because that commit's MCP server framed stdio messages LSP-style
and could not complete a handshake with any MCP client, so the reviewed candidate would have shipped
unusable. xAI's `CONTRIBUTING.md` states the update path explicitly: *"To update a live plugin, bump
the `sha` (remote) … and regenerate the index — don't open a parallel duplicate entry."* Only
`source.sha` changed; the index was regenerated with their `scripts/generate-plugin-index.py`, both
their validators pass, and the declared components are byte-identical.

**The submission is not accepted and not live in the marketplace.** It is awaiting external review.
Do not describe it otherwise anywhere public.

Routine new releases do not need to move the pin. Move it only for a defect that would ship broken,
and say why in the PR.

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
