---
name: neuruh-proof-card
description: Project an internal-looking record through the public proof-card allowlist. Use when publishing a receipt, status card, or public proof and private fields must be stripped. Never invent proof fields. Call the MCP tool proof_card.
---

# Proof card

Use this skill when the task is to emit a public-safe subset of a record.

Do not invent `mission`, `status`, `commit_sha`, tests, URLs, or limitations. Only project fields already present on the supplied record. Do not add extra allowlist keys unless the user named them.

Call the MCP tool `proof_card` with:

```json
{
  "record": {
    "mission_id": "...",
    "status": "...",
    "commit_sha": "...",
    "tests": {},
    "public_url": "...",
    "limitations": []
  },
  "extra_allow": []
}
```

`proof_card` calls the existing `public_proof_card` function. It is an allowlist, not a blacklist. Private implementation fields are omitted unless explicitly allowed. This is not DeedSonar, Mother, or a private receipt runtime.
