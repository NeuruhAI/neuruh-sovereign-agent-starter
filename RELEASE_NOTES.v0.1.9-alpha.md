# Neuruh Sovereign Agent Starter — v0.1.9-alpha

**One fix: the stdio MCP server now speaks the framing MCP clients actually use.**

## What was wrong

The server framed JSON-RPC messages LSP-style, with `Content-Length` headers. MCP's stdio
transport is newline-delimited JSON — one JSON object per line — and that is what every MCP
client writes. A spec-compliant client sent `initialize` and got nothing back, so the handshake
never completed and none of the three tools was reachable over the wire.

This affected every surface that advertises stdio MCP: Cursor / Agent Plugins, Claude-compatible
plugin consumers, OpenAI/Codex workspace import, GitHub Copilot CLI, generic MCP clients, and the
xAI/Grok manifest.

The manifests, schemas, and tools were all correct. Only the transport framing was wrong.

## Why the tests did not catch it

The suite exercised `handle_rpc()` directly, and its single transport test wrote `Content-Length`
frames itself and then asserted the reply contained a `Content-Length` header. The test agreed
with the server about a framing no client uses, so both stayed wrong together.

## What changed

- `_read_message` reads newline-delimited JSON, and still accepts `Content-Length` framing from
  any older caller. It reports which framing arrived.
- `_write_message` replies in the framing the client used.
- New tests: a real subprocess round-trip over newline-delimited JSON (`initialize` →
  `notifications/initialized` → `tools/list` → `tools/call`), which fails against the
  0.1.8-alpha transport, plus direct framing-detection and writer assertions.

## What did not change

No tool was added or removed. No schema, permission, credential, or network behavior changed.
`context_pack`, `cheap_route`, and `proof_card` behave exactly as in 0.1.8-alpha. Still offline
stdio after install, still no account or API key, still no private Neuruh runtime.

## Upgrading

Replace any `v0.1.8-alpha` pin with `v0.1.9-alpha`. If you pinned `v0.1.8-alpha` and your MCP
client never listed the tools, this is why.
