# Distribution submission receipt — v0.1.8-alpha

MISSION=`NEURUH-PUBLIC-DISTRIBUTION-CONVERGENCE-20260902`

## Custody

- Canonical source: `NeuruhAI/neuruh-sovereign-agent-starter`
- Base before this release lane: `c40fcd4dd763a14ee9b3601a8315fef58a66a40a`
- Package version target: `0.1.8a0`
- Public plugin identity: `neuruh-public-micro-plugins`
- Public plugin version target: `0.1.8-alpha`

## External distribution state

- xAI official marketplace: **SUBMITTED / EXTERNAL REVIEW** at `xai-org/plugin-marketplace#503`; pinned to reviewed source `c40fcd4`; **NO DUPLICATE SUBMISSION**.
- Cursor Marketplace: **READY_FOR_FORM**; root Agent Plugin manifest present and repository public.
- Claude plugin directory: **READY_FOR_FORM**; `.claude-plugin/plugin.json` present.
- OpenAI/Codex workspace GitHub import: **READY_FOR_IMPORT** via public plugin repository.
- GitHub Copilot CLI: **READY_DIRECT** via root Agent Plugin manifest.
- Generic MCP: **READY_DIRECT** via stdio server.
- PyPI: **NOT_PUBLISHED**.
- Official MCP Registry: **BLOCKED_ON_PACKAGE_PUBLICATION**.

## Release authority

The release workflow on this lane refuses pull-request CI as release authority. It may publish only after a successful same-repository push-triggered CI run on `main`.

## Public boundary

No private Neuruh runtime, customer data, private prompts, scoring recipes, credentials, production connectors, or consequential authority are included.

## Promotion rule

Merge only after exact-head CI is green. The existing release workflow should then create immutable `v0.1.8-alpha` if the tag does not already exist.
