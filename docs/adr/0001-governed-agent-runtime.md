# ADR 0001: Governed agent runtime

- Status: Accepted
- Date: 2026-08-23

## Context

The software factory needs LLM-driven planning and implementation without allowing model output to become an unrestricted operating-system capability. The same agent workflow must also be able to move between hosted NVIDIA NIM and other model providers later.

## Decision

Agents return typed Pydantic contracts. LangGraph owns workflow state and sequencing. Side effects go through an internal tool registry guarded by a workspace policy. Files are resolved beneath a per-project root, commands are referenced by allow-listed names, and tool requests have idempotency keys.

MCP is an integration boundary over the same tool registry, not the internal execution model. This keeps protocol concerns separate from authorization and execution. Model provider SDKs are hidden behind the structured model gateway.

## Consequences

- No agent receives a raw shell or host filesystem handle.
- MCP and native callers receive the same policy behavior.
- Deterministic quality gates decide whether a release candidate can be approved.
- Adding richer tools requires an explicit registry entry and policy decision.
- Production deployment still needs stronger process/container isolation, secrets brokering, persistent state and network egress controls.
