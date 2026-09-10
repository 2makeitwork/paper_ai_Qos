# Incident 2 — collection round of 2026-09-10

Second, independently labelled observation round. It exists because the study
was still under live outage conditions the day after round 1 was frozen, and
because round 1's pseudonym map is deliberately immutable: re-collecting into it
now would renumber every `sess-NN` and invalidate the frozen bundle. Round 1
(2026-09-01 → 2026-09-09) stays as published; this directory is added alongside it.

## Reproduce

```bash
python3 scripts/log_mirror.py snapshot                       # freeze the log tree
python3 scripts/latency_from_logs.py raw_snapshots/20260910T155718/logs \
        --since 2026-09-10T00:00 \
        --emit-csv evidence/incident_20260910/request_lifecycle.csv
python3 scripts/analyze.py                                   # asserts the numbers below
```

* Frozen input: `raw_snapshots/20260910T155718` (419 files, `SHA256SUMS` manifest).
* `--since` is a scope control, not a cosmetic filter: the same log tree carries
  conversations from unrelated projects, and those are not this study's to
  publish even as pseudonymised timing rows.
* Naming: this round uses `S1, S2, S3` — the per-round pseudonyms of
  `scripts/latency_from_logs.py`, assigned by first request. They are **not**
  round 1's `sess-NN` namespace, and the mapping to real conversation
  identifiers is withheld, as everywhere in this bundle.

## What is in the file

`request_lifecycle.csv` — 62 rows, three conversations. A row is one request
**episode**: a single submitted prompt can account for several rows when it is
resumed and stalls again (55 distinct submits produced the 62 rows; the five
timeout rows come from two prompts). Columns: session,
send timestamp, outcome (`S` completed / `T` parked / `F` failed / `U`
cancelled), wait for first streamed chunk, total turn seconds, send-to-stall
seconds, retries, the park trigger, first-chunk-to-stall seconds, and the
context occupancy the client reported at send (`usedTokens` of
`reportedLimitTokens`).

Counts asserted by `scripts/analyze.py`: 53 completed, 5 timeout parks
(`resume_tool_call`, the 80408 banner), 2 permission-dialog parks, 2 failed or
cancelled — 62 rows in total from 55 submitted prompts.

## Headline measurements

| Finding | Value |
|---|---|
| Smallest context that timed out on the day | 490,789 tokens (one conversation; two submitted prompts, five stall events) |
| Largest context that completed on the day | 452,447 tokens |
| Send-to-stall, fresh dispatch | 125.3 s and 127.1 s |
| Send-to-stall, measured from a Continue click | 60.9 s and 61.1 s |
| Longest park | 4,860.7 s (a banner left unanswered for 81 minutes) |
| Context occupancy the client reports | `Context usage sync received … usedTokens=…, reportedLimitTokens=1000000` |

Round 1's pooled data does **not** separate outcomes by size (180 of 203
successful requests sit above the smallest stalled context), so the
452,447-versus-490,789 band from this single day is a same-day boundary
observation, not a threshold. Context size is reported as a probability factor
throughout.

## The paired experiment (size as cause, not correlation)

One conversation, one account, one model, eight minutes apart, nothing else
changed:

* five sends at **494,193** tokens → no streamed output at all, banner each time;
* the client's context-compaction control reports
  `Compression API call completed for session compact …` and then
  `usedTokens=117153` (13:12:52);
* the next send, carrying **85,115** tokens → first streamed chunk in **8.43 s**,
  turn complete in **10.08 s**.

That is the study's only within-conversation causal result, and it also names
the operator's real remedy — compact the context rather than press Continue —
which the banner text never mentions.

## Three negative results, recorded because they cost time to disprove

1. **Tab visibility.** A conversation whose panel was hidden 0.76 s after sending
   took its first streamed chunk 1.34 s after send and completed in 2.58 s.
   Hiding does not throttle the stream or the timeout clock.
2. **Server-side cache residency.** At the same size (323,270 then 323,737
   tokens), a 7.9-minute idle gap preceded a 17.58 s wait and a 27.7-minute idle
   gap preceded a 17.11 s wait. No measurable effect, so cold-cache eviction does
   not explain the 28.03 s outlier seen earlier at 251,788 tokens.
3. **Growing an agent's context by asking it to read files.** A turn designed to
   add roughly one hundred thousand tokens added **851**: the agent answered a
   line-count question with a counting command instead of loading the files.
   Context cannot be inflated by instruction — only by content the task genuinely
   requires, or by text the operator pastes.

## Client behaviours found in this round (each is an ask in the report)

* A conversation can sit **indefinitely on a tool-approval dialog while
  unobserved** — no signal anywhere else in the client (one such park lasted
  69.25 s, another about 12 minutes).
* A **duplicate Continue click is dropped** silently:
  `resume: ignored, current state=streaming`.
* Text typed while a conversation is parked enters a **queue that is logged
  nowhere** — zero queue, defer or hold-back markers across all published
  extracts, so the operator's intent-to-dispatch delay is unrecoverable.
* Repeated identical prompts produce independent request lifecycles with distinct
  request identifiers, so the client does not deduplicate or short-circuit them;
  probe wording must still vary, because the model *can* see its own previous
  identical answer.
