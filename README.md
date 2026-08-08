# Neuruh Sovereign Agent Starter

A small runnable reference agent composed from Neuruh Public Commons primitives.

It demonstrates a governed run instead of the usual `prompt -> model -> tool -> hope` pattern:

```text
mission
  -> capability registry
  -> policy gate
  -> inference health / optional loopback model call
  -> exact predeclared execution binding
  -> governed exec
  -> evidence + Agent Receipt chain
  -> sealed Agent Run Manifest
```

## Core safety rule

**Model output never becomes command authority.**

The only process that can execute is the exact executable + argv tuple declared by the operator in `execution_binding`, matched to a declared process capability and allowed by policy. The starter does not synthesize shell commands, uses no shell, and will not call a remote inference host in v0.1.

## What it proves

A successful run yields:

- deterministic policy decision;
- declared capability validation;
- inference backend health evidence;
- optional local OpenAI-compatible inference observation;
- exact-argv governed execution evidence;
- tamper-evident Agent Receipt ledger;
- independently validated Agent Run Manifest.

## Install public composition

After Release 009 is tagged:

```bash
pip install '.[public]'
```

## Run dependency-free example behavior

The synthetic example does not require a model; inference is optional. It executes only `/usr/bin/printf` with the exact argv declared in the example.

```bash
neuruh-sovereign-agent examples/starter.synthetic.json --out-dir run-output
```

For a local model, set `inference.required=true`, provide a loopback OpenAI-compatible backend and a prompt.

## Private boundary

This is not AXON, AEGIS/IAR, Governance Core, Mother/Father, LandOS, Recipe Engine or DeedSonar. It contains no production authority topology, private policies, proprietary scoring, production connectors, private prompts, customer data or Neuruh routing intelligence.

Status: Active Alpha candidate.
