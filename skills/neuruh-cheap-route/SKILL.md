---
name: neuruh-cheap-route
description: Choose the highest net-value execution route above a capability floor. Use when comparing candidate routes, layers L0-L4, or cheapest-capable vs frontier cost. Never invent candidate costs or probabilities. Call the MCP tool cheap_route.
---

# Cheap route

Use this skill when the task is to pick one candidate from a supplied list.

Do not invent `candidate_id`, `layer`, `success_probability`, expected value, or cost fields. Only score candidates the user or current artifacts already contain.

Call the MCP tool `cheap_route` with:

```json
{
  "candidates": [
    {
      "candidate_id": "...",
      "layer": "L0",
      "success_probability": 0.9,
      "expected_value_usd": 0,
      "execution_cost_usd": 0,
      "model_cost_usd": 0,
      "risk_cost_usd": 0,
      "founder_minutes": 0,
      "latency_minutes": 0
    }
  ],
  "minimum_success_probability": 0.8
}
```

`cheap_route` calls the existing `choose_cheapest_capable_route` function and returns that decision as a dict. This is a standalone public scoring utility, not private Neuruh routing, IAR, or AXON.
