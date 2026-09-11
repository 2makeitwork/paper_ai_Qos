# Abstract and entry texts

One description of this project at four lengths. The authoritative text is the abstract in
`paper_ai_QoS.md`; what follows are shorter forms of the same content for people who need a
sentence rather than a paragraph, and they are not expected to match it word for word.

> **Released 2026-09-11 as v1.0.1** (methodology v0.1). This snapshot is frozen: later
> corrections and additions ship as a new version with a new tag, never as an edit to the bytes a
> citation points at — cite the tag or the Digital Object Identifier, not a branch. Two version
> numbers mean two different things here: the tag names this public snapshot, while *methodology
> v0.1* names the definitions, which stay unchanged until a second provider has been measured
> (section 7). Every figure quoted in this document set is asserted against the shipped evidence by
> `scripts/analyze.py`, which fails when a number and the evidence disagree and warns when a file
> is edited after the date above.

## Project identity

* Publication identity: **AI Service QoS — Independent Measurement of What Users Actually Receive**
* Differentiating claim: the novelty is of **perspective, not method** — the measurement point is the paying user's side, published in aggregate to check what a provider delivered, a vantage no prior external measurement occupies.
* North star: An independent, outside-in measurement framework for evaluating the reliability, latency, usability, and failure behavior of AI services under real user workloads.
* Release title: **AI Service QoS: An Independent Outside-In Measurement Methodology** — with the Qwen3.8-Max / Qoder incident as **Case Study 1**
* Methodology version: **v0.1**
* Author: **2makeitwork** — independent, unaffiliated (decided 2026-09-11). No institution name goes
  in any byline, citation, dataset card or archive record; an empty affiliation field is the
  intended state, not an oversight.

## Abstract, condensed

Capability benchmarks score answers. They do not measure the service: how long a request waits, whether it is silently dropped, how a provider reports an overflow, or how many retries a user spends getting a usable reply. Nor is this external latency benchmarking or gateway auditing, which measure inference-system performance under controlled loads and provider honesty respectively. This paper establishes a method for measuring the quality of service (QoS) an AI service actually delivers, at the level of the individual submitted request, defined from the user's side and independently of any provider's vocabulary, so that results are comparable across services and verifiable without vendor cooperation. The method specifies a unit of observation, a latency distribution rather than a mean, a six-class outcome taxonomy with raw provider codes retained alongside it, project-defined denominators, retry accounting that never folds retries into successes, a task taxonomy following real work, and a machine-readable event schema. We demonstrate it on one field incident — Qwen3.8-Max through the Qoder CN IDE, where 33 requests timed out as client code 80408 while the dedicated input-too-long code never fired, against a registry advertising 1M context over a declared 180,000-token input limit. The incident is the example, not the subject. A second collection round the following day turned the size claim from correlation into a within-conversation experiment: in a conversation the client itself reported at 490,789 and 494,193 context tokens, five stalls produced no streamed output at all, and after the client's own context-compaction control reduced that conversation to 117,153 tokens, the next request — carrying 85,115 — returned its first streamed chunk in 8.4 seconds; the largest context that completed anywhere in that round was 452,447 tokens, and pooled data from both rounds overlap in size, so context is reported as a probability factor and never as a threshold. Three negative results are stated with the same weight as the positive ones: panel visibility, server-side cache residency, and inflating an agent's context by instructing it to read files. We neither benchmark that model nor investigate why the server stalls; both require data only the vendor holds, and the schema is written so that a vendor can supply exactly that data and answer them.

## One line

A user can tell within a day whether a model is good enough. This measures what they cannot
tell — whether the vendor will answer, in time, on the day it matters — request by request, from
the client's own log, with no vendor cooperation.

## Short form (about 300 characters)

A request-level way to measure the one property of an artificial-intelligence service that a user
cannot evaluate for themselves: capability reveals itself in a day of real work, delivery does not,
and it arrives as one generic banner whatever caused it. Defined from the user's side and
independent of any provider's vocabulary: unit of observation, latency distributions, a six-class
outcome taxonomy, retry accounting and a machine-readable event schema — demonstrated on a ten-day
field incident with every figure reproducible from the shipped evidence.

## Three sentences

Capability benchmarks tell you how good a model is; nothing in them tells you
whether your own request got a usable answer, how long it waited, or what the
provider said when it silently did not answer. This work specifies the measurement
method for that question — one submitted user request at a time, from the client
side — and demonstrates it on a ten-day incident in which 33 requests failed as a
generic timeout while the dedicated input-too-long code never fired once, and in
which the same conversation stalled five times at 490,789 context tokens yet
answered in ten seconds once its context was compacted to 117,153. The evidence is
anonymised, machine-checked and re-derivable by script: every published number is
asserted against the shipped files, and the open questions we could not answer from
the outside are listed for the vendor.

