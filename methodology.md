# Methodology

> **Released 2026-09-11 as v1.0.1** (methodology v0.1). This snapshot is frozen: later
> corrections and additions ship as a new version with a new tag, never as an edit to the bytes a
> citation points at — cite the tag or the Digital Object Identifier, not a branch. Two version
> numbers mean two different things here: the tag names this public snapshot, while *methodology
> v0.1* names the definitions, which stay unchanged until a second provider has been measured
> (section 7). Every figure quoted in this document set is asserted against the shipped evidence by
> `scripts/analyze.py`, which fails when a number and the evidence disagree and warns when a file
> is edited after the date above.

> **Methodology v0.1** — the concepts below are frozen. The stage ladder to v0.5, a second provider and a continuous observatory is `paper_ai_QoS.md` section 7.

## Pipeline

```
Qoder CN installation ──the collector (project tooling)──▶ a local raw dump (not published)
                          │
                 scripts/anonymize.py ──▶ evidence/        (publishable, self-auditing)
                          │
                  scripts/analyze.py  ──▶ analysis/summary_tables.md
                          └── asserts every number quoted in the report
```

## What re-runs, and from what

A claim about reproducibility is worth only as much as the attempt that tested it. Measured on
2026-09-11, against the pinned snapshot `raw_snapshots/20260909T183241/` (461 files, `SHA256SUMS`
manifest beginning `4d3c3b5758396e42`; the snapshot is not published because it carries local paths
and real conversation identifiers):

| Step | Command | Result of the attempt |
|---|---|---|
| Derived statistics from the published evidence | `python3 scripts/analyze.py` | **reproduces exactly.** 62 assertions pass. The output file ends with a content hash plus a second-precision timestamp, and when the hash is unchanged the file is not rewritten at all — so running the checks cannot dirty the tree, and two copies with the same hash hold the same statistics whatever their stamps say |
| Card against files | `python3 scripts/verify_dataset_card.py` | **reproduces exactly**, eight checks, in either repository |
| Log extracts from the pinned snapshot | the collector with `LOGSRC=<snapshot>/logs`, then `scripts/anonymize.py` | **does not reproduce the frozen bundle.** Of 24 published items, 4 matched byte for byte, 11 differed, and 9 were not produced at all (`evidence/screenshots/`, `evidence/user_statements.md`, four extracts, two statistics files, the round-2 directory) |

The reasons are concrete rather than mysterious: the error-code dictionary and the model registry
are **fetched live** from the client and the service, so they are point-in-time observations that
can move under the pipeline; the screenshot and the operator statements were never derived from
logs; and several extracts were added to the collector after the freeze, against the mirror rather
than against this snapshot. So the honest framing, used throughout this project: **`evidence/` is
the frozen observation, and everything downstream of it is reproducible.** A reader who wants to
check a number re-derives it from `evidence/`; a reader who wants to re-derive `evidence/` itself
needs the author's unpublished raw tree *and* the study window still being served by the provider,
which no snapshot can guarantee.

## Log anchors (how each event class is detected)

| Event class | Anchor in `~/.config/QoderCN/logs/**/*.log` | Notes |
|---|---|---|
| Timeout (80408) | `[ChatSessionService] Creating tool_call … {"title":"resume","rawInput":{"chatTask":"CONTINUE_TASK","reasonForCode":80408}}` | logged when the banner + resume button appear; the button press adds `[ACP] Permission resolved`. The banner text itself is never logged (client-side DOM) |
| Quota/account | `ACP session/prompt failed` / `State transition: streaming -> error` / `Handling request error for session` | each event writes ~3 marker lines a few ms apart; clustered at ≤2 s |
| Conversation lifecycle (the vendor's `task`) | `task.status.update {"taskId":X,"status":…}` in `windowN/quest.log` (X reappears as `executionSessionId`; polled via `getMasterModeTaskById`) | a second, independent stream: its `ActionRequired` state arrives within 234 ms of every 80408 resume line, which is how report §4.2 attributes timeouts to conversations. Every open window writes the same event (≤0.7 s apart), so `(session, status)` is de-duplicated at ≤2 s and quest.log never supplies window attribution |
| Interaction phases | `[ACPProgressStateMachine] State transition: A -> B, trigger: T, sessionId: S` in `windowN/agent.log` | one line per phase boundary; the trigger says which (send pressed / first chunk / tool dialog / timeout banner / resume click / turn over). Consecutive transitions of one conversation bound the time spent in each phase (report §4.7). Per-window, not replicated; carries a sessionId, so attribution is direct |
| Context occupancy per request | `Context usage sync received for session S: requestId=…, usedTokens=N, reportedLimitTokens=M` (plus `Context usage update: {…}`) | the only real size figure the client exposes, and the only one that matters for a capacity claim — it replaces the transcript-character proxy. Never written to the transcript, and no output-token or cached-input-token count accompanies it |
| Panel visibility | `[ChatViewManagerService] Switched tab: from <view id> to <view id>` | the covariate that lets a stall or a wait be attributed to service behaviour rather than to an unobserved panel; measured with it, visibility had no effect (report §9) |
| Request outcomes baseline | `chat_finish:success:200` vs `chat_finish:{"code":…}` | timeout events produce **no** `chat_finish` line at all — the stall evidence |

Lines containing `"command"` are echoes of the investigating agent's own
shell commands (the IDE logs tool invocations into the same files) and are
filtered out at collection and again at anonymization.

## Sources (standard per-user locations)

| Source | Supplies |
|---|---|
| `~/.config/QoderCN/logs/` | all event timestamps (ms), resume tool calls, quota payloads, model-registry refresh lines, conversation lifecycle (`windowN/quest.log`), interaction phases (`windowN/agent.log`) |
| `~/.config/QoderCN/User/error-code-cache.json` | the vendor's code→banner-message dictionary (versioned, fetched) |
| `~/.config/QoderCN/User/globalStorage/state.vscdb` (`ItemTable`) | BYOK model definitions (`aicoding.customModels`), selected context presets (`aicoding.modelSelector.runtimeConfig.*`), prompt history with timestamps (`lingma.chat.localHistory.*`) |
| `~/.qoder-cn/cache/projects/*/conversation-history/<sid>/<sid>.jsonl` | transcript sizes, entry counts, context-growth curve |
| `/usr/share/qoder-cn-ide/resources/app/product.json` | client name/version/commit |

## Collection rounds and pseudonym namespaces

| Round | Span | Published where | Conversation labels |
|---|---|---|---|
| 1 | 2026-09-01 → 2026-09-09 | `evidence/` — a **frozen record of observations**, not a build artifact: see "What re-runs, and from what" below | `sess-01` … `sess-20`, numbered by row order in `stats/session_size_stats.csv` |
| 2 | 2026-09-10 | `evidence/incident_20260910/` | `S1`, `S2`, … assigned by first request in that CSV alone |
| 3 | 2026-09-11 → ongoing | **not published.** The same instruments keep collecting while the work is unobserved; whether it becomes a second dataset is an open decision, and if taken it will be a separate directory with its own pseudonym namespace, published as a new dataset configuration rather than an edit to the frozen one | `S1…` numbering restarts in its own directory, as round 2's does |

The namespaces are deliberately **not** interchangeable and no cross-reference
is published, because either one would leak the mapping to real conversation
identifiers. Round 2 exists as a separate directory rather than an extension of
round 1 because `anonymize.py` numbers pseudonyms in first-appearance order: any
new raw id added to the round-1 input would renumber every later `call-NNN` and
silently invalidate the frozen bundle. A later round is therefore always a new
directory, produced with `scripts/latency_from_logs.py --since <round start>` —
that flag is a scope control, not a convenience filter, because the same log tree
also carries conversations from unrelated projects.

## Measurement caveats baked into the analysis

- The transcript JSONL stores no per-message timestamps and not every prompt;
  prompt timestamps come from the state DB history instead.
- Per-request **context occupancy is** logged by the client, as
  `Context usage sync received for session … usedTokens=…, reportedLimitTokens=…`
  (found 2026-09-10; the earlier claim here that no token usage is logged was wrong,
  because the search covered only `usage`, `prompt_tokens`, `input_tokens` and
  `total_tokens`). Still absent: output-token count, cached-input-token count, and any
  of it inside the transcript. Transcript growth stays a lower bound on request
  content (system prompt, tool schemas and memory blocks are re-sent but not stored).
- Resume tool-call lines carry no sessionId. Report §4.2 attributes them to a
  **conversation** through the `ActionRequired` transition in
  `windowN/quest.log` (1:1, ≤234 ms — see the task-lifecycle anchor above), and
  to a **chat window** by the `agent.log` file the line was found in; no resume
  event appears in two windows' logs, so the window split is safe to add up.
- The client's watchdog duration is undocumented; only its effect (the
  banner + resume tool call) is measured. Report §4.3 bounds it from the phase
  and lifecycle streams (modal 61 s), and §4.7 states why the *reset* semantics
  stay inferred: the state machine logs the first chunk of a phase, not each one.
- Phase timings are client-perceived: the `prompting` interval mixes the client's
  own context assembly with server latency, so "wait for first chunk" is an upper
  bound on round-trip, not a network measurement.
- **An agent's context cannot be inflated by instruction.** Asking it to "read
  every file" does not grow the conversation: asked for line counts, it ran a
  counting command and the turn added 851 tokens (report §9). Controlled size
  sweeps need content the task genuinely requires, or text the operator pastes.
- **The client's input queue is invisible.** Text typed while a conversation is
  parked on a banner or a dialog is held, and no log line marks either the hold
  or the release (zero queue, defer or hold-back markers across every published
  extract). Send timestamps are therefore dispatch times, never intent times.
- **Log retention is size-based, not time-based, and shallow.** Each window's
  `agent.log` rotates at 5 MiB into a single `agent.1.log`; the next rotation
  overwrites it, so the collector's `--include='*.log'` must run before a
  window rotates twice or the earliest events are unrecoverable. The published
  extracts were frozen against `raw_snapshots/<ts>/` (a full copy + `SHA256SUMS`)
  and are kept current by the project's log mirror, which mirrors each file
  per-(path,inode) so a rotation-out generation is captured and hashed before
  it can be overwritten, and re-hashes committed regions on every 3-minute scan
  to detect any in-place edit of already-written log bytes.
- **Adding a stream must not renumber the frozen map.** `anonymize.py` assigns
  `call-NNN` to any UUID it has not seen, in first-appearance order, so a new raw
  extract containing an unknown id would shift every later pseudonym. The
  quest.log extract is therefore filtered to conversations that already have a
  row in `session_stats/session_size_stats.csv` (1 of the 10 task ids in the
  mirror is dropped, 12 events), and the collector reads
  `LOGSRC=<mirror dir>` so a stream can be added from the frozen mirror instead
  of the live tree, which has already moved past the study window.
