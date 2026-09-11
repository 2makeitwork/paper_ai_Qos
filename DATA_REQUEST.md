# Data Request Protocol — per-request evidence to verify a provider's own QoS claim

> **Released 2026-09-11 as v1.0.2** (methodology v0.1). This snapshot is frozen: later
> corrections and additions ship as a new version with a new tag, never as an edit to the bytes a
> citation points at — cite the tag or the Digital Object Identifier, not a branch. Two version
> numbers mean two different things here: the tag names this public snapshot, while *methodology
> v0.1* names the definitions, which stay unchanged until a second provider has been measured
> (section 7). Every figure quoted in this document set is asserted against the shipped evidence by
> `scripts/analyze.py`, which fails when a number and the evidence disagree and warns when a file
> is edited after the date above.

*Companion to `paper_ai_QoS.md` (§2.11, §3.2, §4.3, §6). Provider-neutral: this is
what we request from **any** provider before a service-quality claim — including a
provider's own — can be checked server-side rather than inferred from the client.*

## Principle

Client logs measure what the **user experienced**; they cannot see why a request
stalled. When a provider attributes a failure to a specific mechanism (e.g. "a
gateway 504 on the first packet at ~60 s"), that mechanism is **verifiable only
with provider-side, per-request records joined to the client's events.** So the
ask is deliberately small: enough to reproduce the provider's own conclusion, and
no more.

## Tier 0 — the join key (nothing else is usable without it)

- **T0.1** A **request/trace id that appears in both the client and the provider
  log for the same request.** If the client and gateway stamp different ids, a
  mapping. Without a shared key, timing/token fields cannot be aligned to the
  events we can see.

## Tier 1 — timing that resolves the mechanism

- **T1.1** Per request, provider-side timestamps in ms with a stated clock/zone:
  `t_received`, `t_model_start`, **`t_first_token`** (first response byte emitted),
  `t_last_token`, `t_end`, and **`t_timeout_emitted`** (when the gateway/edge gave up).
- **T1.2** The edge/gateway **timeout configuration**: idle vs request/connection
  timeout value; whether it fires on **first byte** or on **inactivity**; whether
  SSE **heartbeat/keepalive** is sent and its interval; whether the error is raised
  at the edge or upstream.
- **T1.3** The **raw log lines the provider cites** as its own evidence.

## Tier 2 — capacity and tokenization truth

- **T2.1** Per request, token counts **as the service measured them**: prompt/input
  tokens **including system prompt + tool definitions + memory blocks**;
  cached-vs-fresh prompt tokens; output tokens; and **reasoning/thinking tokens
  reported separately from content tokens** — plus whether the reasoning phase
  emits **any byte** before the first content token (this is what "one continuous
  generation" is measured against).
- **T2.2** The provider's **true enforced input-token limit**, how advertised
  presets (e.g. 200K/400K/1M) map to it, and the **tokenizer name/version** — so a
  "context" figure has a unit. Effective/usable window vs nominal (retrieval decay,
  internal truncation) if they differ.
- **T2.3** Raw request payload size in **bytes**, and the largest payload accepted.

## Tier 3 — outcome, retries, load

- **T3.1** For failing requests, the real model-layer **HTTP status + error body**:
  did the backend ever emit a context-length / 413 / "input too long" error, or
  **only a gateway timeout**? The threshold separating the two.
- **T3.2** Every **retry** marked (provider-auto vs user), each with its own
  id/ts/outcome, and confirmation whether the identical context was resubmitted
  verbatim — so first-attempt vs eventual rates are authoritative.
- **T3.3** **Load/state** at those timestamps: tenant rate-limit (TPS/TPM) / quota
  state, concurrency, region — to separate capacity stalls from size stalls.

## Format

Structured export (**JSONL or CSV**), **one row per request and per retry**, keyed
by T0.1, for the named time windows, timestamps in ms with timezone. A ready
field list mirrors the event schema in `paper_ai_QoS.md` Appendix A.

## Why this is minimal

It asks only for fields the provider already logs to reach its own diagnosis. A
provider that concludes "it was a 60 s first-packet gateway timeout" can supply
`t_first_token`, `t_timeout_emitted`, the timeout config, and the join id without
new instrumentation — which is exactly what makes the claim falsifiable.
