---
pretty_name: AI Service QoS — field evidence for a Qwen3.8-Max / Qoder CN incident
tags:
  - ai-evaluation
  - observability
  - reliability
  - latency
  - large-language-models
  - service-quality
size_categories:
  - n<1K
language:
  - en
license:
  - cc-by-4.0          # documented key is `license` (accepts a list); `licenses` is ignored
configs:
  - config_name: request_lifecycle_round1
    data_files:
      - split: train
        path: evidence/stats/request_lifecycle.csv
    default: true
  - config_name: request_lifecycle_round2
    data_files:
      - split: train
        path: evidence/incident_20260910/request_lifecycle.csv
  - config_name: session_sizes
    data_files:
      - split: train
        path: evidence/stats/session_size_stats.csv
  - config_name: context_growth
    data_files:
      - split: train
        path: evidence/stats/context_growth.csv
  - config_name: timeline_events
    data_files:
      - split: train
        path: evidence/stats/timeline_events.csv
  - config_name: timeout_events
    data_files:
      - split: train
        path: evidence/logs/timeout_resume_events.csv
---

# AI Service QoS — field evidence

> **Pre-release, last revised 2026-09-11** (methodology v0.1). Definitions, wording and figures
> may still change; cite a snapshot — a release tag or a commit, not a branch — so that a later
> revision cannot move what your citation points at. Every figure quoted in this document set is
> asserted against the shipped evidence by `scripts/analyze.py`, which fails when a number and the
> evidence disagree and warns when a file is edited after the date above.

**AI Service QoS — Independent Measurement of What Users Actually Receive** — methodology v0.1, and the first data product of an independent, outside-in measurement framework. The system measured here is **Case Study 1**, not the subject: the framework claims provider neutrality and one provider is not proof of it — a second provider measured with *these same definitions and no new ones* is the test (paper section 7, Stage 3).

Machine-checkable evidence for **"AI Service QoS: An Independent Outside-In Measurement Methodology, with Case Study 1 (Qwen3.8-Max / Qoder)"** (`paper_ai_QoS.md`, with the practitioner report
`report_qwenAliServiceQuality.md`). It is a request-level measurement of the
service quality an ordinary user experiences in an artificial-intelligence coding
service, taken entirely from the client's own runtime log, with no provider
cooperation and no access to the provider's infrastructure.

## Dataset details
### Where each layer of this project lives

This repository is the **data layer**. The method document (`paper_ai_QoS.md`) and
**Case Study 1** (`report_qwenAliServiceQuality.md`), the vendor-facing report with the
per-event tables and the asks, are in the source repository:
<https://github.com/2makeitwork/paper_ai_Qos> — together with the collector, the
anonymiser and the log mirror that produced these files. Two scripts ship **here** as
well, so that nothing in this card has to be taken on trust inside this repository:
`scripts/analyze.py` re-derives and asserts every published figure against `evidence/`,
and `scripts/verify_dataset_card.py` asserts this card against the files it declares.


### Motivation

Capability benchmarks score answers; provider dashboards report what the provider
chooses to measure. Neither answers the user's question — *did my request get a
usable answer, and how long did I wait?* This dataset exists so that question can
be asked of a service from the outside, and so every number in the paper can be
recomputed from these files rather than taken on trust.

### Verification after publication

The whole published repository was downloaded back to an empty directory and compared file by
file with the working tree: **34 of its 36 files were byte-identical** (measured 2026-09-11; the
repository's commit history shows which revision that was). The two exceptions are
known and intended — the hub's own `.gitattributes`, created with the repository, and
`README.md`, which is this card with three lines of internal instruction removed (the source
repository's `README.md` is a different document, its homepage). One caveat if you re-run the
shipped scripts: the last line of `analysis/summary_tables.md` carries a generation timestamp,
so that file moves on every run — a difference in when it was built, not in what it says.
(Incidental finding for anyone scripting the client: `hf download --include` accepts repeated
patterns but only honoured the last one, so pass one pattern per invocation.)

Both scripts were then executed **inside that download**, with nothing else present:
`scripts/verify_dataset_card.py` exits 0 and `scripts/analyze.py` passes 52 assertions against
`evidence/`. The cross-document drift check between the paper and the case report prints an
explicit skip there, because the narratives live in the source repository — a skip, never a
silent pass.

### Composition

| Path | Contents |
|---|---|
| `evidence/logs/` | 388 kilobytes: the 33-event timeout extract, 1,252 conversation-lifecycle lines from the client's task tracker, 885 per-interaction phase lines, 50 quota-error log lines with payload variants, the outcome census |
| `evidence/config/` | 108 kilobytes: the fetched error-code dictionary entries, the model-registry line and the bring-your-own-key definitions that show the 180,000-versus-1,000,000 contradiction, the selected context presets, the environment record |
| `evidence/stats/` | 44 kilobytes: 20-conversation transcript size table, the context-growth curve, the merged timeline, the round-1 request-lifecycle table |
| `evidence/incident_20260910/` | 20 kilobytes: the second collection round — 62 request episodes carrying per-request **context occupancy in tokens**, plus its own README |
| `evidence/screenshots/` | 152 kilobytes: the operator's screen showing nine consecutive timeout banners in one conversation |
| `evidence/error_messages.json` | Every string the paper quotes, verbatim, in one place |
| `analysis/summary_tables.md` | The derived statistics, regenerated and asserted by `scripts/analyze.py` |

Totals: 25 files, 724 kilobytes under `evidence/`, plus the generated analysis
table. Two collection rounds, deliberately separate: 2026-09-01 → 09-09 (frozen
bundle, conversation labels `sess-01` … `sess-20`) and 2026-09-10 (labels `S1` …,
own frozen log snapshot).

### How to load it, and how to check that this card is telling the truth

The six tabular files are declared as named configs, so a reader loads a table
directly instead of eyeballing markdown:

```python
from datasets import load_dataset

round2 = load_dataset("2makeitwork/paper_ai_Qos", name="request_lifecycle_round2")
round2["train"].num_rows          # 62 request episodes
round2["train"][0]["used_tokens_at_send"]
```

The six configs: `request_lifecycle_round1` — 308 rows, `request_lifecycle_round2` —
62 rows, `session_sizes` — 20 rows, `context_growth` — 93 rows, `timeline_events` —
51 rows, `timeout_events` — 33 rows. Everything else under `evidence/` — the log
extracts, the configuration records, the screenshot — is deliberately **not** a
config: those are line-oriented evidence files meant to be read and grepped, and
flattening them into a table would destroy the timestamps that make them
verifiable.

Two independent checks, one offline and one after upload:

```bash
python3 scripts/verify_dataset_card.py           # every declared file exists, every
                                                 # declared column matches its header,
                                                 # row counts match the card text
python3 scripts/analyze.py                       # asserts all 50 published figures
```

```bash
python3 -c "from datasets import load_dataset; \
  [load_dataset('2makeitwork/paper_ai_Qos', name=n)['train'] for n in \
   ['request_lifecycle_round1','request_lifecycle_round2','session_sizes', \
    'context_growth','timeline_events','timeout_events']]; print('LOADABLE')"
```

**State as published (first upload 2026-09-10, commit `16a35ca`; revised in place since).** Confirmed by the hub: the
repository is public, 36 files, and the front matter was parsed — its tags carry
`license:cc-by-4.0`, `size_categories:n<1K` and `language:en`. **Confirmed by the hub** later the same day
(2026-09-10): its conversion endpoint returned **all six** configs with their `train`
splits — `request_lifecycle_round1`, `request_lifecycle_round2`, `session_sizes`,
`context_growth`, `timeline_events`, `timeout_events` — which is what `load_dataset` and
the dataset Viewer read. Minutes after the first commit the same endpoint returned
`500 Internal Server Error`, so the conversion is asynchronous and a single early
failure means nothing. One thing this does **not** establish: the `datasets` library is
not installed on the workstation that published this, so the Python snippet above has
not been executed here — the configs are server-converted, not snippet-verified.

The non-tabular part of the bundle stays browsable and downloadable either way;
making a file loadable is not the same as making it required for reproduction.

### Collection process

A single workstation, a single subscription account, one operator, nine plus one
days. The client's runtime log tree was mirrored continuously (append-only, one
file per path and inode, each committed region re-hashed on every scan so an
in-place edit of already-written log bytes is detectable), frozen as checksummed
snapshots, then filtered to named log anchors and anonymised by script. Nothing
was typed by hand into any file under `evidence/`.

## Personal and private content

**Conversations are not included.** Full chat transcripts carry third-party
project content, so they are excluded from the bundle entirely; only statistics,
error-related log extracts and configuration records pass through. Identifiers are
replaced by a deterministic, script-built map — paths, user names, host names,
local network addresses, account and model identifiers, application programming
interface keys, and every conversation identifier (report `anonymization.md`). The
anonymizer fails with a non-zero exit code if any forbidden pattern survives its
own output, and a repository-wide gate re-checks every published file, link and
ignored directory:

```bash
python3 scripts/analyze.py                  # re-derives and asserts every published figure
python3 scripts/verify_dataset_card.py      # asserts this card against the files it declares
python3 scripts/check_release_sync.py       # compares this repository's bytes with the source
                                            # repository and the Zenodo record
```

The first two run offline and exit 0 in either repository — the source repository and this
data layer — against the files shipped here. The third reaches the hub (and Zenodo, given a
record identifier) and is the release-time check that the copy you are reading is byte-for-byte
the copy in the other places: it reports drift rather than asserting agreement, because the
three locations are updated by different commands and nothing synchronises them. The self-audit
of the anonymiser itself (`scripts/anonymize.py --input raw_evidence`) needs the raw logs, which
are not published, and the document gate over links, personal data and ignore rules (`tools/`) is
local-only tooling that is deliberately not part of either repository: the commands above are what
a reader can actually run, so they are what this card asks a reader to run.

Pseudonyms (`sess-NN` in round 1, `S1`… in round 2) are numbered by the data's own
order; the mapping to real conversation identifiers is not published and cannot be
recovered from these files.

## Uses

```bash
python3 scripts/analyze.py          # asserts all 50 published figures against evidence/
python3 scripts/latency_from_logs.py raw_snapshots/<stamp>/logs \
        --since 2026-09-10T00:00 --emit-csv /tmp/round.csv    # rebuild a round
```

Use it to reuse the event schema, to check the paper's arithmetic, to compare your
own provider against the method, or as training data for nothing at all — see
below.

### Out-of-scope uses

Not a model-quality benchmark and not a leaderboard: it measures the service, not
the answers, and one account over ten days cannot rank providers. Not suitable as
model training data — it contains no conversational text by design. Not a
certification of the named products; the vendor's replies are collected in
`ask_vendor.md` and were not received at publication time.

## Limitations

Single workstation, single account, single model pair, ten days, no provider
cooperation. Observational except for one within-conversation pair (context
compaction). Log retention is size-based and shallow, so the earliest events of a
busy conversation are unrecoverable. The client's timeout threshold is inferred
from its own state machine, not documented by the vendor. Request **size** is
available from the client only as context occupancy; output-token and
cached-input-token counts are absent, which is why the mechanism question stays
open. State each of these whenever the data is reused.

## Citation

```
2makeitwork (independent, unaffiliated). "AI Service QoS: An Independent Outside-In
Measurement Methodology,
with Case Study 1 (Qwen3.8-Max / Qoder)." Dataset snapshot <tag or commit>, 2026.
```

Cite the **snapshot**, name the **collection round**, and cite the **client version
plus service** rather than the model alone — a client-side watchdog misattributed to
a model is the most likely misquote. `CITATION.cff` carries the machine-readable
form; the positioning against prior measurement work is in the paper's section 1.4, with each
work's own identifier given there.

## License

Text, tables, figures and data: **Creative Commons Attribution 4.0**
(`LICENSE-content.md`). The scripts published alongside it, which re-derive and assert
every number in this card: **MIT** (`LICENSE-code.md`).
