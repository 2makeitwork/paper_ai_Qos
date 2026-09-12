# AI Service QoS — Independent Measurement of What Users Actually Receive

Qwen3.8-Max is the example in this repository, not the subject. The subject is a method for measuring
**quality of service (QoS)**: what the service around a model actually does with a user's work.
Whether it answers. How long the first streamed chunk takes. What it tells you when it fails.

You learn within a day whether a model is clever enough. You never learn whether the service behind
it will answer, and nothing published tells you either: no leaderboard scores it, no status page
covers it. When it fails, one banner covers two different problems — "Response timeout", for a
request that was merely slow and for one far too large. Internet access had that same hole until
somebody measured it from the user's side. An internet service provider still advertises a speed
"measured under controlled conditions", but what a household can consult is an independent
measurement, broken out by provider, technology, region and hour. AI services have no such number,
and [section 7.1](paper_ai_QoS.md) argues they should.

Two questions decide whether the rest of this page is yours, the two you end up asking if you buy or
run an AI service: *how often does real work come back usable?*, and *what does that rate do under
load, at large context, near quota, or during a degradation?* If neither is yours, stop here. If
either is, the [paper](paper_ai_QoS.md) holds the method and the answers, counted one submitted
request at a time out of the log the client already writes. Nothing was asked of the provider.

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

**The [paper](paper_ai_QoS.md) is the contribution.** It measures what an AI service gives a user, in
a way someone else can run against another provider and compare. Seven decisions define it:

- the unit of count is one submitted request, not a session or a token stream;
- time is a distribution, never a mean, because a mean buries the tail;
- each ending gets one of six labels, with the provider's own error code kept beside it;
- every percentage names what it is out of;
- a retry is never counted as a success;
- work is sorted by what the user was trying to finish;
- every event is written to a machine-readable schema.

None of it borrows a provider's vocabulary, which is why two services can be compared and why a
stranger can check the numbers without the provider's help.

The instruments are not new: measuring a service from outside is an old trade, and
[section 1.4](paper_ai_QoS.md) says who does what. What nobody occupies is the seat. Nobody else
reads a paying user's log and publishes what it says, broken out by task and by hour. A leaderboard
ranks what a system computes; this checks what a provider delivered. [Section 7.1](paper_ai_QoS.md)
sets out the institution that would make the internet-service-provider comparison real: a public
measure of AI-service delivery.

Everything else here is a **means** to that end, and is labelled as such:

| | Artifact | Role |
|---|---|---|
| **end** | [`paper_ai_QoS.md`](paper_ai_QoS.md) | the method, its definitions, its findings, its limits |
| **means** | [`report_qwenAliServiceQuality.md`](report_qwenAliServiceQuality.md) | **Case Study 1** — the vendor-facing case report that motivated the method and carries the per-event tables, the reproduction steps and the asks |
| **means** | [`evidence/`](evidence/) + [the dataset](https://huggingface.co/datasets/2makeitwork/paper_ai_Qos) | the anonymised observations every number is re-derived from |
| **means** | [`methodology.md`](methodology.md), [`anonymization.md`](anonymization.md) | detection anchors, provenance, what re-runs from what, the scrubbing policy |
| **means** | [`scripts/`](scripts/) | the collector, the anonymiser, and the checks that re-derive and assert every published figure |

**Case Study 1** is the first system run through the method: Qwen3.8-Max, through the Qoder CN
integrated development environment and Alibaba Cloud Model Studio, over ten days of one person's real
work. The finding in four lines, where the report spends twenty:

- The registry offered 1M-context presets for an entry whose own declared input limit is 180,000
  tokens.
- Requests over the limit came back as "Response timeout" (client code 80408). The service's own code
  for that condition, `80411 "Input content too long"`, fired zero times.
- The resume button re-submitted the identical request: the same bytes into the same wall.
- Predictable inside a burst, random across days — a fixed client watchdog meeting a server latency
  that moves. Context size raised the odds; it never gated.

Three log streams carry that, not memory: the banner events; the client's own task tracker, which
reached `ActionRequired` within 234 ms of every banner (report §4.6) and whose `task` names a chat
conversation, not a chat box (report §3.1); and the phase stream (report §4.7), timestamping every
send, first streamed chunk, tool dialog, banner, resume click and turn end. Three clocks on one event
is what turns a complaint into a latency distribution.

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

The capture and shipping pipeline is not in this repository: the collector that reads the
installation, the tamper-evident log mirror with its systemd timers, the browser-side cross-check
watcher, the release gate, the payload builders. This is a public record of an observation, not a
toolkit. `methodology.md` says what each instrument did, and the archived source copies under Cite
this below carry the whole pipeline, so the collector stays reachable from a citation.

## Cite this

| Object | Identifier |
|---|---|
| The method and findings | `paper_ai_QoS.md` in this repository, at a **tag** — cite the paper, and the snapshot you read |
| The archived software (every version) | concept DOI [10.5281/zenodo.22701430](https://doi.org/10.5281/zenodo.22701430) — always resolves to the latest archived version; `v1.0.0` is [10.5281/zenodo.22701431](https://doi.org/10.5281/zenodo.22701431) |
| The evidence, loadable | <https://huggingface.co/datasets/2makeitwork/paper_ai_Qos> |
| A specific number | the commit that produced it, plus `python3 scripts/analyze.py`, which re-derives it from `evidence/` |

`CITATION.cff` carries the same for machines. The dataset card's Citation section gives the rules:
cite a snapshot, not a branch; name the collection round; cite the client version and service, not
the model alone, because a watchdog on your own desk is easy to misattribute to a model.

## Verify this repository yourself

```bash
python3 scripts/analyze.py                  # re-derives and asserts every published figure
python3 scripts/verify_dataset_card.py      # checks the card against the files it declares
python3 scripts/check_release_sync.py --ref <tag>    # optional, needs network: compares
                                            # the served dataset repository with the tag
```

Every check above exists because something once passed review and was wrong; the reasons are in the
commit messages. One limit: rebuilding the evidence tree needs the same machine, installation and
frozen raw dump. `methodology.md`, under "What re-runs, and from what", records which claims were
re-tested and what the attempt produced. Evidence timestamps are local time (AWST, UTC+8).

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
