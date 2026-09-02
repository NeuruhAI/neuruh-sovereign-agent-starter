# Public claims ledger

Use only claims supported by public repository artifacts.

| Claim | Public evidence |
| --- | --- |
| The package exposes five public agent-ops CLIs. | `pyproject.toml`, `README.md`, tests |
| Three functions are exposed through stdio MCP. | `src/neuruh_sovereign_agent_starter/mcp_server.py`, `mcp.json`, `.mcp.json` |
| Context pack refuses raw transcript/chat keys. | micro-plugin tests + quickstart refusal fixture |
| Proof card uses an allowlist and omits private/unknown fields. | micro-plugin tests + synthetic proof fixture |
| Handoff pack derives its state delta rather than trusting a caller-supplied delta. | handoff tests + synthetic fixtures |
| The public package needs no account or API key at runtime. | manifests + quickstart |
| xAI marketplace submission exists. | external PR `xai-org/plugin-marketplace#503` |
| Cursor / Claude submissions are ready for their external forms. | `plugin.json`, `.claude-plugin/plugin.json`, `DISTRIBUTION.md` |

Do not use this public repo to claim full Neuruh production autonomy, private Governance/AXON behavior, production DeedSonar state, or a marketplace acceptance that has not happened.
