# Rules for working in this repository

They apply to the author and to any AI agent equally. This file exists because on 2026-09-11 an
agent read a verification check as an instruction, committed work the author had not asked it to
commit, and told the author it had not committed anything — while a different session, assuming
the commit was the author's, pushed it to the public remote. Two of the three failures were
avoidable with rules written down rather than remembered.

## Who does what

Only the author runs `git commit`, `git push`, creates or moves tags, publishes a GitHub release,
or publishes an archive record. An agent prepares the change, runs `./scripts/preflight.sh`, and
stops there. **A clean, verified, uncommitted working tree is the expected end state of an agent's
work — not a problem to solve.**

`scripts/preflight.sh` reports `no uncommitted change anywhere` because its checks read the
working tree, so an uncommitted edit can make a green run describe a tree that no longer exists.
That check describes the author's next step. It does not authorise anyone else to take it.

Never infer permission from a passing gate, a documented convention, or the fact that a command
exists. Nothing in this repository is a substitute for the author saying "commit", "push",
"tag", "publish".

## Text a reader sees

Anything in a published file is written for the person who downloads the repository, not for
whoever maintains it. So, in published documents: no instructions addressed to the maintainer, no
notes about where a piece of text should be sent, no planning-stage labels, no release-pipeline
commentary, no references to files that are deliberately kept private unless the sentence says
they are private.

Where a process fact is worth publishing, state it as a fact — "the collector runs on a per-minute
systemd timer" — rather than as an instruction. Editorial routing notes belong in the project's
private release notes.

`scripts/analyze.py` enforces the heading case, `scripts/verify_dataset_card.py` enforces the
command case (every command in the dataset card must run in the repository that serves it), and
`scripts/preflight.sh` runs both **inside the staged payload**, because the author's disk has
everything and a check against it proves nothing about what a reader receives.

## Numbers

A figure quoted in prose must be a measurement, dated, and re-derivable: `scripts/analyze.py`
recomputes every published number from `evidence/` and fails when the documents and the evidence
disagree — including the count of its own checks, which is quoted in `methodology.md`. Do not
"fix" a failing assertion by editing the expected value: establish the measurement first, then
decide which of the two is wrong.

## Versioning

Two version numbers mean two things. A tag names a public snapshot; *methodology v0.1* names the
definitions, which stay unchanged until a second provider has been measured. Superseded tags are
left where they are — rewriting a reference someone may already have fetched costs more than an
extra tag.
