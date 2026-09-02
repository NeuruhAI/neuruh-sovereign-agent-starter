# Launch message

I got tired of babysitting coding agents.

So I started separating the jobs around the model: context, routing, handoff, proof, and authority.

This public repo is a small, safe slice of that work: five agent-ops utilities plus a three-tool stdio MCP server. It does not expose the private Neuruh runtime.

The simple rule behind it: **the model should not also be your memory format, routing policy, handoff protocol, and proof system.**

Start with `QUICKSTART.md`. Distribution and marketplace state are in `DISTRIBUTION.md`.
