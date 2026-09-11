# AI Service QoS — Independent Measurement of What Users Actually Receive

Whether a model is good enough shows itself in a day of use. Whether the service behind it will
answer — in time, for the work actually being attempted, on the day it matters — shows itself very
unevenly: neither a capability leaderboard nor a provider status page reports it, and one banner
text, "Response timeout", covered both requests that were merely slow and requests that were too
large for the service's own declared input limit. This repository measures that second thing, the
**quality of service (QoS)** an AI service actually delivers, one submitted request at a time,
read out of the client's own log.

Two questions decide whether any of this is worth your time, and they are the two a buyer or an
operator of an AI service ends up asking: *if I give this service my real work, how often do I get
a usable result?* and *what happens when the service is under load, when context gets large, when
quota is approached, or when the provider degrades?* If either is a question you recognise, the
[paper](paper_ai_QoS.md) below is the method and what one incident answered. If neither is,
nothing here is for you.

**Case Study 1** — Qwen3.8-Max — is the worked example that makes the method concrete, not the
thing under measurement.

**Author:** 2makeitwork — independent, unaffiliated.

> **Released 2026-09-11 as v1.0.2** (methodology v0.1). This snapshot is frozen: later
> corrections and additions ship as a new version with a new tag, never as an edit to the bytes a
> citation points at — cite the tag or the Digital Object Identifier, not a branch. Two version
> numbers mean two different things here: the tag names this public snapshot, while *methodology
> v0.1* names the definitions, which stay unchanged until a second provider has been measured
> (section 7). Every figure quoted in this document set is asserted against the shipped evidence by
> `scripts/analyze.py`, which fails when a number and the evidence disagree and warns when a file
> is edited after the date above.

> **North star.** An independent, outside-in measurement framework for evaluating the reliability, latency, usability, and failure behavior of AI services under real user workloads.

## What this repository contributes

**The [paper](paper_ai_QoS.md) is the contribution.** It specifies a request-level method for
measuring the quality of service an artificial-intelligence service actually delivers to a user:
the unit of observation, a latency distribution rather than a mean, a six-class outcome taxonomy
that keeps the provider's own codes beside it, explicit denominators, retry accounting that
refuses to hide retries inside successes, a task taxonomy following real work, and a
machine-readable event schema — all defined independently of any provider's vocabulary, so results
are comparable across services and verifiable without a provider's cooperation.

The novelty is one of **perspective, not of method**. The instruments are shared with prior
external measurement of model services, and [section 1.4](paper_ai_QoS.md) names who and how this
differs. What none of that work occupies is the vantage: a reading taken on the paying user's side,
published as a stratified public aggregate, which checks what a provider *delivered* rather than
ranks what a system *computes*. [Section 7.1](paper_ai_QoS.md) states the institution that serves
— a public, user-side measure of AI-service delivery — with broadband performance reporting as its
working analogue.

Everything else here is a **means** to that end, and is labelled as such:

| | Artifact | Role |
|---|---|---|
| **end** | [`paper_ai_QoS.md`](paper_ai_QoS.md) | the method, its definitions, its findings, its limits |
| **means** | [`report_qwenAliServiceQuality.md`](report_qwenAliServiceQuality.md) | **Case Study 1** — the vendor-facing case report that motivated the method and carries the per-event tables, the reproduction steps and the asks |
| **means** | [`evidence/`](evidence/) + [the dataset](https://huggingface.co/datasets/2makeitwork/paper_ai_Qos) | the anonymised observations every number is re-derived from |
| **means** | [`methodology.md`](methodology.md), [`anonymization.md`](anonymization.md) | detection anchors, provenance, what re-runs from what, the scrubbing policy |
| **means** | [`scripts/`](scripts/) | the collector, the anonymiser, and the checks that re-derive and assert every published figure |

**Case Study 1** is the first system measured, not the subject: Qwen3.8-Max through the Qoder CN
integrated development environment and Alibaba Cloud Model Studio, over a ten-day field incident.
Its headline, in one paragraph rather than twenty — the report has the detail: a model registry
offering 1M-context presets for an entry whose own declared input limit is 180,000 tokens;
oversized requests failing as opaque "Response timeout" banners (client error code 80408) while the
service's own `80411 "Input content too long"` code never fired once; the resume button
re-submitting the identical request; and the whole loop deterministic within a burst but intermittent
across time, which is a fixed client watchdog meeting time-varying server latency — context size
raising the odds, never acting as a hard gate.

Three independent log streams make the account checkable rather than anecdotal: the banner events,
the client's own task tracker (whose `ActionRequired` state arrives within 234 ms of each banner,
report §4.6 — and whose `task` names one chat *conversation*, not one chat box, report §3.1), and
the per-interaction phase stream (report §4.7), which timestamps every send, first streamed chunk,
tool dialog, banner, resume click and turn-over. That is how a user-side measurement gets a
latency distribution instead of a complaint.

## Layout

| Path | Contents |
|---|---|
| `paper_ai_QoS.md` | **the paper — the contribution**: the method and definitions, the findings, the limits; §1.4 positions it against prior measurement work and §7.1 states what it is for |
| `abstract.md` | shorter forms of the same description (one line, about 300 characters, three sentences); the authoritative abstract is the one in `paper_ai_QoS.md` |
| `report_qwenAliServiceQuality.md` | the case report for the provider — the means: summary, findings, per-event data, asks, limitations, reproduction |
| `ask_vendor.md` | the open questions addressed to the IDE vendor and the model service, each stated as measured-by-us, answer-unknown |
| `DATASET_CARD.md` | the dataset card, published as `README.md` of [the dataset repository](https://huggingface.co/datasets/2makeitwork/paper_ai_Qos) |
| `CITATION.cff` | machine-readable citation, with the archive identifiers |
| `RELEASE_NOTES.md` | the text of the GitHub release note, authored as a tracked file so it passes the same scans as everything else |
| `LICENSE` | what is covered by which license: text and data under Creative Commons Attribution 4.0, `scripts/` under MIT |
| `LICENSE-content.md` / `LICENSE-code.md` | Creative Commons Attribution 4.0 for text, tables, figures and data; MIT for the scripts |
| `methodology.md` | anchors, sources, pipeline, exclusions |
| `anonymization.md` | scrubbing policy and how it is machine-checked |
| `evidence/` | anonymized raw statistics, log extracts, configs, timeline CSVs, error-message strings, screenshot, operator statements; `evidence/incident_20260910/` is a second, separately labelled collection round (2026-09-10) with its own pseudonym namespace |
| `scripts/anonymize.py` | turns a raw dump into `evidence/`; exits nonzero if any forbidden pattern survives |
| `scripts/analyze.py` | recomputes every number quoted in the report from `evidence/` alone and asserts them; regenerates `analysis/summary_tables.md` |
| `scripts/latency_from_logs.py` | turns the client's phase-transition and context-occupancy log lines into a per-request lifecycle table (wait for first streamed chunk, turn total, send-to-stall, first-chunk-to-stall, timeout versus dialog park, tokens at send); `--since` scopes a collection round to its own incident |
| `scripts/verify_dataset_card.py` | checks `DATASET_CARD.md` against the files it declares — config paths exist, tables are well-formed, stated row counts are true, required card sections present |
| `scripts/check_release_sync.py` | compares the published data layer, file by file and hash by hash, across the working tree (or a tag), the Hugging Face dataset repository and a Zenodo record — the three update independently, so drift is the default state and this is how it is measured rather than assumed (`--ref <tag>`, `--zenodo <record>`, `--zenodo-draft <id>` with a token). It also scans the **served text** for maintainer instructions, because fixing a document locally is not the same as fixing what the hub hands out |
| `analysis/summary_tables.md` | the derived statistics, as generated |

The capture and shipping pipeline — the collector that reads the installation, the tamper-evident log mirror and its systemd timers, the DOM watcher cross-check, the release gate and the payload builders — is the project's own tooling and is not published here. `methodology.md` states what each instrument did, and the complete pipeline is preserved in the archived source copies cited under Cite this above, which is where a reader who needs the collector should look.

## Cite this

| Object | Identifier |
|---|---|
| The method and findings | `paper_ai_QoS.md` in this repository, at a **tag** — cite the paper, and the snapshot you read |
| The archived software (every version) | concept DOI [10.5281/zenodo.22701430](https://doi.org/10.5281/zenodo.22701430) — always resolves to the latest archived version; `v1.0.0` is [10.5281/zenodo.22701431](https://doi.org/10.5281/zenodo.22701431) |
| The evidence, loadable | <https://huggingface.co/datasets/2makeitwork/paper_ai_Qos> |
| A specific number | the commit that produced it, plus `python3 scripts/analyze.py`, which re-derives it from `evidence/` |

`CITATION.cff` carries the same in machine-readable form, and the dataset card's Citation section
states the rules: cite a snapshot not a branch, name the collection round, and cite the client
version plus the service rather than the model alone.

## Verify this repository yourself

```bash
python3 scripts/analyze.py                  # re-derives and asserts every published figure
python3 scripts/verify_dataset_card.py      # checks the card against the files it declares
python3 scripts/check_release_sync.py --ref <tag>    # optional, needs network: compares
                                            # the served dataset repository with the tag
```

Each of these checks exists because something passed review and was wrong; the reasons are in
the commit messages. Rebuilding the evidence tree needs a machine with the same installation and
the same frozen raw dump: `methodology.md`, "What re-runs, and from what", states which of these
claims were tested and what the attempt produced. Timestamps in the evidence are local time
(AWST, UTC+8).

## Scope and honesty notes

- Single workstation, single account, 9-day log retention — observational,
  not a controlled benchmark; the report's §7 limitations apply to every
  file here.
- Full chat transcripts are deliberately **not** included (third-party
  project content); only error-related extracts and statistics are.
- The pre-anonymization material — the client's own log tree, the transcript exports, the
  checksummed snapshots — is likewise **not published**, because it carries local paths and
  real conversation identifiers. `anonymization.md` states the scrubbing policy and how it is
  machine-checked, so the exclusion can be audited from the policy rather than taken on trust.
- All identifiers (user, host, paths, sessions, tool calls, account, BYOK
  model ids, LAN addresses) are pseudonymized per `anonymization.md`;
  timestamps and error strings are exact.
