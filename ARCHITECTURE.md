# Architecture

```text
Operator mission + static config
        |
        v
Capability Registry (007)
        |
        v
Policy Gate (006) -------- DENY/ESCALATE -> stop, no inference probe, no execution
        |
      ALLOW
        |
        v
Inference Health (008) ---- optional loopback model observation
        |
        v
Exact execution binding
        |
        v
Governed Exec (005)
        |
        +--> Agent Receipt chain (001)
        |
        +--> Evidence references (003 semantics)
        |
        v
Agent Run Manifest (009)
        |
        v
Independent manifest verification
```

## Critical non-escalation property

The model cannot create a command. The execution tuple is fixed in operator configuration before inference occurs. Model output can only become evidence/output data.

## Side-effect ordering

1. Parse strict configuration.
2. Resolve and validate declared capability.
3. Evaluate policy.
4. On DENY/ESCALATE: stop before inference/network/execution.
5. On ALLOW: observe local inference health.
6. If inference is required and unavailable: fail before execution.
7. Optional model output is captured as evidence.
8. Execute only the exact predeclared tuple through Governed Exec.
9. Seal receipt chain.
10. Seal and independently verify run manifest.
