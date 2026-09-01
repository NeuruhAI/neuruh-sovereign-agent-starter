---
name: neuruh-context-pack
description: Compile a bounded pointer-heavy execution packet from known mission fields. Use when you need a compact execution context, a mission packet, or must refuse raw chat/transcript replay. Never invent field values. Call the MCP tool context_pack.
---

# Context pack

Use this skill when the task is to turn known execution state into a small packet.

Do not invent `mission_id`, `objective`, refs, failures, blockers, authority, budget, acceptance tests, or next actions. Only pass fields the user or current artifacts already contain.

Call the MCP tool `context_pack` with:

```json
{
  "state": {
    "mission_id": "...",
    "objective": "...",
    "current_state": "...",
    "changed_since_last_run": [],
    "canonical_refs": [],
    "known_failures": [],
    "blockers": [],
    "authority": {},
    "budget": {},
    "acceptance_test": {},
    "next_action": "..."
  },
  "max_bytes": 4096
}
```

`context_pack` calls the existing `compile_context_packet` function. Unknown fields are dropped. Transcript/chat keys are refused. This is not AXON, Mother, IAR, or DeedSonar.
