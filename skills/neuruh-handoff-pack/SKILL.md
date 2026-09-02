---
name: neuruh-handoff-pack
description: Compile a bounded agent-to-agent continuation packet from previous and current public state. Use when handing a mission to another agent without replaying chat. Never invent field values. Compose context pack and state diff via the CLI or compile_handoff_packet. Not an MCP tool.
---

# Handoff pack

Use this skill when one agent must continue another agent's public mission.

Do not invent `mission_id`, `parent_mission_id`, `objective`, state, refs, failures, blockers, authority, budget, acceptance tests, or next actions. Only pass previous and current JSON the user or current artifacts already contain.

This skill composes the existing `compile_context_packet` and `diff_public_state` functions. It does not reimplement packing or diffing.

Call the CLI:

```bash
neuruh-handoff-pack previous.json current.json --max-bytes 4096
```

Or call `compile_handoff_packet(previous, current, max_bytes=4096)`.

`parent_mission_id` is taken from `previous.mission_id` (or `previous.mission` if that is all that is present). `changed_since_last_run` is derived as pointer-heavy added/changed/removed path strings from `diff_public_state`; do not trust a caller-supplied delta. Transcript/chat keys are refused. Nested private keys are refused by `diff_public_state`. The result is then packed by `compile_context_packet` so the size bound and unknown-field drop still apply.

This is not AXON, Mother, IAR, or DeedSonar. It is not an MCP tool.
