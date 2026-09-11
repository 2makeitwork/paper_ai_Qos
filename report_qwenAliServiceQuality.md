# Case Study 1 — Qwen3.8-Max through Qoder CN + Alibaba Cloud Model Studio

> **Released 2026-09-11 as v1.0.1** (methodology v0.1). This snapshot is frozen: later
> corrections and additions ship as a new version with a new tag, never as an edit to the bytes a
> citation points at — cite the tag or the Digital Object Identifier, not a branch. Two version
> numbers mean two different things here: the tag names this public snapshot, while *methodology
> v0.1* names the definitions, which stay unchanged until a second provider has been measured
> (section 7). Every figure quoted in this document set is asserted against the shipped evidence by
> `scripts/analyze.py`, which fails when a number and the evidence disagree and warns when a file
> is edited after the date above.

*Advertised 1M context, delivered timeouts. Part of **AI Service QoS — Independent Measurement of What Users Actually Receive** (methodology v0.1): this is the vendor-facing case report; the method itself is `paper_ai_QoS.md`.*

> **Relationship to the paper.** `paper_ai_QoS.md` is the citable document for the
> method and the findings. This file is the **case report written for the vendor**:
> the six-finding summary, the unit vocabulary, the per-conversation event tables,
> the asks, the reproduction commands and the second collection round in full.
> Where the two overlap, the paper governs; `scripts/analyze.py` fails the build if
> a shared figure or a corrected wording drifts apart between them.

**Field report — service-quality investigation, September 2026**

| | |
|---|---|
| Author | 2makeitwork (solo operator, single workstation) |
| Observation window | 2026-09-01 → 2026-09-09 (round 1, runtime-log retention of the installed client) plus a second collection round on 2026-09-10 (§9) |
| Client | Qoder CN IDE 1.1.3 (commit `fd1459de`), Linux 7.0.0-31 (Ubuntu) |
| Models under test | Qwen3.8-Max on Alibaba Cloud Model Studio **token-plan** subscriptions, both delivery paths: BYOK endpoint `qwen3.8-max-tp` (id `custom:model_…`) and the IDE's system-registry entry `qmodel_38max` — see §2 |
| Evidence | Machine-generated log extracts, the client's fetched error-code dictionary, the client's model registry, transcript statistics — anonymized in `evidence/`, regenerable via `scripts/` (see `methodology.md`) |

*Personal paths, workspace names, session/account identifiers and API keys are
removed throughout; the scrubbing policy is `anonymization.md`, and it is
machine-checked by `scripts/anonymize.py` (which fails on a surviving pattern).*

## 1. Summary

An agentic coding session that appears to fail "always" was traced through the
client's own records. The failure is the combination of (a) a context size the
service advertises but does not honour, and (b) an overflow that surfaces as an
opaque "response timeout" instead of an input-too-long error — after which the
client's resume button re-sends the identical oversized request. Within a burst
the loop is deterministic (every resume re-times-out), but across a longer span
the *same* large request sometimes succeeds minutes later: the trigger is a
**fixed client watchdog meeting time-varying server latency** — measured off the
client's own state machine as ~60 s of silence between chunks, §4.3 — with
oversized context raising the odds rather than acting as a hard gate.

Six findings, all evidenced in §4:

1. **The vendor's own registry contradicts itself on Qwen3.8-Max's context.**
   The model entry declares `"maxInputTokens":180000` while offering the user
   selectable context presets `"1M":{"tokenCount":1000000}` and
   `"400K":{"tokenCount":400000}` (default 200K). The BYOK model definition
   for the same model states `max_input_tokens: 1000000`. A user cannot
   reconcile 180K with 1M from inside the product.
2. **Exceeding the real capacity fails as a timeout, never as an
   input-too-long error.** The client's fetched error dictionary (v1.0.11)
   contains a dedicated code — `error.code.80411: "Input content too long,
   please simplify and retry"` — but across nine days and all 33 failure
   events, 80411 **never fired once**. Every event carried
   `reasonForCode: 80408` ("Response timeout. Click to resume or switch to
   another model and try again.").
3. **The timeouts are not in the transport, they are the model call.** The
   client logs every chat completion with a `chat_finish:` line: successes as
   `success:200`, quota/account failures with their code. The 33 timeout
   events produce **no `chat_finish:` line and no failure marker at all** —
   the request is accepted and then answers nothing until the client's
   watchdog fires. This is a server-side stall surfaced as a client banner.
4. **The resume button is a no-new-information retry, and the failure beneath
   it is intermittent.** Pushing it re-sends the identical request (same
   context, same size), so within a burst it re-times-out deterministically —
   observed cadence on 2026-09-09: 20 resume events between 13:36 and 14:51 in
   one chat window, ~4 minutes apart, matching the operator's screenshot of nine
   consecutive banners. But the same conversation also *completes runs between
   those banners* (`Completed` at 14:13:39 and 14:21:01, inside the 14:10–14:23
   failure cluster) at a context that only ever grew, and a second chat box in
   that window, holding ~12× less stored content (16 K vs 187 K message chars),
   timed out four times (15:24, 15:33, 17:04, 17:05) between runs that finished
   at 15:40, 16:26, 16:33 and 16:48. A fixed-size ceiling cannot flip
   success↔failure at monotonically rising size; a **fixed client timeout
   against variable server latency** can. Oversized context raises the odds but
   is not the sole gate (§4.2).
5. **Two distinct interruption modes with different recovery UX, and
   inconsistent codes between them.** Timeout mode shows a banner + resume
   button (code 80408). Quota/account mode shows a different banner with no
   button and requires typing a new prompt; its payloads are inconsistent:
   code `100400` appears with three different wordings ("Allocated quota
   exceeded…", "Your token-plan 1-week quota has been exhausted. The quota
   will reset at 09-08 01:45:00 UTC…", "Access denied…"), and code `"112"`
   is a **string** where every other code is an integer, all wrapped in
   JSON-RPC `-32603`. Any monitoring keyed on one exact phrase undercounts.
6. **The client's own persistence hides the failure.** The timeout banner text
   appears in no log and in no transcript file (it is DOM-rendered from the
   error-code dictionary); the transcript JSONL stores no per-message
   timestamps and does not reliably store every prompt. The events are only
   reconstructable from the runtime log lines of the resume button
   (`"title":"resume"` tool calls) — though the same runtime log turns out to
   hold every phase boundary of every turn, which is what supplies the latency
   and hold-time numbers in §4.7. **One correction from §9:** context occupancy
   *is* logged per request (`Context usage sync received … usedTokens=…,
   reportedLimitTokens=…`), so request size does not have to be proxied from
   transcript characters; what is still missing is output-token count, cached
   input tokens, and any of it inside the transcript.

## 2. Setup

Long-running agentic sessions (60–600+ transcript entries, large tool outputs,
every request re-sending the full conversation) on one account. Both model
paths observed are Alibaba Cloud Model Studio token-plan endpoints; they
differ only in delivery — the IDE's system-registry entry `qmodel_38max` and
the BYOK custom model `qwen3.8-max-tp`. The system path's bundled quota was
exhausted well before the observation window (consistent with the early
`100400`/`112` quota and pricing-redirect traffic, §4.4), so the traffic in
this study runs on the token-plan
BYOK path with the 1M context preset selected; the system entry still carries a
400K preset selection but could not serve requests. The failure the operator
reported: "the other window always fails" — one specific chat window looping
on timeouts, while fresh windows on the same account and model worked
normally.

## 3. Method

Anchors, all verified against the installed client (file-by-file provenance in
`methodology.md`, which also states what re-runs from what — the extracts below are a
frozen record of the study window, re-derived from `evidence/` rather than rebuilt
from the provider):

- **Timeout events**: `[ChatSessionService] Creating tool_call …
  {"title":"resume","rawInput":{"chatTask":"CONTINUE_TASK","reasonForCode":80408}}`
  — logged when the banner+button appear; the button press logs
  `[ACP] Permission resolved`.
- **Quota/account events**: markers `ACP session/prompt failed`,
  `State transition: streaming -> error`, `Handling request error for session`.
- **Successes/errors baseline**: `chat_finish:success:200` vs
  `chat_finish:{"code":…}` payload counts.
- **Advertised limits**: the `Model classes refreshed` registry line;
  `error-code-cache.json`; the client's SQLite state DB for per-model selected
  presets (`aicoding.modelSelector.runtimeConfig.*`).
- **Session size**: transcript JSONL byte and character counts per session.

### 3.1 Unit vocabulary: IDE window ≠ task ≠ request

The vendor's word **task** is not this report's unit of measurement. Three
nested objects, each with its own anchor:

| Object | Vendor's name for it | Anchor in the evidence | How many |
|---|---|---|---|
| IDE window (the UI container that holds chat boxes) | `windowN/` log directory | path of every log line | 3 (`window1`, `window2`, `window3`) |
| One chat conversation | **task** — `task.status.update {"taskId":X,"status":…}` in `windowN/quest.log`, polled by API method `getMasterModeTaskById`; the same line names X twice (`taskId`, `executionSessionId`), so task id ≡ conversation id | `evidence/logs/task_status_lines.txt` | 9 of the 20 catalogued conversations carry lifecycle events |
| One upload of the whole conversation (what this study measures) | request — `ACP session/prompt`, answered as a `chat_finish:` line | §3 anchors above | 245 requests reached a `chat_finish` line (225 `success:200`, 20 quota/account failures, §4.3); the 33 timed-out requests never reached one |

So **two chat boxes are not two tasks**: a box holds many conversations over its
lifetime (`evidence/stats/session_size_stats.csv` lists 20 conversations in 6
project caches against 3 windows), and each conversation is its own task. Two
boxes count as two *running* tasks only while both are generating — `Running` is
a state, and a box parked on the timeout banner reports `ActionRequired` instead
(§4.6). The quota wording "Running task quota exceeded"
(`error.code.task.running.quota.exceeded`) never fired in these nine days, so its
ceiling is bounded only at ≥2 (§4.6). **No vendor document inside the evidence
defines `task`** — everything in this subsection is inferred from the client's
own records, and is stated as inference wherever the report uses it.

## 4. Evidence

### 4.1 The registry contradiction (verbatim from the client log)

```json
{"name":"qmodel_38max","displayName":"Qwen3.8-Max", …,
 "maxInputTokens":180000, …,
 "contextConfig":{"1M":{"tokenCount":1000000},
                  "200K":{"tokenCount":200000,"isDefault":true},
                  "400K":{"tokenCount":400000}}}
```

BYOK definition of the same model (client state DB, API keys stripped):

```json
{"provider":"bailian","model":"qwen3.8-max-tp","displayName":"Qwen3.8-Max",
 "max_input_tokens":1000000,
 "contextConfig":{"1m":{"label":"1M","tokenCount":1000000}, …}}
```

Selected presets at time of observation: `qmodel_38max → 400K`,
`qwen3.8-max-tp → 1m` (the path actually serving traffic, §2). The 1M/400K
presets exceed the entry's own `maxInputTokens` of 180,000 by 5.5x and 2.2x.

### 4.2 Timeout events (33, all code 80408, none ever 80411)

| Conversation (= one task, §3.1) | IDE window | Timeouts | Span | Stored transcript at the 15:21 stats snapshot |
|---|---|---|---|---|
| `sess-03` | window3 | 23 | 2026-09-09 08:48 → 14:51 | 93 entries, 190 KB, 187 K message chars |
| `sess-04` | window3 | 4 | 2026-09-09 15:24 → 17:05 | 24 entries, 17 KB, 16 K message chars |
| `sess-11` | window1 | 5 | 2026-09-08 15:57 → 2026-09-09 00:17 | 626 entries, 380 KB, 364 K message chars |
| `sess-16` | window1 | 1 | 2026-09-07 14:09 | 198 entries, 133 KB, 129 K message chars |

The counts are unchanged from this report's first pass (33, of which 27 sat in
window3's log), but the *attribution* is now per conversation instead of
per window: the 27 window3 events were two different chats — the deep `sess-03`
(23) and a much smaller neighbouring box `sess-04` (4) — and `sess-11`'s fifth
event falls on 2026-09-09 00:17, not on Sep 8. Session-level attribution comes
from an independent log stream, the client's own task tracker: each banner puts
its task into `ActionRequired` within ≤0.24 s of the resume tool call, so all 33
events pair 1:1 with a named conversation (§4.6); the window column is the
`agent.log` file the resume line was read from.

2026-09-09 detail: 00:17 (`sess-11`), then 08:48, 12:18, 12:20, 13:36, 13:39,
13:41, 13:56, 14:10, 14:11, 14:15, 14:17, 14:20, 14:23, 14:26, 14:27, 14:28,
14:30, 14:31, 14:32, 14:37, 14:44, 14:48, 14:51 (all `sess-03` — the 13:36–14:51
block is the densest resume-button loop, 20 events), then 15:24, 15:33, 17:04,
17:05 (`sess-04`, with Completed runs at 15:40, 16:26, 16:33 and 16:48 in
between). Full per-event CSV: `evidence/logs/timeout_resume_events.csv`.

Timeouts concentrate in the deepest conversations — the No. 1 and No. 4
conversations by stored size (`sess-11` 364 K, `sess-03` 187 K message chars)
carry 28 of the 33 events, so oversized context clearly *raises* the failure
rate. It is not a hard gate, though, and the corrected attribution makes the
mechanism claim sharper on both sides:

- **Two larger conversations never failed.** `sess-15` (245 K chars) and
  `sess-07` (195 K) outrank the looping `sess-03` and logged zero timeouts — but
  neither appears in the task tracker at all, so they were not being run while
  the ceiling was in effect. The honest comparison is "deep and idle" against
  "deep and active", not "large is safe".
- **A conversation an order of magnitude smaller still failed.** `sess-04`
  (16 K chars at the 15:21 stats snapshot, still growing when the log extract
  ends at 17:13) produced four 80408 banners in the same hour that the 187 K
  `sess-03` was completing runs.
- **Inside one conversation the outcome flips at monotonically rising size.**
  `sess-03` shows banners at 14:10:52, 14:11:56, 14:15:45, 14:17:04 and 14:20:12
  with **completed runs at 14:13:39 and 14:21:01 between them** (§4.6) — a
  success at a context strictly larger than the failures that preceded it,
  followed by another failure two minutes later.

Request size cannot explain a failure that clears itself at a larger size and
returns at the largest, nor one that occurs in a 16 K-character session while a
187 K-character session answers; time-varying server latency against the
client's fixed watchdog can.

### 4.3 The stall, not an error

Across the same retention window the client logged 245 `chat_finish` lines
(after removing one line that is an echo of the investigating agent's own
command): 225 successes as `chat_finish:success:200`, 20 quota/account
failures as `chat_finish:{"code":…}`. For all 33 timeout events there is **no
`chat_finish` line and no failure marker** — the only trace is the resume
tool call. The request disappears server-side; the client's watchdog
(name unknown) decides the response is never coming.

That watchdog is undocumented by the vendor, but the client's own task tracker
(§4.6) measures it: of the 33 `Running` → `ActionRequired` transitions, **16 land
at exactly 61 s** after the run started, and the other 17 later (126 – 1,607 s).
Since 155 of the 194 *successful* runs in the same extract took longer than 61 s
(median 135 s, longest 4,131 s), the limit cannot cap total duration — it is
**~60 s of silence between chunks**, the clock restarting on each one. That is
also why an oversized context triggers it: not because the request is refused,
but because a slow first token or a long tool-call gap starves the stream.

### 4.4 Quota-mode payload inconsistency (18 events, 5 sessions)

```
"code":100400,"message":"Allocated quota exceeded, please increase your quota limit. …"
"code":100400,"message":"Your token-plan 1-week quota has been exhausted. The quota will reset at 09-08 01:45:00 UTC…"
"code":100400,"message":"Access denied, please make sure your account is in good standing. …"
"code":"112","message":"{\"pricingUrl\":\"https://qoder.com.cn/pricing?client=qoder\"}"   ← string, not int
wrapper: {"code":-32603,"data":{…}}                                                        ← double-nesting
```

One UI banner family covers at least four distinct account states; none of
them is "context too long", and the dedicated 80411 code stayed silent.

### 4.5 Operator testimony (verbatim, timestamps from client prompt history)

> "2 failure modes. Time out: you have a messages that reads Response timeout.
> Click to resume or switch to another model and try again. plus a button to
> push, after pushing, the button is replaced by 'working...' — quota issue:
> there's no button (a different message) you have to type in something. I
> never resubmit the complete meg. I always use 'continue, retry, try again'"

> "…the return code may be inconsistent. On the UI, I see at least 3 times
> timeout with the retry button in the past 60mins."

The UI observation was accurate and conservative: the log-anchored count for
that hour is far higher (§4.2), and the "3 in 60 minutes" window is the
resume loop of a large-context request against a server whose latency was
climbing at that time.

![Nine consecutive timeout banners in one transcript, with the Continue button
below](report_qwenAliServiceQuality_img/timeout_storm_ui.png)

### 4.6 The client's own task tracker corroborates every banner

`windowN/quest.log` keeps a lifecycle for each conversation-as-task (§3.1):
`task.status.update {"taskId":X,"status":…}`, where the same line repeats X as
`executionSessionId`, polled by the client's `getMasterModeTaskById` API method.
Published extract: [`evidence/logs/task_status_lines.txt`](evidence/logs/task_status_lines.txt).

- 1,252 log lines → **524 events** after collapsing the cross-window repeats
  (102 events are written by more than one IDE window, ≤0.7 s apart — which is
  why quest.log's file name must *not* be used to attribute an event to a
  window; window attribution stays on `agent.log`). All 524 also arrive as
  `.skipNonQuestTask` twins, i.e. the tracker covers ordinary chat, not only
  Quest-mode work. Status counts: `Running` 258, `Completed` 208,
  **`ActionRequired` 33**, `Error` 18, `Stopped` 7, over 9 conversations.
- **`ActionRequired` pairs 1:1 with the 33 timeout banners of §4.2** — every
  resume tool call has one within 234 ms, and none is unpaired. Two independent
  streams (the button in `agent.log`, the state machine in `quest.log`) confirm
  the same 33 events, and the state machine supplies the conversation id the
  resume line omits — that is how §4.2 is now attributed per conversation.
- `Running` spans: 257 closed, median **126 s**, p90 679 s, max 4,131 s — the
  dead time the banner adds on top of a normal run.
- **Two tasks really are two tasks: 10 overlapping `Running` pairs**, e.g.
  `sess-03` 00:48:35 → 00:54:08 overlapping `sess-11`'s runs 00:49:59 → 00:50:44
  and 00:53:48 → 00:55:29 on 2026-09-09, both reaching `Completed`. Never three.
  `error.code.task.running.quota.exceeded` ("Running task quota exceeded") sits
  in the fetched dictionary and **never fired**, so that ceiling is bounded only
  at ≥2 and its value stays unknown (§7).
- A box parked on the banner is **not** occupying a running slot:
  `ActionRequired` (33) and `Stopped` (7) are states with nothing in flight — the
  loop's cost is wall-clock, not concurrency (§5).
- End states read from the same stream: the deep `sess-03`'s **last** recorded
  event is the 14:51:24 `ActionRequired` — the banner it was abandoned at — and
  `sess-16` is caught mid-`Running` where the retained log region ends.
- Completeness: 1 of the 10 task ids in the log mirror has no row in
  `evidence/stats/session_size_stats.csv` (a conversation with no transcript
  statistics), and its 12 events are excluded from the published extract so the
  frozen pseudonym map stays valid.

### 4.7 Every interaction is timestamped — the phase stream supplies the latency axis

The same `agent.log` that carries the resume button also carries **one line per
phase boundary of every turn**:
`[ACPProgressStateMachine] State transition: A -> B, trigger: T, sessionId: S`
(published extract [`evidence/logs/phase_transitions.txt`](evidence/logs/phase_transitions.txt),
885 transitions, 9 conversations — and unlike quest.log these are per-window,
not replicated). The trigger names what the operator sees on screen:

| Trigger | UI meaning | Count in extract |
|---|---|---|
| `user_message_chunk` | send pressed (`→ prompting`) | 252 |
| `agent_thought_chunk` | first streamed chunk — the "Thinking…" label (`prompting → streaming`) | 245 |
| `permission_request` | tool-approval dialog shown (`streaming → suspended`) | 37 |
| `resume_tool_call` | **the 80408 timeout banner** (`streaming → suspended`) | **33** |
| `user_resume` | Continue pushed / dialog approved (`suspended → streaming`) | 67 |
| `chat_finish:…` | the turn is over (`streaming → completed`, or `→ error`) | 208 successes, 4 pre-stream rejections |

Reading each pair of consecutive transitions of one conversation as an interval
gives the timings this study could otherwise only describe as "unmeasurable
from the client":

- **Wait for first output** — send pressed to first chunk: median **9.6 s**,
  p90 49 s, max 132 s, min 1.2 s (n = 245). Client-perceived, so it includes the
  client's own context assembly; it is not a pure server round-trip.
- **Generation time** — `streaming` to `chat_finish:success`: median 105 s, p90
  477 s, longest 2,310 s, and **149 of 208 successful generations outlasted the
  61 s watchdog interval** — a second stream corroborating §4.3's "the watchdog
  caps inactivity, not total duration".
- **Banner and dialog are separable for free**: `suspended` is entered by
  `resume_tool_call` (**33 — exactly the §4.2 timeout count, a third independent
  confirmation from a log stream that never mentions 80408**) or by
  `permission_request` (37).
- **What the loop cost the human**: 32 of the 33 banners were resumed — the 33rd
  is `sess-03` at 14:51:24, the one it was abandoned at (§4.6) — median hold
  30 s, **90.5 min of operator waiting summed over the banners**, plus 122.0 min
  on permission dialogs.
- **Fast fail versus slow fail**: the 4 prompts rejected before any chunk
  arrived (2 × code `100400` "Access denied…", 2 × code `"112"` pricing
  redirect — the account path of §4.4) answered in a median **0.7 s**, while the
  timeout path burns a full watchdog interval to deliver the same information:
  "this request will not be served". That asymmetry is a UX finding, not just a
  latency one.

Caveat: the state machine records the *first* chunk of a phase, not each chunk,
so per-chunk silence is not observable here (which is why §4.3's reset semantics
remain an inference), and `prompting` blurs client-side preparation with server
latency. Nothing in this section needs the transcript: every line carries the
conversation id, so interaction-level attribution is direct.

## 5. User impact

- Each loop iteration costs the full watchdog interval of dead time; the
  13:36–14:51 block is ~75 minutes of wall-clock lost in one conversation
  (`sess-03`). Summed over the study window, the 33 banners held the operator
  **90.5 min** and the 37 tool-approval dialogs **122.0 min** (§4.7).
- The banner's advice ("click to resume or switch model") is wrong for this
  failure class: resuming re-sends the identical oversized request. Starting a
  smaller-context conversation helps but is no escape hatch either — `sess-04`
  (16 K characters) timed out four times while the 187 K `sess-03` completed
  runs in the same hour (§4.2). Waiting for server latency to drop clears either
  case; neither fact is visible in the UI.
- The advertised 1M context is not a usable capacity claim; a user selecting
  it converts a would-be validation error into a silent stall that can loop for
  hours at a stretch.
- Recovery UX asymmetry (button vs must-type) plus inconsistent codes makes
  automated accounting of either mode error-prone without the anchors in §3.

## 6. Asks (to the IDE vendor and the model service)

1. Return **80411** (or HTTP 413-style `context_length_exceeded`) when input
   exceeds the real limit — the code exists; use it instead of stalling.
2. Make the context presets honest: either cap selectable presets at
   `maxInputTokens` (180K for Qwen3.8-Max today) or raise the real limit to
   match the 1M preset. The BYOK definition claiming 1,000,000 for the same
   model needs the same reconciliation.
3. Change the timeout banner's guidance for repeat failures in one session:
   after N identical resumes, suggest "start a new session (context too
   large)" rather than "click to resume" — and say plainly that a new session
   can also fail while server latency is high (§4.2), so the hint is a
   mitigation, not a fix.
4. Normalize error payloads: integer codes only, one message wording per
   code, no JSON-RPC double-wrapping of the business code.
5. Log the failure client-side: persist the banner event (code + timestamp)
   into the transcript JSONL, and log per-request input-token usage on the
   `chat_finish` line. Today the client cannot answer "how big was the
   request that timed out?" — corrected in part by §9: context occupancy *is*
   logged (`Context usage sync received … usedTokens=…`), but never reaches the
   transcript, and the two figures that would settle mechanism — output-token
   count and cached input-token count — are absent. The phase data for "how long
   did each step take" already exists in `agent.log` (§4.7) and likewise dies
   with log rotation; writing both into the transcript would make a turn
   auditable by the user, not only by a forensics pass.
6. Publish the running-task quota: the client ships the message
   `error.code.task.running.quota.exceeded` ("Running task quota exceeded") but
   neither that dictionary, the UI, nor any vendor document in this evidence
   states the limit or defines `task` (§3.1, §4.6). Users running two or three
   chat boxes in parallel cannot tell what they are spending.
7. Make a blocked conversation visible when it is not on screen, and log what the
   client holds back. In the second round (§9) a conversation waited on a
   tool-approval dialog for 69 seconds and on another occasion for about twelve
   minutes with no signal anywhere outside that panel; a second Continue click is
   dropped without feedback (`resume: ignored, current state=streaming`); and
   text typed while a conversation is parked enters a queue that produces no log
   line at all, so the gap between the operator's intent and the dispatch cannot
   be reconstructed. Also document where the sixty-one-second clock starts and
   what a fresh send re-offers that a resume does not (§9).

## 7. Limitations

- Single workstation, single account, 9-day log retention; no controlled
  sweep of request size vs timeout latency (each probe costs a watchdog
  interval). The size correlation in §4.2 is observational, and a later
  re-collection turned one conversation's trace from a pure failure loop into
  timeout→success→timeout at *rising* context (§4.2, §4.6) — which is why size
  is treated as a probability factor, not a threshold.
- **"Task" is inferred, not documented.** Everything in §3.1 and §4.6 about the
  vendor's task object comes from the client's own log lines (`taskId` ≡
  `executionSessionId`, `getMasterModeTaskById`, the status vocabulary) — no
  provider specification in the evidence defines it, and its meaning could
  differ on another plan or client version. The one number that would matter
  for parallel use, the running-task ceiling, stayed unobserved:
  `error.code.task.running.quota.exceeded` never fired, so §4.6 bounds it only
  at ≥2. The probe that would settle it is three chat boxes generating at once,
  watching for that code versus a plain 80408 stall — each probe costs a
  watchdog interval, which is why it is not run here.
- **Retention is shorter than "9 days" implies.** Each chat window's runtime
  log rotates at 5 MiB and keeps only *one* backup generation
  (`agent.log` → `agent.1.log`; the *next* rotation overwrites the old
  `agent.1.log`), so a busy window can drop days-old events within hours of
  activity. The §4.2 counts are therefore frozen against a point-in-time copy
  of the log tree (`raw_snapshots/`, gitignored), not the mutable live tree,
  and are kept current by the project's log mirror — an append-only,
  SHA-256-verified mirror that also flags any in-place rewrite of
  already-written log bytes.
- **The two horizons in the evidence differ.** The transcript statistics
  (`evidence/stats/session_size_stats.csv`) were collected at 15:21 on
  2026-09-09, while the log extracts run to 17:13 — so sizes quoted in §4.2 for
  conversations still active after 15:21 (notably `sess-04`) are snapshots taken
  mid-flight, and re-collecting them now would renumber every `sess-NN`
  pseudonym. §4.6's task extract and §4.7's phase extract were cut from the mirror
  (`logs_mirror/`, gitignored) through the collector's `LOGSRC=` override
  for exactly that reason: they add streams without disturbing the frozen map.
  Both are filtered to conversations that already have a stats row
  (`KEEP_ALL=1` lifts that filter for a local-only dump of a live installation).
- The exact server-side mechanism (queue vs prefill stall vs gateway) is not
  observable from the client; §4.3 proves only "no response was ever emitted".
- Transcript characters are a lower bound for request size (system prompt,
  tool schemas and memory blocks are re-sent but not stored in the JSONL).
  §9 supersedes this proxy where the log has the real figure: the client reports
  per-request context occupancy as `usedTokens` of `reportedLimitTokens`.
- The IDE's watchdog duration is not documented by the vendor. §4.3 measures it
  indirectly from the client's state machine (modal 61 s on a 33-event sample);
  the watchdog's name, its exact threshold, and whether the clock really resets
  per streamed chunk are not observable from the client.

## 8. Reproduction

1. Install Qoder CN ≥ 1.1.x; configure a BYOK model on Alibaba Cloud Model
   Studio (token plan); select the 1M context preset for Qwen3.8-Max.
2. Run an agentic session until the transcript exceeds ~150 KB of re-sent
   content (deep tool-use sessions reach this in under an hour).
3. Observe: responses stop arriving; the client shows "Response timeout.
   Click to resume…"; each resume re-fails in ~1–3 minutes; fresh sessions
   with small contexts respond normally on the same account and model. The
   stall is intermittent — the same oversized request may also succeed after a
   wait (§4.2), so treat it as a probabilistic failure driven by server latency
   on top of the size effect, not a fixed error.
4. Verify from logs (no UI needed): `grep '"title":"resume"' ~/.config/QoderCN/logs -r`
   — every event carries `"reasonForCode":80408`, and no `chat_finish` line
   exists for it.
5. Cross-check the same events from a second stream:
   `grep 'task.status.update' ~/.config/QoderCN/logs/*/window*/quest.log` — each
   banner shows up as that conversation's task going `ActionRequired` within a
   few hundred milliseconds, and the `Continue` click returns it to `Running`.
6. Timestamp every interaction of a turn from a third stream:
   `grep 'ACPProgressStateMachine' ~/.config/QoderCN/logs/*/window*/agent.log` —
   triggers `user_message_chunk` (send), `agent_thought_chunk` (first "Thinking…"
   chunk), `resume_tool_call` (timeout banner), `user_resume` (Continue),
   `chat_finish:…` (turn over). Subtracting consecutive transitions of one
   conversation yields time-to-first-chunk and generation time (§4.7).

## 9. Second collection round, 2026-09-10 (an independent re-run during a live outage)

The day after round 1 was frozen, the same workstation entered another timeout
storm — and this time the client's own per-request context occupancy (§7) could
be read from the log as it happened. The round is kept separate
(`evidence/incident_20260910/`, regeneration command in its README) because round
1's pseudonym map is deliberately immutable: re-collecting into it would renumber
every conversation and invalidate the frozen bundle.

**Scope and headline.** 62 request episodes from 55 distinct submitted prompts
across three conversations: 53 completed, five ended in a timeout park, two in a
tool-approval park, two failed or cancelled. All five timeout parks sit in one
conversation at **490,789 and 494,193 tokens** of a reported 1,000,000 limit, and
they come from only **two submitted prompts** (one prompt parked four times as it
was resumed and stalled again, the second parked once); the largest context that completed anywhere in the
round is **452,447 tokens**. That is a same-day separation of roughly 38,000
tokens — not a threshold. Round 1's pooled data does not separate at all (180 of
203 successful requests sit above the smallest stalled context), so size stays a
probability factor.

**A within-conversation causal pair.** The stalled conversation produced the
study's first experiment rather than an observation:

| Step | Context occupancy | Outcome |
|---|---|---|
| two submitted prompts, five stalls | 490,789 / 494,193 tokens | no streamed output at all; banners at 11:04:20, 11:05:49, 11:07:49 and 12:23:15 (one prompt, resumed three times) and 13:05:11 (the second prompt) |
| press stop, then the client's context-compaction control | 494,193 → 117,153 (`Compression API call completed for session compact`) | — |
| next send | 85,115 tokens | first streamed chunk in **8.43 s**, turn complete in **10.08 s** |

Same conversation, same account, same model, same preset, minutes apart, with one
variable changed. It confirms §4.2's mechanism claim experimentally and names the
operator's actual remedy, which the banner never mentions: **compact the context,
do not press Continue**.

**Two stall clocks, by ruling.** Send-to-stall and first-chunk-to-stall are
reported as separate columns (`to_stall_s`, `stall_from_chunk_s`) because they
answer different questions — how long the operator was held (125.3 s and 127.1 s
on fresh dispatches; one banner left unanswered for 4,860.7 s) versus what the
client's watchdog measures (60.9 s and 61.1 s, counted from a Continue click).
The roughly sixty-six-second difference between a fresh dispatch and a resume on
the *identical* payload is **unexplained**: the log shows both paths and their
costs but not why they differ (§6 ask 7).

**Three negative results,** recorded because each one cost an experiment:

1. **Tab visibility** throttles nothing — a conversation whose panel was hidden
   0.76 s after sending took its first chunk 1.34 s later and completed in 2.58 s
   while invisible.
2. **Server-side cache residency** shows no measurable effect — at effectively
   identical size (323,270 then 323,737 tokens), a 7.9-minute idle gap preceded a
   17.58 s wait and a 27.7-minute gap preceded a 17.11 s wait. Cold-cache
   eviction therefore does not explain the 28.03 s outlier measured at 251,788
   tokens.
3. **Context cannot be inflated by instruction** — a turn designed to add roughly
   a hundred thousand tokens added **851**, because the agent answered a
   line-count question with a counting command instead of loading the files.

Result 3 also corrects my own reading earlier in this round: the seven-step
ladder's waits (2.62, 6.92, 10.93, 7.94, 28.03, 5.14, 6.21 seconds) are **not** a
dose-response curve. Service load dominates the wait for the first streamed
chunk; what size decides is the binary outcome.

**Client behaviours with direct user impact.** A conversation can wait
indefinitely on a tool-approval dialog while nobody is looking at it (69.25 s in
one case, about twelve minutes in another) with no signal outside that panel; a
second Continue click is dropped without feedback
(`resume: ignored, current state=streaming`); and text typed while a conversation
is parked enters a queue that writes **no log line at all** — established by
absence across all three published extracts, which makes the interval between the
operator's intent and the actual dispatch unrecoverable. Identical repeated
prompts are *not* deduplicated by the client (distinct request identifiers,
independent lifecycles), although probe wording should still vary because the
model can see its own previous answer.

## Appendix — evidence package

`evidence/` (anonymized, machine-checkable): 33-event timeout CSV with
millisecond timestamps and pseudonymized tool-call ids; 50 raw quota-error log
lines with payload variants; `chat_finish` census; the fetched error-code
dictionary entries (80408/80411/40429/100400/112 family); the model-registry
line and BYOK definitions showing the 180K-vs-1M contradiction; per-model
selected context presets; 20-session transcript size table and the failing
session's context-growth curve; merged timeline CSV (51 events); the operator's
screenshot and timestamped verbatim statements; `error_messages.json` with
every quoted string; a 1,252-line conversation-lifecycle extract from the
client's task tracker (`logs/task_status_lines.txt`, 524 events after
≤2 s de-duplication); an 885-line per-interaction phase extract
(`logs/phase_transitions.txt`); and a second, separately labelled collection
round in `incident_20260910/` (62-request lifecycle CSV carrying per-request
context occupancy, plus its README and three negative results). `analysis/summary_tables.md` is regenerated and asserted
against this report by `scripts/analyze.py`. Full chat transcripts are
withheld: they carry third-party project content beyond this study's scope.
