# Organism vNext composition (CANONICAL CANDIDATE — not production canonical)

`neuruh_sovereign_agent_starter.organism` composes the Public Commons primitives this starter
already pins with the learning back half into one end-to-end governed agent lifecycle over
isolated, replayable Worlds.

```
WORLD → SEED → EVIDENCE → IDENTITY → SIGNAL → RECIPE → INTENT → CAPABILITY → POLICY → AUTHORITY
→ ACTION → GOVERNED EXECUTION → RECEIPT → OUTCOME → CALIBRATION → LEARNING PROPOSAL
→ CANONICAL REVISION → PROMOTION → EFFECTIVE STATE → MEMORY → NEXT LOOP
```

| module | role | primitives reused |
|---|---|---|
| `contracts` | organism envelopes + contract graph | 009 canonical_json/sha256_ref |
| `world` | WorldSeedSpec, World, snapshot, fork, replay | 001 receipts, 007 registry, 006 policy |
| `authority` | six-fact authority decision, gov.decision.request.v1 / AXON / world-engine projections | 007, 006 |
| `lifecycle` | intent → policy → authority → governed exec → receipt → manifest | 005, 001, 009 |
| `learning` | outcome → calibration → 019 → 030-shape → 033 → 020 → 034 → 035 → 036 | outcome-record, 017, 019, 020, 033–036 |
| `projection` | reversible Markdown (Obsidian) projection | — |
| `product_adapter` | product → bounded agent domain (declared, not wired) | 007, 006 |
| `court` | world-demo-001 executable court + negative court | all |

Run without installing anything (sibling source trees):

```sh
. scripts/organism_env.sh
python3 -m unittest discover -s tests -p 'test_organism_*.py'
python3 -m neuruh_sovereign_agent_starter.organism.court --out /tmp/court
```
