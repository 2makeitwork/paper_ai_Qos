An independent, outside-in measurement of what an artificial-intelligence service actually
delivers to a user — request by request, from the client's own log, with no vendor cooperation
and no access to the provider's infrastructure.

**The contribution is the paper, `paper_ai_QoS.md`.** Methodology v0.1 specifies a request-level
unit of observation, a latency distribution rather than a mean, a six-class outcome taxonomy that
keeps the provider's own codes beside it, explicit denominators, retry accounting that refuses to
hide retries inside successes, a task taxonomy following real work, and a machine-readable event
schema — all defined independently of any provider's vocabulary, so results are comparable across
services and verifiable without a provider's cooperation.

The novelty is one of **perspective, not of method**. The instruments are shared with prior
external measurement of model services; the vantage is not — a reading taken on the paying user's
side, published as a stratified public aggregate, which checks what a provider *delivered* rather
than ranks what a system *computes*. Section 1.4 names the prior work and the difference;
section 7.1 states the institution this is meant to serve, with broadband performance reporting as
its working analogue.

Everything else in this repository is a means to that end:

- `report_qwenAliServiceQuality.md` — **Case Study 1**, the case report written for the provider:
  the per-event tables, the reproduction steps and the requests made of the vendor
- `methodology.md` — detection anchors, file-by-file provenance, and what re-derives from what
- `analysis/summary_tables.md` — the derived statistics, as generated
- `DATASET_CARD.md` — the dataset card, published as the README of the dataset repository

**Case Study 1** is the first system measured, not the subject: Qwen3.8-Max through the Qoder CN
integrated development environment and Alibaba Cloud Model Studio, over a ten-day field incident in
which 33 requests failed as one opaque client timeout code while the dedicated input-too-long code
the service documents never fired once, against a model registry advertising 1M-context presets for
an entry whose own declared input limit is 180,000 tokens. A second collection round the next day
turned the size claim from correlation into a within-conversation experiment, and reports three
negative results with the same weight as the positive ones.

Loadable evidence: <https://huggingface.co/datasets/2makeitwork/paper_ai_Qos>

Archived under DOI [10.5281/zenodo.22701430](https://doi.org/10.5281/zenodo.22701430) — the
concept identifier, covering every archived version of this release; `v1.0.0` is
[10.5281/zenodo.22701431](https://doi.org/10.5281/zenodo.22701431).

Every figure quoted in those documents is recomputed from the shipped `evidence/` and asserted by
`python3 scripts/analyze.py`, which fails when a number and the evidence disagree;
`python3 scripts/verify_dataset_card.py` checks the card against the files it declares, and
`./scripts/preflight.sh` runs every check in one pass. All three run in either repository and need
nothing beyond the files themselves.

**Version 1.0.1, released 2026-09-11.** What changed since `v1.0.0`: the front page and this note
now present the paper as the contribution and the case report, evidence and tooling as the means it
serves; the archive identifiers above are recorded in `CITATION.cff`, whose invented `versions:` key
was replaced by schema-valid `identifiers:` and whose `cff-version` is corrected to 1.2.0. **No
evidence, no definition and no figure moved** — *methodology v0.1* names the definitions, which
stay unchanged until a second provider has been measured, while this tag names the public snapshot.
Cite the tag or the identifier, not a branch. Author: 2makeitwork — independent, unaffiliated.
Text, tables, figures and data under Creative Commons Attribution 4.0; executable tooling under
`scripts/` under the MIT license.
