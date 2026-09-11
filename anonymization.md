# Anonymization policy

> **Released 2026-09-11 as v1.0.0** (methodology v0.1). This snapshot is frozen: later
> corrections and additions ship as a new version with a new tag, never as an edit to the bytes a
> citation points at — cite the tag or the Digital Object Identifier, not a branch. Two version
> numbers mean two different things here: the tag names this public snapshot, while *methodology
> v0.1* names the definitions, which stay unchanged until a second provider has been measured
> (section 7). Every figure quoted in this document set is asserted against the shipped evidence by
> `scripts/analyze.py`, which fails when a number and the evidence disagree and warns when a file
> is edited after the date above.

Everything under `evidence/` is produced by `scripts/anonymize.py`, which
builds a deterministic pseudonym map from the raw dump and refuses to finish
if any forbidden pattern survives (exit code 1 + `LEAK` report). The map is
rebuilt from scratch on every run; nothing is hand-edited.

## What is removed or pseudonymized

| Class | Example form | Replacement | Assignment rule |
|---|---|---|---|
| OS user & home | `/home/<real>/…` | `/home/user/…` | fixed |
| Host/user prompt | `<user>@<host>:` | `user@host:` | fixed |
| Workspace/project names | `<projectname>-<hash8>` cache dirs and bare names | `ws-A-cache`, `ws-A` … | letter by first appearance |
| Chat session ids | 8-hex short ids and full UUIDs | `sess-01` … | number by order in the session statistics table |
| Other UUIDs (tool calls, request ids) | full UUIDs | `call-001` … | number by first appearance |
| BYOK model record ids | `model_17…_xxxxxx` | `byok-model-01` … | number by sorted order |
| Account/tenant id | vendor tenant UUID | `<account-id>` | fixed pattern |
| LAN addresses | `192.168.x.x` | `<lan-ip-1>` … | number by sorted order |
| Private hostnames | ssh aliases appearing in captured lines | `<host-1>` | fixed list |
| API keys | never collected: the BYOK export drops the `apiKey` field at the source, `secret://…` state-DB entries are not read; a `sk-…` pattern guard exists as a backstop | `<redacted-key>` | pattern |

Echo lines (the investigating agent's own shell commands, captured inside the
IDE logs) are dropped entirely — they are self-referential, not evidence.

Full chat transcripts are excluded from the published bundle altogether:
regex scrubbing cannot be trusted to catch everything a user typed into a
work session.

## What is kept, deliberately

- All timestamps (millisecond precision, local time AWST = UTC+8).
- All error codes and banner/message strings, verbatim.
- Product identifiers: client name/version/commit, model display names and
  registry ids (`qmodel_38max`, `qwen3.8-max-tp`) — public product facts.
- The vendor's public pricing URL, the error-dictionary version and fetch time.
- The operator handle `2makeitwork` (intended public attribution).
- The screenshot (IDE UI text only; no filesystem paths visible in it).

## Re-checking

`anonymize.py` audits its own output against the forbidden-pattern list
(`/home/<user>`, username, private hostnames, LAN ranges, key patterns,
tenant id, BYOK ids). To independently spot-check:

```bash
grep -rE "/home/[a-z]|@[a-z]+:[a-z]|192\.168\.|sk-[A-Za-z0-9]{16}" evidence/ && echo FOUND || echo clean
```

Pseudonyms are stable only within one run against one raw dump; re-collecting
after new activity may renumber `call-NN`/`sess-NN`. Correlations inside the
published files (timeline ↔ events ↔ stats) are therefore self-consistent,
and that is all the study requires.
