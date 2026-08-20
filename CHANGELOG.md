# Changelog

## 0.1.1a0 — v0.1.1-alpha

- Every dependency now resolves to an immutable public tag. The `neuruh-agent-receipt`
  dependency previously pinned a raw commit SHA.
- The sealed manifest records the version of each component that actually ran, read from
  installed distribution metadata, instead of a hard-coded component list that had drifted
  from the released versions. Covered by a new test.
- `__version__` is read from installed distribution metadata.
- Packaging metadata: PEP 639 `license`/`license-files`, project URLs; the public
  composition moved from an optional extra to required dependencies.
- README documents the pinned component matrix, the run and both verification steps with
  expected output, the public API, and the safety boundary.
- Continuous integration on Python 3.11, 3.12, and 3.13.
- Source formatting throughout. Enforcement behavior is unchanged.

## 0.1.0a0 — v0.1.0-alpha

- Initial public extraction: runnable governed-agent reference composition.
