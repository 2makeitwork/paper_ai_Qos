# AI Service QoS: An Independent Outside-In Measurement Methodology, with Case Study 1 (Qwen3.8-Max / Qoder)

**Author.** 2makeitwork — independent, unaffiliated: no institution is claimed, and none should be
added to any listing, citation or archive record on this project's behalf. The handle is
pseudonymous by choice and is not to be resolved to a person.

> **Released 2026-09-11 as v1.0.1** (methodology v0.1). This snapshot is frozen: later
> corrections and additions ship as a new version with a new tag, never as an edit to the bytes a
> citation points at — cite the tag or the Digital Object Identifier, not a branch. Two version
> numbers mean two different things here: the tag names this public snapshot, while *methodology
> v0.1* names the definitions, which stay unchanged until a second provider has been measured
> (section 7). Every figure quoted in this document set is asserted against the shipped evidence by
> `scripts/analyze.py`, which fails when a number and the evidence disagree and warns when a file
> is edited after the date above.

> **Relationship to the case report.** This is the citable method-and-findings
> document. `report_qwenAliServiceQuality.md` is the vendor-facing case report that
> carries the per-event tables, the asks and the step-by-step reproduction; the
> figures the two share are kept in agreement by `scripts/analyze.py`.

**AI Service QoS — Independent Measurement of What Users Actually Receive.** One submitted request at a time, measured from the client side, with no vendor cooperation and no provider vocabulary. The field incident below is **Case Study 1** — the first demonstration, not the subject.

> **North star.** An independent, outside-in measurement framework for evaluating the reliability, latency, usability, and failure behavior of AI services under real user workloads.
>
> **Methodology version:** v0.1, concepts frozen 2026-09-10. The version ladder (v0.5, a second provider, a continuous observatory) is section 7.
incident as the worked example.**

> **Posture (read first).** This is an **observational case study of a single
> account on a single workstation over one nine-day window**. It is **not a
> benchmark, not a controlled experiment, and not a provider ranking**. Qwen3.8-Max
> through the Qoder CN IDE + Alibaba Cloud Model Studio is used as **one throwaway
> example** to make a measurement method concrete; the example serves the
> methodology, not the reverse. Claims are written as *observed in this field
> sample*, never as population statistics. Every headline number is regenerable
> from `evidence/` by `scripts/analyze.py`, which fails if a figure drifts.

## Abstract

Model-capability benchmarks measure how *smart* a model is. They do not measure
the *service*: how long a request waits, whether it is silently dropped, how a
provider reports an overflow, or how many retries a user spends to get an answer.
As agentic workflows make a single task into dozens of long, context-heavy
requests, that service layer — not raw capability — increasingly decides whether
the work completes. The two are not symmetric in how a user learns of them: capability is disclosed
by the first day of real work, while delivery is disclosed only by failure, and a failure is reported
as one generic banner whatever caused it.

This paper proposes **request-level QoS measurement for AI services**: a unit of
observation (the submitted request), a latency representation (a distribution,
not a mean), a provider-neutral outcome taxonomy (S/T/Q/F/U/A), explicit
denominators (Usable Request Rate and companions), retry accounting that refuses
to hide retries inside successes, and a machine-readable event schema. It fixes
definitions *independently of any provider* so results can be compared across
them. Its novelty is of **perspective, not of method**: the instruments are shared with prior external
measurement, but the vantage — the paying user's side, published as a stratified public aggregate that
checks a provider against its own quality-of-service claim without the provider's cooperation — is
occupied by none of them.

The Qwen3.8-Max / Qoder incident is the worked example. From the client's own
runtime log we reconstruct the request lifecycle (`prompting → streaming →
completed | suspended | error`) with millisecond timestamps, and observe that
long accumulated contexts repeatedly enter a **timeout / resume loop** surfaced as
an opaque "Response timeout" (client code **80408**) — while the service's own
**80411 "Input content too long"** code never fires once across **33** failure
events, and the IDE registry simultaneously declares `maxInputTokens: 180000` and
offers **1M / 400K** presets. We then show the failure is **intermittent** — the
same window succeeds three times between two timeout clusters at a strictly
larger context — which means a **fixed client watchdog against time-varying server
latency**, not a hard context ceiling, is the operative mechanism. The case
demonstrates the paper's central point: a large share of what users experience as
"the AI is broken" is a *service-delivery* phenomenon, invisible to capability
benchmarks and recoverable only with request-level instrumentation.

A companion, fully anonymized evidence bundle and the scripts that regenerate
every figure live alongside this paper.

---

## 1. Introduction

> **Central question.** What service does an AI provider actually deliver to a user submitting real work?

The object of measurement is the request-outcome stream a user experiences. How intelligent the model is, how fast the inference engine runs, how many tokens per second a provider advertises, and whether a published specification is correct are *inputs* to that question rather than the question itself. That is what makes this an **industrial** rather than an academic exercise: it answers the two questions a buyer or operator of an AI service actually asks — *if I give this service my real work, how often do I get a usable result?*, and *what happens when the service is under load, when context gets large, when quota is approached, or when the provider degrades?*

### 1.1 The measurement problem

When an agent session "always fails," the diagnosis available to a user is a
banner. The banner may say *timeout*; the underlying event may be an input
overflow, a rate limit, a gateway stall, or a plan restriction — and the same
UI text can cover several of them. Capability leaderboards are silent on all of
this because they score *answers*, not *delivery*. What is missing is a way to
describe **what the service did** to a stream of real requests: their timing,
their outcomes, their retries — measured from the user's side.

The two things a paid service has to be good at are not symmetric in how a user finds out.
**Capability discloses itself:** within a day or two of real work, a person knows whether the model
is good enough for their task and can decide whether to keep paying — costly to discover, which is
what every benchmark exists to make cheaper, but discoverable. **Delivery does not.** A service that
answers well nine times and stalls on the tenth looks, from inside the tenth conversation, like bad
luck; a token-burst throttle, a saturated region, a plan restriction and an input overflow all arrive
as the same banner; and nothing in the interface accumulates them into a rate, so the pattern becomes
unmistakable only after the subscription is paid for. A model that does not answer is not a capable
model that failed to speak: to that user, in that minute, it is no model at all. That asymmetry — not
the wish for another quality axis — is why this measurement is needed and why the taxonomy in
section 2.4 is built from what the interface reported rather than from what the user suspected.

The novelty that follows is one of **perspective, not of method**: the instruments reviewed in
section 1.4 are shared with prior external measurement and we claim none of them as new; what none
of them occupies is the vantage — a reading taken on the paying user's side, published only in
aggregate, to check what a provider delivered rather than to rank what a system computes.

### 1.2 Why request-level

The natural unit is not the session or the day but the **submitted request**:
submit a task, receive (or fail to receive) a usable response, possibly retry. A
long agentic session is then a *sequence* of request observations sharing
context, not one averaged number. Request-level observation lets us keep latency
as a distribution, attribute failures to a layer (provider/client/user), and —
crucially — see retry burden that a session average would erase.

### 1.3 The concerns behind this work

We state these as the problems that motivated the method, not as research
questions we claim to settle:

- **C1 — Delivery is invisible to capability metrics.** Latency, silent drops,
  timeouts and retries are a distinct axis of "quality" that a capability score
  does not see, yet which dominate the user's experience of agentic work.
- **C2 — Provider vocabulary is not a measurement basis.** Error codes and
  message strings are inconsistent (in this case the same numeric code
  `100400` carries three different wordings, and a code appears as both the
  string `"112"` and integers elsewhere, wrapped in a JSON-RPC `-32603`). Any
  monitoring keyed to one exact phrase under-counts. Measurement must be
  normalized **independently of the provider's terms**.
- **C3 — Client observability is partial and can mislead.** The registry
  contradicts itself on the model's own context limit; the banner text was, at
  first inspection, in no log or transcript; retention is size-based and shallow.
  An **independent, external record** is required to trust a negative probe.
- **C4 — A fixed timeout is not a silver bullet against dynamic load.** When a
  client watchdog is fixed but server latency varies, an overflow that *should*
  return a validation error instead becomes an intermittent silent stall — and a
  request-size threshold alone cannot explain it.
- **C5 — Retries must not be hidden.** A "resume" button that re-sends the
  identical oversized request is a retry with no new information; collapsing it
  into a success would erase the user's actual burden.

The rest of the paper defines the method (§2), the implementation and its
instruments (§3), the case (§4), and what it does and does not establish (§5–6).

---

### 1.4 Positioning against prior measurement work

External, black-box measurement of large-language-model services is **not new** and this paper claims
no priority for it. The instruments are shared with the work below; the purpose is not. Only the
category and the difference are stated here; the per-work record, including what was considered and
deliberately not cited, is in the project's working notes, which are not published — every claim made
below therefore stands on the identifiers given in the table.

| Category | Work | The difference, in one line |
|---|---|---|
| Controlled-load and system benchmarking | LLMPerf (Ray project); MLPerf Inference (Reddi *et al.*, ISCA 2020) | they fix the offered load and score a **system**; we take the arrival process as it comes and score the **request outcome** |
| Benchmarking *methodology* and vocabulary | Internet-Draft *Benchmarking Methodology for Large Language Model Serving* (draft-gaikwad-llm-benchmarking-methodology-01) | a serving-infrastructure standard — throughput, tokens per accelerator-second, scheduling fairness, memory pressure, prefix-cache and guardrail overhead — whose vocabulary our event schema maps onto rather than competes with; note its Application-Gateway boundary measures user-observable latency too, but only under a controlled synthetic load against a system the tester configures, the cooperative frame we drop |
| Longitudinal outside-in monitoring | public LLM latency tracker (`llmlatency/llm-latency-tracker`; `llmlatency.dev/methodology`) | synthetic probes cannot observe a provider restriction, a retry burden, or an answer that arrived and was still unusable |
| Considered, not cited | model-authenticity auditing — GateScope (arXiv:2604.21083) and the substitution audit (arXiv:2504.04715); also excluded: a failover study (arXiv:2607.15899, one narrow angle) and a vendor monitoring page | whether a provider is truthful about the model behind an endpoint is a different question from whether the service answered, in time — and each of those supplies its own ground truth to test against |

**Shared means, different end.** Time to first streamed chunk, latency quantiles, error codes,
retry counts: we reuse them and claim none of them. Each work above holds model behaviour fixed and
varies the load, to produce a number describing a system. We vary nothing, to produce an account of
what a paying user received — and the quantity none of them measures, model intelligence, is the one
a user can settle for themselves, as section 1.1 argues, whereas delivery cannot be settled by
attention.

**No ground truth of our own.** Because nothing reaches us but the provider's response, outcomes are
classified by status codes, error payloads and streamed events, never by whether an answer looks
wrong. That is also why the taxonomy in section 2.4 carries no judgement about answer content, and
why every denominator here is defined by us rather than taken from a provider.

What we therefore claim, narrowly: (i) the **submitted user request** as the unit of
observation, with a six-class outcome taxonomy that separates provider failure from
client-side stall from user invalidation; (ii) **provider-independent denominators**,
so a provider cannot define away its own failures; (iii) **natural workload
normalisation** by task group instead of a synthetic difficulty score or a single
quality index; and (iv) the combination of reliability, latency distribution,
provider restriction and retry accounting into one user-level account of service
quality, reproducible from a client log alone. Each is modest on its own; the claim is the vantage
they share. **What is genuinely new is perspective, not method** — none of the surveyed instruments
measures on the paying user's side *and* publishes the result as a stratified public aggregate, and it
is that combination, not any single metric, that no prior work occupies. The historical analogue is
the distinction between benchmarking a web server and measuring the experience of the web service it
hosts; the contemporary one, taken up in section 7.1, is broadband performance reporting.

Two honesty notes. The case in §4 is the **motivating example, not the novelty
claim** — a single account over ten days cannot rank providers, and we do not
attempt to. And the works above are identified from a systematic search; its working record is kept
with the project's release notes and is not published, so each work is given here with its own
permanent identifier and our characterisation of it must be checked against the primary text
itself — that reading is an open item before submission, not a formality already discharged.

## 2. Measurement Methodology

Definitions here are **provider-neutral by construction** and are intended to be
**frozen before any second provider is measured**, so no definition is bent to
fit a result. The provider's raw codes and message strings are always retained
*alongside* — never replaced by — the normalized categories below.

### 2.1 Unit of observation

The submitted request. Each observation records: `submit_ts`, the first-token and
final-response timestamps when available, an `outcome`, latency when a usable
response arrives, a task classification, and whatever workload metadata exists
(context size, output length, tool use, concurrency). A session contributes many
request observations; it is never collapsed into a single average.

### 2.2 Timestamp model

Three moments matter and must not be conflated:

- **submit** — the request is sent;
- **first token** — the first usable response byte is rendered (time-to-first-token, TTFT); in this incident the observable is the client's first *streamed chunk* edge (`prompting → streaming`), which is what every wait figure in §4 measures, and it is not a rendering-time measurement;
- **completion** — the response is finished (total latency).

For a **stall**, the meaningful quantity is **time-to-stall**: submit until the
service stops producing and the client treats the request as hung. Timestamps
should carry precision and timezone; all timestamps in this case are client-local
(AWST, UTC+8) at millisecond resolution.

### 2.3 Latency representation: a distribution, not a mean

Mean response time is **not** the primary statistic. The primary representation is
a distribution over submitted requests, binned so that the shape (and the
timeout tail) is visible; percentiles (P50/P90/P95/P99) may supplement it, and
raw timestamps are retained so bins can be re-cut later.

| Response time | Share of submitted requests |
|---|---:|
| 0–5 s | % |
| 5–10 s | % |
| 10–20 s | % |
| 20–30 s | % |
| 30–60 s | % |
| 60–120 s | % |
| 120–300 s | % |
| 300 s+ | % |
| timeout / no response | % |

A practical consequence from this case: the client's `[ACPProgressStateMachine]`
lifecycle log (`prompting → streaming`, `streaming → completed`,
`streaming → suspended`) timestamps each edge, so **TTFT, total latency, and
time-to-stall are reconstructable from the log stream alone** for requests the
client saw. Server-side time-to-first-byte is *not* separable from the client
view, so latency here is **client-perceived** — which is, precisely, the object of
study.

### 2.4 Outcome taxonomy

One primary, normalized outcome per eligible request; raw provider text kept
separately:

- **S — Successful response** (a usable response arrived within the protocol).
- **T — Timeout / no usable response** (the observation period elapsed with
  nothing usable; this is a *measured outcome*, defined by our own observation
  timeout, not by the provider's).
- **Q — Provider/account/service restriction** (quota, TPS/TPM rate limit,
  concurrency, plan, context or model restriction). *We do not assume a code
  means weekly-quota exhaustion*; the mapping from a raw code to `Q` is stated
  and auditable.
- **F — Provider/service failure** (5xx, gateway, malformed provider response).
- **U — User/client-side invalidation** (malformed request, invalid key, user
  cancellation).
- **A — Ambiguous / unresolved** (evidence cannot establish attribution).

### 2.5 Usable Request Rate (URR)

A **project-defined** metric with a **project-defined denominator** (not the
provider's):

> **URR** = usable responses ÷ eligible submitted requests, within the defined
> observation protocol.

Companions: **FAUR** (first-attempt usable rate), **EUR** (eventual usable rate,
allowing retries), and **Retry Burden** (extra requests/time spent to reach a
usable outcome). URR is only reported where a complete eligible-submission
denominator exists; where it does not (as in parts of this case), we present
**descriptive** counts and distributions and say so — we do not launder a
`chat_finish` subset into a rate.

### 2.6 Retry treatment

The original request and every retry are recorded separately and linked by an
origin id. We report first-attempt result, eventual result, retry count, and
elapsed time to eventual completion. **A request that needed three resumes is not
equivalent to one that succeeded immediately**, and retries are never folded into
the success count when computing FAUR.

### 2.7 Task taxonomy

Task type is a central dimension and follows *real work*, not an invented
difficulty score — e.g. `coding > rust > debugging`, `coding > java > backend`,
`legal > civil > drafting`, `office > email`, `research > synthesis`, with an
`unknown/other` catch-all and room to grow. This case is essentially
**single-domain (long agentic coding)**; multi-domain distribution is future work,
stated as a limitation.

### 2.8 Natural workload normalization

Users pick a model to accomplish a task; if a cheaper model suffices, economics
pull toward it. So we observe **`task → model selected → plan selected → observed
QoS`** as the workload, rather than compressing everything into one synthetic
difficulty number. Technical variables (input tokens, context size, output
length, tool use, concurrency) remain explanatory features, not the normalization
itself.

### 2.9 Price

Plan price and entitlements (context, quota, concurrency, rate limits, model
access) are recorded as **metadata first**. No universal `QoS ÷ $` score is
constructed.

### 2.10 Statistical reporting

For each provider / model / plan / task group we report: eligible request count
`n`, URR (where the denominator supports it), first-attempt usable rate, failure
distribution, latency distribution, timeout rate, retry burden, task
distribution, and the observation period. **`n` is always shown.** Small samples
are described, never generalized to a population.

### 2.11 Capacity units must be measured, not asserted

Vendors advertise context in **tokens** ("1M context"), but a token is a
vendor-defined unit: different tokenizers split the same text differently, so two
vendors' "1M tokens" are **not** the same capacity; nominal window is not
effective window (output budget, agent scaffolding, and retrieval accuracy that
decays well before the limit); and — as §4.2 shows — one product can advertise 1M
while its own model entry declares 180,000. So this methodology treats advertised
capacity as **untrusted metadata** and requires a provider-neutral, *measured*
unit: normalized payload size and a reference tokenization, and above all the
**largest amount of a shared reference prompt the service accepts and answers
correctly**. Cross-vendor comparability comes from measuring that, not from
reading each vendor's number.

---

## 3. Measurement Implementation

### 3.1 Instruments and their order of trust

Two independent streams are used, deliberately ordered:

1. **The client runtime log (primary).** Qoder CN writes, per agent request, a
   `[ACPProgressStateMachine] State transition: <from> -> <to>` edge with a
   millisecond timestamp and `sessionId`, plus `chat_finish:success:200` /
   `chat_finish:{"code":…}` lines, the `[ChatSessionService] Creating tool_call
   … "title":"resume" … "reasonForCode":80408` line (the timeout banner's only
   durable trace), quota markers, the `Model classes refreshed` registry line,
   and the fetched `error-code-cache.json`. `scripts/latency_from_logs.py` walks
   the transitions per session to reconstruct request boundaries and outcomes.
2. **A DOM watcher (cross-check).** `cdp_watch.js` — project tooling, preserved in the archived
   source copy rather than in this repository — attaches to
   the renderer over CDP and stamps transitions the log may miss. It is treated
   as a **candidate-signal source only**, never authoritative, because it has a
   documented false-positive class: it reads the current message bubble, so an
   assistant reply that *quotes* "Response timeout. Click to resume" or says
   "working"/"thinking" raises `banner_on`/`working`. In one session it logged
   3 `banner_on` and 54 `working` with **zero** matching 80408 / resume events in
   the log — i.e. it saw the paper being written, not a failure. This is kept in
   the study as an *observability* result, not a measurement.

Supporting instruments: the log mirror, a tamper-evident append-only
mirror that also flags in-place edits, exists because retention is shallow (§4.7).

### 3.2 Event reconstruction

A request is the span from a `-> prompting` edge to the next terminal edge:
`-> streaming` (first token), then `-> completed` (S), `-> suspended` (a park —
see the caveat in §4.3), `-> error` (F/other), or `-> cancelled` (U). Time to
first token is `prompting -> streaming`; total latency is `prompting ->
completed`; time-to-stall is `prompting -> suspended`.

**Reconstruction caveat (surfaced by the method itself):** `suspended` is
*over-counted* relative to timeout banners (71 parks vs 33 80408 events in the
case), because the state machine parks for reasons beyond the watchdog
(including tool-permission waits). The `trigger:` field on the transition
separates them directly (`resume_tool_call` 33 vs `permission_request` 38), and
the 33 is a third independent confirmation of §4.2. That a lifecycle log cannot,
on its own, distinguish "stalled" from "waiting for the user" **unless** it reads
`trigger:` is precisely the kind of instrumentation gap this methodology is built
to expose.

### 3.3 Evidence hierarchy

Every claim is tagged as **observation** (a log/registry/string as-is),
**reproducible client behavior** (a resume yields another request and another
park), **provider-documented behavior** (a code's documented meaning), or
**interpretation** (a bounded hypothesis). Interpretation is never presented as
observation. The structure for each finding is *observation → evidence →
interpretation → limitation*.

### 3.4 Reproducibility

the collector reads the installation → `scripts/anonymize.py` produces
`evidence/` (fails on any surviving PII pattern) → `analyze.py` recomputes and
**asserts** every quoted number against `evidence/` and regenerates
`analysis/summary_tables.md`. Reader-side: `python3 scripts/analyze.py`.

---

## 4. Case Study 1: Qwen3.8-Max / Qoder CN — the first demonstration

### 4.1 Environment

Qoder CN IDE (Electron/Chromium 148), Linux; a token-plan subscription on
Alibaba Cloud Model Studio, reached two ways: the BYOK endpoint
`qwen3.8-max-tp` and the system-registry entry `qmodel_38max`. Observation
window 2026-09-01 → 2026-09-09 (client log retention), timestamps local AWST
(UTC+8). Workloads are long agentic coding sessions: hundreds of transcript
entries, large tool outputs, each request re-sending the accumulated context.

### 4.2 Context configuration (observation)

The registry entry for the model declares, in one JSON object:

```json
{"name":"qmodel_38max", "maxInputTokens":180000,
 "contextConfig":{"1M":{"tokenCount":1000000},
                  "200K":{"tokenCount":200000,"isDefault":true},
                  "400K":{"tokenCount":400000}}}
```

The BYOK definition for the same model states `max_input_tokens: 1000000`. The
selectable 1M/400K presets exceed the entry's own 180,000 by 5.5× and 2.2×, and a
user cannot reconcile this from inside the product. *Interpretation:* a
configuration surface exposes capacities it does not honor; *limitation:* this is
client-side metadata and does not by itself prove what the backend will accept.

### 4.3 Request-level outcomes and latency (small-n demonstration)

Reconstructing `scripts/latency_from_logs.py` over a **frozen log snapshot**
(`raw_snapshots/…`; regenerated to `evidence/stats/request_lifecycle.csv` and
asserted by `analyze.py`) yields **308 requests across 10 sessions** — outcomes
S 211, T 71 (parks = 33 timeout + 38 permission dialog), F/U 26 (client-perceived;
**n shown throughout; not a population estimate**). This `agent.log` reconstruction
is a **parallel cut**; the authoritative per-request timings are the field report's
`quest.log` task-tracker stream (cross-checks below).

**Time to first token (n=282)** — bimodal, which is why the mean is not used:

| TTFT | count | share |
|---|---:|---:|
| 0–5 s | 56 | 19.9% |
| 5–10 s | 82 | 29.1% |
| 10–20 s | 26 | 9.2% |
| 20–30 s | 27 | 9.6% |
| 30–60 s | 55 | 19.5% |
| 60–120 s | 27 | 9.6% |
| 120–300 s | 9 | 3.2% |

P50 = 11.3 s, P90 = 61.1 s, max = 132.3 s. About a third of requests wait over
30 s for the *first* token — invisible in a mean, decisive for an interactive
agent.

**Total latency, clean successes (n=179):** P50 = 120 s, P90 = 453 s, max = 1781 s
(~30 min): deep tool-use turns are long, with a heavy tail.

**Parks, and what actually caps them (self-verified).** `suspended` is entered by
**two** causes, told apart by the transition's `trigger:` field — asserted from our
own frozen extract: **33 `resume_tool_call`** (the 80408 timeout banner, a *third*
client-side confirmation of §4.2's count from a stream that never says "80408") and
**38 `permission_request`** (a tool-approval dialog). So `T`=71 = 33 timeout + 38
dialog, **not** 71 timeouts. The vendor's ticket attributes the ceiling to a
**first-packet (首包) gateway timeout**, but **our client data does not support that
reading**: all 33 timeouts *did* stream a first token (their TTFT is a normal
seconds), yet parked a median **305 s** after submit with **none under 55 s and a
floor of 61.1 s**. A first-packet cap would bound TTFT, not total time — so the
~60 s is an **inactivity/idle timeout** (≈60 s of *no streamed bytes*, mid-generation
→ ALB **504** → remapped to **80408**), which is also why **149 of 208 successful
generations ran past 61 s**: the clock resets on each chunk, so only a >60 s *gap*
fails. Measurement caught the provider's own root-cause wording to be imprecise —
an evidence-hierarchy win. (Vendor ticket held as source, not published verbatim.)
The report's task-tracker gives the same shape with a slightly lower first-token
median (**wait-to-output median 9.6 s, P90 49 s, max 132 s, n=245**; generation
median 105 s, P90 477 s, max 2310 s); the ~1–2 s gap vs my TTFT is method (it
pairs the send-press event, not the `prompting` transition). Both agree on the
headline: **bimodal time-to-first-token, a heavy generation tail, and timeouts at
an inactivity gap** — and the human cost is real: 32 of 33 banners were resumed
(median hold 30 s; ~90.5 min summed waiting), while 4 pre-stream rejections
fast-failed in a median **0.7 s** to deliver the same "won't be served"
information the timeout path takes a whole watchdog interval to convey.

### 4.4 Error behavior (raw vs normalized)

- **80408 "Response timeout. Click to resume or switch to another model and try
  again."** — carried by all 33 timeout events.
- **80411 "Input content too long, please simplify and retry"** — the dedicated
  overflow code exists in the fetched dictionary (v1.0.11) yet **fired zero times
  across all 33 events**. The failure mode it was made for is the one the service
  never reports.
- **`100400`** appears with three different messages ("Allocated quota
  exceeded…", "Your token-plan 1-week quota has been exhausted…", "Access
  denied…"); **`"112"` is a string** where every other code is an integer; all are
  wrapped in JSON-RPC **`-32603`**. Normalized to `Q`/`F` with raw text retained,
  these are exactly why §2.4 refuses to equate a code with a single meaning
  (§2.4; provider-doc-documented, not inferred).

### 4.5 The resume / retry loop (reproducible client behavior)

Within a burst, resume re-sends the identical request and parks again — the
densest cluster is 20 parks in a 75-minute window (~4-minute cadence). Across
the whole window, of **211 reconstructed successes, 179 (85%) needed no resume
and 32 needed ≥1** (up to 4), plus 71 parks total. FAUR ≈ 85% of eventual
successes were first-attempt; the retry burden (49 in-band resumes) is the cost
FAUR-vs-EUR makes visible. Retries are recorded separately, never folded into
successes (§2.6).

### 4.6 Session size and the intermittency (the key observation)

One window's two deepest conversations over ~50 minutes produced **park → park →
park → successes (15:40, 16:26, 16:33, 16:48) → park → park** while their stored
context grew monotonically — so a failing request was *smaller* than the request
that succeeded next to it. Attribution note (corrected after the client's phase
log was brought in): the later parks and the successes between them belong to a
second, much smaller conversation in the same window, and the earlier ones to the
190-kilobyte conversation, whose own record also interleaves completed runs
(14:13:39, 14:21:01) with stalls (14:10:52 through 14:23:46). *Interpretation
(bounded):* a fixed client watchdog against time-varying server latency, with
oversized context raising the odds, fits this; a hard context-size ceiling does
not (it cannot clear at a larger size and return at the largest). *Limitation:*
this section is correlational — the paired, causal version of the same claim comes
from the second collection round in §4.8. *Limitation:* the exact server-side
mechanism is not observable from the client; §4.3 proves only that no response was
emitted before the park.

### 4.7 Client observability (what is and is not recoverable)

What the client *does* persist: lifecycle state-transition timestamps, the resume
80408 tool_call, `chat_finish` outcomes, the registry line, and the error-code
dictionary. What it does *not*: the banner's rendered text as such (DOM-only),
and any durable copy beyond a shallow retention. **One correction from the second
round:** per-request context occupancy *is* logged, as
`Context usage sync received for session … usedTokens=…, reportedLimitTokens=…`
(plus a `Context usage update` variant) — an earlier claim in this paper that no
token usage appears in the client log was wrong, because the search was run
against the conventional field names (`usage`, `prompt_tokens`, `input_tokens`,
`total_tokens`) and not against the vendor's own naming. Still absent: output-token
count, cached-input-token count, and any of it inside the transcript. This single
field is what turns "oversized context" from a transcript-size proxy into a
measured quantity, and it carries §4.8. **Retention is size-based and short:** each window's
`agent.log` rotates at 5 MiB keeping only *one* backup generation, so the next
rotation destroys the storm block. Evidence is therefore frozen against
a frozen snapshot plus the mirror's copy, not the mutable live tree.

### 4.8 Second collection round (2026-09-10): the size claim becomes experimental

The day after round 1 was frozen, the same workstation entered another storm, and
for the first time the client's own occupancy field could be read as it happened.
The round is published separately (`evidence/incident_20260910/`, its own
pseudonym namespace `S1…`, its own frozen log snapshot) because round 1's pseudonym
map is immutable; 62 request **episodes** from 55 submitted prompts, three
conversations, 53 completed.

* **The separation, same day.** Every timeout park sits in one conversation at
  **490,789 / 494,193 tokens** of a reported 1,000,000 limit; the largest context
  that completed anywhere in the round is **452,447 tokens**. Both figures come
  from the client's own log line, not from a transcript proxy. Read this as a
  same-day boundary, not a threshold: in round 1's pooled data the ranges overlap
  (180 of 203 successful requests sit above the smallest stalled context), so size
  remains a probability factor.
* **The paired experiment.** The stalled conversation had two submitted prompts
  that produced five stalls with **no streamed chunk at all**; after the client's
  context-compaction control ran
  (`Compression API call completed for session compact`, occupancy
  494,193 → 117,153), the next send, carrying **85,115** tokens, produced its
  first streamed chunk in **8.43 s** and completed in **10.08 s**. Same
  conversation, account, model and preset, minutes apart, one variable changed.
  It also identifies the operator remedy the banner never mentions: compact, do
  not resume.
* **Two stall clocks.** Send-to-stall (the operator's held time: 125.3 s, 127.1 s,
  one banner left unanswered 4,860.7 s) and first-chunk-to-stall (the client's
  watchdog clock: 60.9 s, 61.1 s) are reported as separate measures. The
  ~66-second difference between a fresh send and a mid-request resume on an
  identical payload is **unexplained** and is put to the vendor as the first
  question in `ask_vendor.md`.
* **Three negative results.** Panel visibility changes nothing (a conversation
  hidden 0.76 s after sending took its first chunk 1.34 s later and finished in
  2.58 s). Cache residency changes nothing measurable (at 323,270 then 323,737
  tokens, a 7.9-minute gap preceded a 17.58 s wait and a 27.7-minute gap a
  17.11 s wait) — which is why cold-cache eviction is not offered as the
  explanation of the 28.03 s outlier at 251,788 tokens. And context cannot be
  inflated by instruction: a turn designed to add ~100,000 tokens added **851**,
  because the agent answered a line-count question with a counting command.
* **Latency is load-dominated, not size-dominated.** The seven waits for first
  chunk across a deliberate size climb (29,646 → 323,888 tokens) were 2.62, 6.92,
  10.93, 7.94, 28.03, 5.14 and 6.21 s: not monotone in size. The method therefore
  reports a distribution plus the binary outcome, and never a size-only curve.

---

## 5. Analysis

### 5.1 Established observations (direct)

- The registry entry self-contradicts on context (`maxInputTokens: 180000` vs
  selectable 1M/400K; BYOK `max_input_tokens: 1000000`) — verbatim client data.
- 33 timeout events over the window, **all 80408**, **80411 never fired**.
- Request lifecycle is reconstructable from the log: 308 requests / 10 sessions,
  with the TTFT, generation-tail and park/watchdog breakdown in §4.3.
- Timeouts cluster by window and by *viewed* session; parks (71 = 33 timeout +
  38 permission dialog, split by `trigger:`) — the 33 is a third independent
  confirmation of the 80408 count.

### 5.2 Consistent interpretations (bounded)

- The operative mechanism is a **fixed ~60 s inactivity/idle timeout (an ALB 504
  when the stream goes silent for ~60 s, remapped to 80408) meeting variable
  server latency**, with oversized context a risk factor, not a
  threshold — the timeout→success→timeout-at-larger-context sequence (§4.6) is
  the discriminating observation.
- Overflow is **mis-signaled**: a dedicated 80411 exists but the condition
  surfaces as 80408, so user-facing guidance and any code-keyed monitoring are
  systematically wrong for this class.

### 5.3 Unresolved

The exact server-side path (request queue, prefill stall, token-burst throttling, a plan's capacity budget, gateway); whether
account/plan state contributes; a clean causal context-size/latency curve
(would need a controlled sweep — deferred, §7); and separating timeout parks from
tool-permission parks (now resolved: `trigger:` asserts 33 timeout / 38 dialog from
the client, §4.3). What remains unresolved is only *why* the stream goes silent for
>60 s (server prefill/decode vs network) — and that our client evidence reads the
~60 s as an **inactivity** floor, not the vendor's stated **first-packet** cap.

### 5.4 Methodological implications

The method *earned its place by what it caught*: shallow retention (§4.7), the
banner/80411 signaling gap (§4.4), the `suspended` ambiguity that broke a naive
timeout count (§3.2), and a DOM instrument that failed positive control on
quoted text (§3.1). Each is an instrumentation requirement for measuring service
QoS independently of a provider — which is the paper's thesis, demonstrated.

---

## 6. Limitations

Stated prominently; they constrain every number above.

- **One account, one workstation, one client, a nine-day retention window.** No
  provider-wide or population claim; "observed in this field sample" only.
- **Client-perceived latency only**; timeouts are **right-censored** (we see
  submit and the park, not the server's own completion or first byte).
- **Per-request *input* occupancy is logged by the client (`usedTokens`), but output tokens, cached input tokens and the resource cost of a request are not**, so request size is bounded
  from transcript growth — a **lower bound**, not a measurement.
- **Advertised context ("1M") is not a comparable unit** (§2.11): per-vendor
  tokenizers, nominal-vs-effective window, and here an advertised 1M against a
  self-declared 180,000 — capacity numbers are untrusted until measured on a
  shared reference payload.
- **The stall *cause* is server-side and unobserved**: we now self-verify the ~60 s
  as an inactivity floor and the 33/38 park split from `trigger:` (§4.3), but *why*
  the stream goes silent is inferred — and it does **not** match the vendor's
  "first-packet" root-cause wording.
- **`suspended` conflates** timeouts with tool-permission waits unless the
  `trigger:` field is read (we now split them, 33 timeout / 38 dialog, §4.3).
- **Single domain** (long agentic coding): the task taxonomy (§2.7) is untested
  across domains here.
- **Small n** throughout; the 308-request reconstruction is frozen into
  `evidence/stats/request_lifecycle.csv` (from a log snapshot) and asserted by
  `analyze.py`, but remains one account / one window, not a population.
- **Observational, not controlled:** the causal role of context size is
  **not** established, and **"the 1M preset causes the failures" is explicitly
  not claimed**.
- **No resource denominator.** Every quantity here is per *request*, because a client cannot see
  what the provider spent: power draw, fleet or region allocation, and the concurrency budget behind
  an account tier are all invisible from outside. So a good usable request rate may mean a better
  service or simply a bigger deployment, and this method cannot rank providers on efficiency — how
  many users a given capacity can serve, or how good the answer is per unit of power consumed. That
  comparison needs provider telemetry, which is why it is put to the provider in `ask_vendor.md`
  rather than attempted here.
- **No second provider**, so provider-neutrality of the schema (§7) is proposed,
  not demonstrated.

---

## 7. Roadmap: from one case study to an AI-service quality-of-service observatory

The deliverable is a **measurement framework and the dataset it produces**, not a report on one
provider. Qwen3.8-Max / Qoder CN is Case Study 1: the first system measured, chosen because the
incident happened, and deliberately *replaceable* — the instrument was built to work without it.
Provider neutrality is claimed at the definition level (section 2.3) and **not yet demonstrated
empirically**, which is exactly what Stage 3 below is for.

| Stage | Content | State |
| --- | --- | --- |
| **0** | Methodology v0.1 frozen; Case Study 1; public repository | **done (this work)** |
| **1** | Release: methodology + case study + request-level dataset + archive identifier | **in progress** |
| **2** | Controlled single-factor experiments: request size, context accumulation, fresh versus long-lived conversations, repeated identical requests, retry behavior → methodology v0.5 | three run informally in section 4.8; the controlled versions not run |
| **3** | A second provider, measured with the same definitions and no new ones | not started |
| **4** | Several providers and real task groups → benchmark v1.0 | not started |
| **5** | Continuous collection: an **AI-service quality-of-service observatory** answering "how reliable was provider X for coding tasks in September?", "does long-context work materially raise timeout probability?", "which provider has the better quality-of-service frontier for *my* workload?" | not started |

Two constraints carried forward from section 1.1: an observatory publishes **distributions and
per-class rates, never an aggregate score or a provider ranking**, because a scalar cannot separate
a provider that says "input too long" from one that times out; and every stage keeps the outcome
classes defined independently of any provider's vocabulary, so a provider renaming its error codes
does not silently redefine the measurement.

This section sketches the *next* phase only; nothing here is built or claimed by
the current data. The intended sequence: **freeze** the schema, outcome taxonomy,
denominator, retry protocol, task taxonomy and reporting rules (§2) — then
re-collect the *same* definitions against a **second provider** to test whether
the schema, denominator and taxonomy survive unchanged. Only after that would
distributions, a multi-dimensional **QoS Frontier** (no single scalar), and a
public observatory be meaningful. The present case is the first worked example,
not that system.

**Methodology-freeze statement:** the definitions in §2 are to be fixed before
any additional provider is measured, so no definition is adjusted after seeing
another result — the primary guard against methodology drift.

### 7.1 The end this serves

The framework above is the means. The purpose is an institution that does not yet exist: a **public,
user-side measure of AI-service delivery** — passive instrumentation that reads the same client log
this paper reads, deployed inside ordinary integrated-development-environment and agent interfaces,
and aggregated across many such clients into distributions that are comparable across providers and
checkable with no provider's cooperation. It reports what neither a capability leaderboard nor a
provider status page does: whether the service answered, in time, for *this* plan, *this* task group,
*here*, at *this* hour.

Its novelty is one of **perspective**, not of method or data. No instrument surveyed in section 1.4
measures from the paying user's side and publishes the result as a stratified public aggregate: the
external monitors there send fixed synthetic probes, and the serving-benchmark methodology needs the
operator's cooperation. The closest working analogue is broadband performance reporting, not another
AI benchmark — providers advertise speeds "measured under controlled conditions" and publish almost
nothing about the conditions, while the number users can actually consult is a public,
measurement-based service broken out by provider, technology, region and time of day, reliable
precisely because it is reported by the party who experiences it rather than by the party being
measured. An AI-service equivalent would let a buyer settle the question section 1.1 says they
cannot: not *is this model smart* — which discloses itself in a day — but *does it deliver, for my
situation*, where the honest answer differs between two neighbours the way the best carrier in one
district is not the best thirty kilometres away. Because it is collected on the user's side and
published only statistically, it is the one measure of delivery a provider cannot special-case the
way it can a benchmark's fixed synthetic probes.

Two things follow, held here as incentives rather than achievements. The measurement is adversarial
to the seller: a provider's quality-of-service claim becomes independently verifiable, so such an
instrument would be resisted — and, as the telecom case predicts, resisted on security and privacy
grounds rather than on the measurement's merit. And a user-side dataset is a *precondition* for any
regime in which service-quality claims can be checked at all, which is the strongest reason to build
it; that is a claim about what becomes possible, not about what this paper's data proves. Two design
duties belong to that goal and are not yet discharged. The observation is a request's outcome and
timing and never its content, and a published aggregate pools across time, so no single request or
hour is carried into the result; the residual duty is a minimum-cell-size rule, because a bin so rare
as to hold only a handful of requests — an uncommon plan in a quiet region for an unusual task group —
edges toward naming a subscriber, and a corporate user's traffic is itself commercially sensitive.
And whether to press the accountability point in regulatory terms is a choice we flag rather than
take, because advocacy would read against the provider neutrality the rest of the paper defends.

---

## 8. Conclusion

The conclusion is **not** "Qwen is bad." It is that **AI service quality contains
behavior that model-capability benchmarks never see** — latency distributions
with heavy tails, mis-signaled overflows, retry loops, and observability gaps —
and that **request-level, distribution-based, provider-independent measurement
exposes it.** This single, ordinary field incident produced all four in a week of
normal use, which is the argument for measuring delivery (not just capability) at
the request level. The next step is to freeze the method and test it on a second
provider — a step left deliberately open, to be taken only if there is interest.

---

## Appendices

**A. Raw event schema (proposed, provider-neutral).** `event_id, provider,
product, client, model, plan, region, task_group_primary, task_group_secondary,
submit_ts, first_token_ts, response_ts, observation_timeout_ts, outcome(S|T|Q|F|U|A),
provider_error_code, provider_error_message, http_status, retry_of_event_id,
input_tokens?, output_tokens?, context_tokens?, request_size?, concurrency?,
tool_use, session_id, source_log, evidence_reference` — each field tagged
observed / provider-reported / inferred / unavailable where useful.

**B. Error-code dictionary.** `evidence/config/error-code-dictionary_extract.json`
— entries for **80408** (timeout), **80411** (input too long, never fired),
**40429** (tool limit), **100400** (quota/access, 3 wordings), **112**
(string code, pricing redirect), wrapped in **‑32603**.

**C. Timeout event table.** `evidence/logs/timeout_resume_events.csv` — 33 rows
(ms timestamps, pseudonymized tool-call ids, all `reasonForCode:80408`);
by-window tally in `evidence/logs/resume_events_by_window.txt` (window3 = 27).

**D. `chat_finish` census.** `evidence/logs/chat_finish_census.txt` — window-scoped
245 lines: 225 `success:200`, 20 error payloads.

**E. Session-size table.** `evidence/stats/session_size_stats.csv` (20 sessions);
failing-session growth curve `evidence/stats/context_growth.csv`.

**F. Registry / configuration evidence.**
`evidence/config/model_registry_qmodel_38max.txt`,
`evidence/config/custom_models_byok.json`,
`evidence/config/runtime_model_selection.txt`.

**G. Measurement scripts.** Published in this repository: `anonymize.py` (raw dump to
`evidence/`, exiting nonzero if any forbidden pattern survives), `analyze.py` (asserts every
frozen number, including the request-lifecycle table), `latency_from_logs.py` (reconstructs §4.3
from a log snapshot and emits `evidence/stats/request_lifecycle.csv`), and the two checks named
above. Held as project tooling and preserved in the archived source copy rather than here: the
collector, the log mirror (retention and tamper-evidence) and the DOM watcher (cross-check only,
candidate signals). The lifecycle input is a **frozen snapshot**, so `analyze.py` can assert
it without re-reading the mutable live log.

**H. Reproduction.** Install Qoder CN ≥ 1.1.x with a Model Studio token-plan BYOK
model; select the 1M preset; run a deep tool-use session past ~150 KB re-sent
context; observe intermittent `Response timeout` banners and that fresh
small-context sessions respond. From logs alone: `grep '"title":"resume"'
~/.config/QoderCN/logs -r` (each event 80408, no `chat_finish` line); and
`python3 scripts/latency_from_logs.py` to reproduce the §4.3 distributions.

**I. Screenshot.** `evidence/screenshots/timeout_storm_ui.png` — consecutive
timeout banners + Continue button in one transcript.

**J. Data dictionary / provenance.** Field meanings as in §2; all identifiers
pseudonymized per `anonymization.md`; timestamps and error strings exact;
observation timezone AWST (UTC+8).

**K. Data request protocol.** `DATA_REQUEST.md` — the provider-neutral, per-request
fields we require from any provider to verify a service-QoS claim server-side
(join key, first-token/timeout timestamps, gateway timeout config, token accounting
incl. reasoning-vs-content, true enforced limit + tokenizer, retries, load). Used
to request the Qwen/Qoder records behind the §4.3 inactivity-timeout finding.
