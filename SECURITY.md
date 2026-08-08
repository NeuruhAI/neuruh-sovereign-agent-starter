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

Do not place credentials, customer data, production endpoints, production policies, private capability maps, private prompts, proprietary weights or production Neuruh configuration in examples or issues.
