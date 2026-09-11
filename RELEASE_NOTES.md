An independent, outside-in measurement of what an artificial-intelligence service actually
delivers to a user — request by request, from the client's own log, with no vendor
cooperation and no access to the provider's infrastructure.

**Methodology v0.1**, demonstrated on **Case Study 1**: Qwen3.8-Max through the Qoder CN
integrated development environment and Alibaba Cloud Model Studio, over a ten-day field
incident in which 33 requests failed as one opaque client timeout code while the dedicated
input-too-long code the service documents never fired once, against a model registry
advertising 1M-context presets for an entry whose own declared input limit is 180,000 tokens.

Start here:

- `paper_ai_QoS.md` — the method and the findings
- `report_qwenAliServiceQuality.md` — the case report written for the provider, with the
  per-event tables, the reproduction steps and the requests made of the vendor
- `methodology.md` — detection anchors, file-by-file provenance, and what re-derives from what
- `analysis/summary_tables.md` — the derived statistics, as generated
- `DATASET_CARD.md` — the dataset card, published as the README of the dataset repository

Loadable evidence: <https://huggingface.co/datasets/2makeitwork/paper_ai_Qos>

Every figure quoted in those documents is recomputed from the shipped `evidence/` and asserted
by `python3 scripts/analyze.py`, which fails the build when a number and the evidence
disagree; `python3 scripts/verify_dataset_card.py` checks the card against the files it
declares. Both run in either repository and need nothing beyond the files themselves.

**Version 1.0.0, released 2026-09-11.** The contribution is a novelty of **perspective, not of
method**: the instruments are shared with prior external measurement of model services, while the
vantage is not — a reading taken on the paying user's side, published as a stratified public
aggregate, which checks what a provider delivered rather than ranks what a system computes.
Section 7.1 of the paper states the institution this is meant to serve and the two design duties
left open. Two version numbers mean two things: this tag names the public snapshot, while
*methodology v0.1* names the definitions, which stay unchanged until a second provider has been
measured. Cite the tag, not a branch. Author: 2makeitwork — independent, unaffiliated. Text,
tables, figures and data under Creative Commons Attribution 4.0; executable tooling under
`scripts/` under the MIT license.
