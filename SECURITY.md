# Security

The starter is intentionally bounded:

- process execution requires an exact operator-declared executable + argv tuple;
- `shell=False` is inherited from Neuruh Governed Exec;
- working directory is confined to an authorized sandbox root;
- model output is evidence, never executable authority;
- v0.1 local-model inference is loopback-only;
- policy and capability validation happen before execution;
- DENY and ESCALATE never execute;
- every attempted allowed execution produces receipt evidence and a sealed manifest.

## Reporting a vulnerability

Report privately at **<https://neuruh.com/security>**, the published disclosure route for Neuruh.
It is also the `Contact` in <https://neuruh.com/.well-known/security.txt>.

Please do not open a public issue for a vulnerability, and do not include credentials, customer
data, production endpoints, or private configuration in a report — a description and reproduction
steps are enough.

### Scope

In scope: this repository, the published `neuruh-sovereign-agent-starter` package, the
`neuruh-public-micro-plugins` plugin manifests, and the stdio MCP server.

Out of scope: private Neuruh runtime, production systems, and any service not distributed from this
repository. This repo is a public-safe edge and holds none of them.

### What this plugin can and cannot do

It runs offline over stdio after install, needs no account, API key, or network at runtime, and
holds no consequential authority — it packs context, ranks routes, projects a public-safe proof
card, diffs public state, and builds handoffs. Model output is evidence, never executable
authority. Nothing here can contact a customer, move money, or write a production system.


Do not place credentials, customer data, production endpoints, production policies, private capability maps, private prompts, proprietary weights or production Neuruh configuration in examples or issues.
