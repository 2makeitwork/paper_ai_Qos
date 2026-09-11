# AI Service QoS — Independent Measurement of What Users Actually Receive

**Author:** 2makeitwork — independent, unaffiliated. The handle is pseudonymous by choice and is not to
be resolved to a person; no institution appears on this project's behalf anywhere, in any byline,
citation or archive record.

> **Pre-release, last revised 2026-09-11** (methodology v0.1). Definitions, wording and figures
> may still change; cite a snapshot — a release tag or a commit, not a branch — so that a later
> revision cannot move what your citation points at. Every figure quoted in this document set is
> asserted against the shipped evidence by `scripts/analyze.py`, which fails when a number and the
> evidence disagree and warns when a file is edited after the date above.

> **North star.** An independent, outside-in measurement framework for evaluating the reliability, latency, usability, and failure behavior of AI services under real user workloads.

An open, auditable way to measure what an AI service *does* rather than what it can answer, plus the first dataset it produced. **Qwen3.8-Max / Qoder CN is Case Study 1** — the first system measured, not the subject; the method is provider-neutral by construction and the roadmap (paper section 7) adds controlled single-factor experiments, a second provider, and continuous collection.

The repository holds the method ([`paper_ai_QoS.md`](paper_ai_QoS.md),
methodology v0.1), the measurement pipeline, and the anonymised evidence — and
**Case Study 1** ([`report_qwenAliServiceQuality.md`](report_qwenAliServiceQuality.md)),
the vendor-facing report on how the Qoder CN IDE + Alibaba Cloud Model Studio
(token plan) behaved when agent-session contexts exceeded what the service
actually processed. One dataset is included, published under the
[`DATASET_CARD.md`](DATASET_CARD.md) front matter.

**Headline**: the model registry offers 1M-context presets for a model entry
whose own `maxInputTokens` is 180,000; oversized requests fail as opaque
"Response timeout" events (client error code 80408), never as the service's
own `80411 "Input content too long"` error — and the resume button re-sends
the identical request. The loop is deterministic within a burst but
intermittent across time (the same oversized request can succeed minutes
later): a fixed client watchdog against time-varying server latency, with
oversized context raising the odds rather than acting as a hard gate.

Every timeout is corroborated by a second, independent stream — the client's own
task tracker in `windowN/quest.log`, whose `ActionRequired` state arrives within
234 ms of each banner (report §4.6). Vocabulary note: the vendor's **`task`**
means one chat *conversation*, not one chat box (report §3.1).

Every *interaction* is timestamped by a third stream —
`[ACPProgressStateMachine] State transition: A -> B, trigger: T, sessionId: S` in
`windowN/agent.log`, whose triggers name send-pressed, first streamed "Thinking…"
chunk, tool dialog, timeout banner, resume click and turn-over. Subtracting
consecutive transitions gives time-to-first-chunk and generation time per turn
(report §4.7); `scripts/collect_evidence.sh` step 10 extracts it.

## Layout

| Path | Contents |
|---|---|
| `paper_ai_QoS.md` | the paper: method first, the incident as its worked example (§1.4 positions it against prior measurement work) |
| `abstract.md` | the single-paragraph abstract used on the paper page |
| `report_qwenAliServiceQuality.md` | the practitioner report (summary, findings, data, asks, limitations, reproduction) |
| *(not published)* `prior-works.md` | search log behind §1.4, gitignored by decision; each cited work carries its own identifier in `PUBLICATION.md` §2.5 instead |
| `ask_vendor.md` | the open questions addressed to the IDE vendor and the model service, each stated as measured-by-us, answer-unknown |
| *(not published)* `PUBLICATION.md` | release strategy, status notes and the media plan; its citable content lives in `CITATION.cff`, the dataset card and `paper_ai_QoS.md` §1.4 |
| `DATASET_CARD.md` | the dataset card, published as `README.md` of [the dataset repository](https://huggingface.co/datasets/2makeitwork/paper_ai_Qos) |
| `CITATION.cff` | machine-readable citation for the dataset, paper and code |
| `LICENSE` | what is covered by which license: text and data under Creative Commons Attribution 4.0, `scripts/` under MIT |
| `LICENSE-content.md` / `LICENSE-code.md` | Creative Commons Attribution 4.0 for text, tables, figures and data; MIT for the scripts |
| `methodology.md` | anchors, sources, pipeline, exclusions |
| `anonymization.md` | scrubbing policy and how it is machine-checked |
| `evidence/` | anonymized raw statistics, log extracts, configs, timeline CSVs, error-message strings, screenshot, operator statements; `evidence/incident_20260910/` is a second, separately labelled collection round (2026-09-10) with its own pseudonym namespace |
| `raw_evidence/` | the pre-anonymization dump this bundle was built from (gitignored, internal — carries local paths and real ids) |
| `scripts/export_error_sessions.py` | (local-only, gitignored) general per-machine transcript exporter feeding `raw_evidence/transcripts/` |
| `scripts/collect_evidence.sh` | re-collects the raw dump from a Qoder CN installation (writes `scripts/raw_local/`, gitignored); `LOGSRC=<dir>` points it at a frozen copy such as `logs_mirror/mirror/` instead of the live tree |
| `scripts/anonymize.py` | turns a raw dump into `evidence/`; exits nonzero if any forbidden pattern survives |
| `scripts/analyze.py` | recomputes every number quoted in the report from `evidence/` alone and asserts them; regenerates `analysis/summary_tables.md` |
| `scripts/latency_from_logs.py` | turns the client's phase-transition and context-occupancy log lines into a per-request lifecycle table (wait for first streamed chunk, turn total, send-to-stall, first-chunk-to-stall, timeout versus dialog park, tokens at send); `--since` scopes a collection round to its own incident |
| `scripts/verify_dataset_card.py` | checks `DATASET_CARD.md` against the files it declares — config paths exist, tables are well-formed, stated row counts are true, required card sections present; run before any upload |
| `scripts/check_release_sync.py` | compares the published data layer, file by file and hash by hash, across the working tree (or a tag), the Hugging Face dataset repository and a Zenodo record — the three update independently, so drift is the default state and this is how it is measured rather than assumed (`--ref v0.3.0-pre`, `--zenodo <record>`, `--zenodo-draft <id>` with a token) |
| `scripts/log_mirror.py` | (local-only, gitignored output) append-only mirror of the live IDE logs into `logs_mirror/`, capturing each file as it rotates out and SHA-256-verifying committed regions to flag in-place tampering; run every minute by the user timer pair in `scripts/systemd/` (`qoder-log-mirror.timer` → `qoder-log-mirror.service scan --once`), and `snapshot` for a checksummed frozen tree |
| `analysis/summary_tables.md` | the derived statistics, as generated |
| `scripts/watcher/` | (local-only, gitignored output) `cdp_watch.js` DOM watcher over CDP — render-side candidate signals; since 2026-09-09 the log phase stream (§4.7) is the primary timing instrument and this is the cross-check (see the false-positive note in its header) |
| `tools/` | (local-only, gitignored) adapted doc index + the mandatory pre-publication gate `verify_docs.py` |

## Verify this repository yourself

```bash
python3 tools/gen_doc_index.py && python3 tools/verify_docs.py  # links, PII audit, ignore hygiene
python3 scripts/analyze.py                          # asserts all report numbers against evidence/
```

A rebuild of the evidence tree requires a machine with the same installation
(see `methodology.md` for exact source paths); timestamps in the evidence are
local time (AWST, UTC+8).

## Scope and honesty notes

- Single workstation, single account, 9-day log retention — observational,
  not a controlled benchmark; the report's §7 limitations apply to every
  file here.
- Full chat transcripts are deliberately **not** included (third-party
  project content); only error-related extracts and statistics are.
- All identifiers (user, host, paths, sessions, tool calls, account, BYOK
  model ids, LAN addresses) are pseudonymized per `anonymization.md`;
  timestamps and error strings are exact.
