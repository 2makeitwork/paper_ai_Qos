# Questions for the vendor (Qoder CN IDE) and the model service (Alibaba Cloud Model Studio)

> **Released 2026-09-11 as v1.0.1** (methodology v0.1). This snapshot is frozen: later
> corrections and additions ship as a new version with a new tag, never as an edit to the bytes a
> citation points at — cite the tag or the Digital Object Identifier, not a branch. Two version
> numbers mean two different things here: the tag names this public snapshot, while *methodology
> v0.1* names the definitions, which stay unchanged until a second provider has been measured
> (section 7). Every figure quoted in this document set is asserted against the shipped evidence by
> `scripts/analyze.py`, which fails when a number and the evidence disagree and warns when a file
> is edited after the date above.

Everything here is stated as *tested by us, answer unknown to us*. We measured from
the client's own runtime log; we did not probe the service, and several of these
can only be answered from inside the provider. Nothing below is a claim that the
vendor is wrong — they are the gaps an outside observer cannot close.

Answer format we would need to fold a reply into the paper: the mechanism, the
number, and whether it is documented anywhere a user can read.

## A. Why a fresh send costs about sixty-six seconds more than a resume

Measured, one conversation, one account, identical payload of 490,789 to
494,193 tokens of a reported 1,000,000 limit:

| Path | Measured interval | Value |
|---|---|---|
| Continue clicked (mid-request resume; `suspended → streaming`, trigger `user_resume`) | resume click → next banner | 60.9 s, 61.1 s |
| Stop pressed then a new send (`cancelled → prompting`, trigger `user_message_chunk`) | send → first banner | 125.3 s, 127.1 s |

Both paths re-offer the same conversation. Questions:

1. Where does the client's timeout clock start — at dispatch, at request
   acceptance, or at the first streamed chunk?
2. What does a fresh send do that a resume does not — a full re-accept, a
   re-prefill of the context, a queue insert, or a silent first attempt that is
   retried before the banner?
3. Is the sixty-one-second figure a fixed client configuration, a per-plan
   setting, or a proxy timeout (we observed the reply arrive as an
   `80408` "Response timeout" banner, and nothing upstream of it is visible from
   the client)?

## B. The timeout code choice

The fetched error-code dictionary contains `error.code.80411` — "Input content too
long, please simplify and retry" — and across 95 observed failures in two
collection rounds it **never fired once**; every oversized-context failure arrived
as `80408` "Response timeout". Question: is an over-capacity request that stalls
inside the service distinguishable from a slow-but-valid request at the point where
the code is chosen, and if not, can the service add a distinct code (or reuse
`80411`) so the client can tell the operator "shrink the conversation" instead of
"wait and retry"?

## C. Context occupancy is logged, two other numbers are not

The client reports, per request, `Context usage sync received … usedTokens=…,
reportedLimitTokens=…`. That single field is what let us pair size with outcome.
Still missing:

1. Output-token count for the turn, and the model's reasoning-token split if any.
2. **Cached input tokens.** If the service returns a cache or prompt-reuse figure,
   the client discards it. We tested whether cache residency explains latency
   (a 7.9-minute versus a 27.7-minute idle gap at the same size: 17.58 s versus
   17.11 s — no effect we could detect), but only the provider can say whether a
   cache exists, what its key is, and how long entries live.
3. Confirmation of what `usedTokens` counts: prompt only, or prompt plus system
   blocks, tool schemas and memory? It is the number our capacity statement rests
   on.

## D. The advertised context presets versus the declared input limit

The registry entry for Qwen3.8-Max carries `"maxInputTokens":180000` while
offering selectable presets of 200K (default), 400K and 1M, and the bring-your-own
definition for the same model states `max_input_tokens: 1000000`. Measured
behaviour over two rounds: requests at 452,447 tokens completed; requests at
490,789 and above failed with no streamed output at all. Questions:

1. Which of the three numbers is the contract, and is the real limit dynamic
   (shared capacity, per-plan tier, time of day)?
2. Is the 180,000 figure a stale field, a billing-relevant limit, or a soft
   quality threshold?
3. Will the preset list be capped at the enforced limit, so a user cannot select
   a capacity the service will not honour?

## E. The running-task quota: stated as a message, never as a number

The dictionary ships `error.code.task.running.quota.exceeded` ("Running task quota
exceeded"). It **never fired** in either round, so we did not probe for it — we
simply report what we observed: at most **two** conversations were in the
`Running` state simultaneously (ten overlapping intervals, both reaching
`Completed`), never three. Question: what is the concurrent-running-task limit per
plan, and can it be surfaced in the product or the pricing page so a user running
two or three chat tabs in parallel knows what they are spending?

## F. Blocked states that are invisible unless you are looking at that exact panel

Observed, all client-side:

1. A conversation can wait indefinitely on a tool-approval dialog with no signal
   outside that panel — we measured waits of 69.25 s and about twelve minutes,
   discovered only because we read the log.
2. A second Continue click is dropped with a log line (`resume: ignored, current
   state=streaming`) but no user feedback.
3. Text typed while a conversation is parked enters a queue that writes **no log
   line anywhere** — we searched every published extract for queue, defer and
   hold-back markers and found none — so the gap between the operator's intent and
   the actual dispatch is unrecoverable even by this method.
4. The timeout banner's own wording ("click to resume or switch to another model")
   is advice we measured to be counter-productive for this failure class: resuming
   re-sends the identical oversized request. The action that worked was the
   context-compaction control (494,193 tokens down to 117,153, then a completion
   in 10.08 seconds), which the banner never mentions.

Questions: can 1 to 3 be surfaced and logged, and can 4 become a contextual
recommendation after repeated identical failures in one conversation?

## G. What we ask for in exchange for nothing

The client-side phase and occupancy log lines already exist and made this whole
study possible without vendor cooperation. The one thing that would help outside
observers most, at almost no cost: **keep them, and write them into the
transcript** rather than only into rotating runtime logs, and publish the field
meanings. Everything in our paper is reproducible from the client alone; that is
the property worth preserving.

## H. What resource was behind the answer? — the denominator a client cannot see

Everything above asks what the service *said*. This asks what it *spent*, because without it no
cross-provider comparison can be honest about efficiency:

1. Per request (or per hour, per account tier), what **compute or power** was assigned? A
   "1 megawatt of capacity serves how many users, how well, for how long" figure is the one number
   that makes two providers comparable when one runs a bigger fleet than the other.
2. Is the concurrency behind this subscription tier a **capacity budget**, and when that budget is
   reached, is the request queued silently, dropped without a code, or served by a degraded path?
   Our data shows 60-second and multi-minute stalls with no distinguishing signal; a load-shedding
   policy would explain them.
3. Do you route accounts across **regions or data centres**, and can a client be told which pool
   served a request? If the serving pool changes under load, then a client-side latency measurement
   is partly a measurement of your scheduling decision — which we would like to be able to state
   instead of infer.

We do not expect these to be answered; they are here because they are the boundary of what an
outside-in method can establish, and the questions a provider-side record could settle.
