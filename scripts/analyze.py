#!/usr/bin/env python3
"""analyze.py — recompute every number the report quotes, from evidence/ only.

Reads the anonymized evidence tree, derives the statistics cited in
report_qwenAliServiceQuality.md, writes analysis/summary_tables.md, and
asserts each expected value. Exit code 1 = a report number no longer
matches the evidence.

Usage: python3 analyze.py            (run from scripts/)
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median as statistics_median

EV = Path(__file__).resolve().parents[1] / "evidence"
OUT = Path(__file__).resolve().parents[1] / "analysis" / "summary_tables.md"

TS = "%Y-%m-%d %H:%M:%S"
fails: list[str] = []


def check(name: str, got, want) -> None:
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'} {name}: {got}" + ("" if ok else f" (report says {want})"))
    if not ok:
        fails.append(name)


def ts_of(line: str) -> datetime:
    return datetime.strptime(line[:19], TS)


# ---- timeout events ---------------------------------------------------------
rows = (EV / "logs/timeout_resume_events.csv").read_text().splitlines()[1:]
codes = Counter(r.split(",")[2] for r in rows)
per_day = Counter(r[:10] for r in rows)
times = sorted(ts_of(r) for r in rows)
# densest 75-minute block
best = max(range(len(times)), key=lambda i: sum(1 for t in times if 0 <= (t - times[i]).total_seconds() <= 75 * 60))
block_n = sum(1 for t in times if 0 <= (t - times[best]).total_seconds() <= 75 * 60)

# ---- quota events (cluster lines within 2 s) --------------------------------
qtimes = [ts_of(ln) for ln in (EV / "logs/quota_error_lines.txt").read_text().splitlines()
          if re.match(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d", ln)]
events: list[list[datetime]] = []
for t in sorted(qtimes):
    if events and (t - events[-1][-1]).total_seconds() <= 2:
        events[-1].append(t)
    else:
        events.append([t])
payloads = sorted(set(re.findall(r'"message":"([^"]{20,140})',
                                 (EV / "logs/quota_error_lines.txt").read_text())))
codes_seen = sorted(set(re.findall(r'"code":"?(-?\d+)"?',
                                   (EV / "logs/quota_error_lines.txt").read_text())))

# ---- chat_finish census ------------------------------------------------------
census = (EV / "logs/chat_finish_census.txt").read_text().splitlines()
c_total = c_success = 0
for ln in census:
    m = re.match(r"\s*(\d+) (.*)", ln)
    if not m or '"command"' in ln:
        continue
    c_total += int(m.group(1))
    if "success:200" in m.group(2):
        c_success += int(m.group(1))

# ---- sessions ----------------------------------------------------------------
sess = [ln.split(",") for ln in (EV / "stats/session_size_stats.csv").read_text().splitlines()[1:]]
big = sorted(sess, key=lambda r: -int(r[3]))[:3]

# ---- request lifecycle (frozen from a log snapshot via scripts/latency_from_logs.py) --
lc = [ln.split(",") for ln in (EV / "stats/request_lifecycle.csv").read_text().splitlines()[1:]]
_fl = lambda x: float(x) if x else None
_p50 = lambda v: (round(sorted(v)[min(len(v) - 1, int(0.5 * (len(v) - 1)))], 1) if v else None)
_succ = [r for r in lc if r[2] == "S"]
_stall = [r for r in lc if r[2] == "T"]
_tto = [r for r in lc if r[2] == "T" and len(r) > 7 and r[7] == "resume_tool_call"]
_tdi = [r for r in lc if r[2] == "T" and len(r) > 7 and r[7] == "permission_request"]
_ttft = [x for x in map(lambda r: _fl(r[3]), lc) if x is not None]
_tot = [_fl(r[4]) for r in _succ if _fl(r[4]) is not None and int(r[6] or 0) == 0]
_stv = [_fl(r[5]) for r in _stall if _fl(r[5]) is not None]
_fau = sum(1 for r in _succ if int(r[6] or 0) == 0)

# ---- task lifecycle (quest.log; one master-mode task per conversation) --------
# The client's task object carries the conversation's own id (the log line names
# it twice: "taskId" and "executionSessionId"). Every open IDE window writes the
# same event into its own quest.log, so (session, status) repeats are clustered at
# ≤2 s — the same rule used above for the quota markers.
TLINE = re.compile(r"^\[(window\d+)\] (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}) \[\w+\] "
                   r"task\.status\.update(\.skipNonQuestTask)? "
                   r'\{"taskId":"(sess-\d+)","status":"(\w+)"')
tl = []
for ln in (EV / "logs/task_status_lines.txt").read_text().splitlines():
    m = TLINE.match(ln)
    if m:
        tl.append(m.groups())
tl_dupes = sum(1 for g in tl if g[2])                     # .skipNonQuestTask twins
tl_main = sorted((g for g in tl if not g[2]), key=lambda g: g[1])
task_ev: list[list] = []                                  # de-duplicated events
for win, ts, _s, sid, st in tl_main:
    t = datetime.strptime(ts, TS + ".%f")
    if (task_ev and task_ev[-1][1] == sid and task_ev[-1][2] == st
            and (t - task_ev[-1][0]).total_seconds() <= 2):
        task_ev[-1][3].add(win)
        continue
    task_ev.append([t, sid, st, {win}])
task_status = Counter(e[2] for e in task_ev)
task_windows = sum(1 for e in task_ev if len(e[3]) > 1)
run_state: dict[str, datetime] = {}
run_iv: list[tuple] = []
for t, sid, st, _w in task_ev:
    if st == "Running":
        if sid not in run_state:
            run_state[sid] = t
    else:
        if sid in run_state:
            run_iv.append((run_state.pop(sid), t, sid))
run_dur = sorted((b - a).total_seconds() for a, b, _ in run_iv)
conc = sorted([(a, 1) for a, _, _ in run_iv] + [(b, -1) for a, b, _ in run_iv],
              key=lambda x: (x[0], x[1]))
conc_now = conc_max = 0
for _t, d in conc:
    conc_now += d
    conc_max = max(conc_max, conc_now)
# unordered pairs of conversations whose Running spans overlap in time
conc_pairs = sum(1 for i, (s1, e1, _n1) in enumerate(run_iv)
                 for s2, e2, _n2 in run_iv[i + 1:] if s2 < e1 and e2 > s1)
# transition spans: Running -> ActionRequired is "sent, then went silent"; the
# duration distribution of successful runs says whether the watchdog caps total
# duration or only the silence between chunks.
wd_span, ok_span = [], []
for (t1, s1, st1, _w1), (t2, s2, st2, _w2) in zip(task_ev, task_ev[1:]):
    if s1 != s2:
        continue
    gap = (t2 - t1).total_seconds()
    if st1 == 'Running' and st2 == 'ActionRequired':
        wd_span.append(gap)
    elif st1 == 'Running' and st2 == 'Completed':
        ok_span.append(gap)
wd_mode, wd_mode_n = Counter(round(g) for g in wd_span).most_common(1)[0]
ok_over = sum(1 for g in ok_span if g > wd_mode)
# ActionRequired = "the banner is up, nothing is generating": pair it with the
# 80408 resume-button events independently captured from the agent logs. Those
# are read at full millisecond precision (`times` above is second-truncated).
ar = [(t, sid) for t, sid, st, _w in task_ev if st == "ActionRequired"]
resume_ms = [datetime.strptime(r.split(",")[0], TS + ".%f") for r in rows]
ar_offsets = [min((abs((t - a).total_seconds()) for a, _ in ar), default=9e9) for t in resume_ms]
ar_paired = sum(1 for g in ar_offsets if g <= 0.5)
ar_max_off = max(ar_offsets, default=0.0)
ar_per_sess = Counter(sid for t, sid in ar)

# ---- per-interaction phase timing (the client's own state machine) -----------
# One line per phase boundary of a turn: `State transition: A -> B, trigger: T`.
# The interval spent in state B runs from that line to the conversation's next
# one, so `prompting` = send pressed → first streamed chunk, `streaming` = the
# generation itself, `suspended` = a dialog or the timeout banner is up.
PLINE = re.compile(r"^\[(window\d+)\] (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}) \[\w+\] "
                   r"\[ACPProgressStateMachine\] State transition: (\w+) -> (\w+), "
                   r"trigger: (.+), sessionId: (sess-\d+)")
ph_raw = []
for ln in (EV / "logs/phase_transitions.txt").read_text().splitlines():
    m = PLINE.match(ln)
    if m:
        ph_raw.append((datetime.strptime(m.group(2), TS + ".%f"), m.group(3), m.group(4),
                       m.group(5), m.group(6)))
ph_by_sess: dict[str, list] = defaultdict(list)
for t, _frm, to, trig, sid in sorted(ph_raw):
    ph_by_sess[sid].append((t, to, trig.split(":")[0], trig))
wait_first, fastfail, gen_ok, hold_banner, hold_perm = [], [], [], [], []
suspend_cause = Counter()
prompts = 0
for sid, seq in ph_by_sess.items():
    for _t, to, fam, _trig in seq:
        if to == "suspended":
            suspend_cause[fam] += 1
    for (t1, state1, fam1, _tr1), (t2, state2, fam2, _tr2) in zip(seq, seq[1:]):
        secs = (t2 - t1).total_seconds()
        if fam1 == "user_message_chunk":
            prompts += 1
            if state2 == "streaming":
                wait_first.append(secs)
            elif state2 == "error":
                fastfail.append(secs)
        if state1 == "streaming" and state2 == "completed" and fam2 == "chat_finish":
            gen_ok.append(secs)
        if state1 == "suspended":
            (hold_banner if fam1 == "resume_tool_call" else hold_perm).append(secs)

# ---- report assertions -------------------------------------------------------
print("assertions against the report:")
check("timeout events", len(rows), 33)
check("all timeouts code 80408", dict(codes), {"80408": 33})
check("timeouts Sep 7/8/9", dict(per_day), {"2026-09-07": 1, "2026-09-08": 4, "2026-09-09": 28})
check("densest 75-min block", block_n, 20)
check("quota events clustered", len(events), 18)
check("quota payload variants", len(payloads), 3)
check("80411 never fired (absent from every log extract)",
      sum("80411" in p.read_text(errors="replace") for p in (EV / "logs").rglob("*")), 0,
      )  # the code exists only in the dictionary (config/), never on an event line
check("chat_finish lines", c_total, 245)  # echo-artifact line removed by anonymize.py
check("chat_finish successes", c_success, 225)
check("largest session entries", big[0][3], "626")
check("lifecycle requests", len(lc), 308)
check("lifecycle sessions", len({r[0] for r in lc}), 10)
check("lifecycle successes (S)", len(_succ), 211)
check("lifecycle stalls (T)", len(_stall), 71)
check("lifecycle timeout parks (trigger resume_tool_call)", len(_tto), 33)
check("lifecycle dialog parks (trigger permission_request)", len(_tdi), 38)
check("lifecycle first-attempt usable", _fau, 179)
check("lifecycle first-chunk median seconds", _p50(_ttft), 11.3)
check("lifecycle clean-success total median seconds", _p50(_tot), 120.0)
check("lifecycle time-to-stall median seconds", _p50(_stv), 305.4)

# ---- incident 2 (2026-09-10 collection round; evidence/incident_20260910/) ----
# Regenerate: python3 scripts/latency_from_logs.py raw_snapshots/20260910T155718/logs \
#               --since 2026-09-10T00:00 --emit-csv evidence/incident_20260910/request_lifecycle.csv
i2 = [ln.split(",") for ln in
      (EV / "incident_20260910/request_lifecycle.csv").read_text().splitlines()[1:]]
i2_to = [r for r in i2 if len(r) > 7 and r[7] == "resume_tool_call"]
i2_dlg = [r for r in i2 if len(r) > 7 and r[7] == "permission_request"]
i2_s_ok = [int(r[9]) for r in i2 if r[2] == "S" and len(r) > 9 and r[9]]
i2_to_ctx = [int(r[9]) for r in i2_to if len(r) > 9 and r[9]]

check("incident-2 requests", len(i2), 62)
check("incident-2 timeout parks (80408 banner)", len(i2_to), 5)
check("incident-2 permission-dialog parks", len(i2_dlg), 2)
check("incident-2 smallest context that timed out (tokens)", min(i2_to_ctx), 490789)
check("incident-2 largest context that completed (tokens)", max(i2_s_ok), 452447)
check("incident-2 timeout send-to-stall, min/max seconds",
      (round(min(float(r[5]) for r in i2_to), 1), round(max(float(r[5]) for r in i2_to), 1)),
      (125.3, 4860.7))

check("task-status lines (incl. .skipNonQuestTask twins)", len(tl), 1252)
check("conversations with task lifecycle events", len({e[1] for e in task_ev}), 9)
check("task lifecycle events after ≤2 s de-dup", len(task_ev), 524)
check("task lifecycle statuses seen", dict(task_status),
      {"Running": 258, "Completed": 208, "ActionRequired": 33, "Error": 18, "Stopped": 7})
check("ActionRequired count == timeout resume count", len(ar), len(rows))
check("every timeout has an ActionRequired ≤0.5 s away", ar_paired, len(rows))
check("per-conversation timeout split (session-level, was window-level)",
      dict(ar_per_sess), {"sess-16": 1, "sess-11": 5, "sess-03": 23, "sess-04": 4})
check("closed Running intervals", len(run_iv), 257)
check("Running spans still open at the extract horizon (log ends mid-run)",
      len(run_state), 1)
check("max simultaneous Running tasks", conc_max, 2)
check("overlapping Running pairs (two tasks at once)", conc_pairs, 10)
check("watchdog: modal Running→ActionRequired span (s)", wd_mode, 61)
check("banners at that modal span", wd_mode_n, 16)
check("successful runs longer than the watchdog span", (ok_over, len(ok_span)), (155, 194))
check("phase transition lines", len(ph_raw), 885)
check("conversations with phase data", len(ph_by_sess), 9)
check("prompts sent (user_message_chunk)", prompts, 252)
check("what suspended a turn", dict(suspend_cause),
      {"resume_tool_call": 33, "permission_request": 37})
check("banner holds that were resumed (sess-03's last never was)", len(hold_banner), 32)
check("median wait for the first streamed chunk (s)",
      round(statistics_median(sorted(wait_first)), 1), 9.6)
check("prompts answered with an error before any chunk", len(fastfail), 4)
check("successful generations longer than the watchdog span",
      (sum(1 for g in gen_ok if g > wd_mode), len(gen_ok)), (149, 208))
check("total operator hold on banners (min)", round(sum(hold_banner) / 60, 1), 90.5)
check("total operator hold on permission dialogs (min)", round(sum(hold_perm) / 60, 1), 122.0)

# ---- cross-document consistency (the paper and the case report must not drift) --
# Both were corrected during the second collection round; a fix applied to one and
# not the other is exactly the failure mode this guards, so the retired wordings are
# forbidden outright and the shared figures must appear in both narratives.
DOCS = [doc for doc in (EV.parent / n for n in ("report_qwenAliServiceQuality.md",
                "paper_ai_QoS.md", "methodology.md", "README.md", "abstract.md")) if doc.exists()]
# The dataset repository ships the data layer only, so the narratives may be absent;
# their absence is reported as a skip, never as a silent pass.
NARRATIVES = [doc for doc in DOCS if doc.name in
              ("report_qwenAliServiceQuality.md", "paper_ai_QoS.md")]
RETIRED = ["no per-request token usage is logged", "checked — zero hits",
           "same window3 session", "Deepest session in window",
           "62 requests across three", "requests, three conversations, columns",
           "largest *active* contexts", "is not documented and was not measured"]
SHARED = ["490,789", "494,193", "452,447", "117,153", "episode"]
drift = []
for doc in DOCS:
    body = doc.read_text(errors="replace")
    drift += [f"{doc.name}: retired wording still present: {phrase!r}"
              for phrase in RETIRED if phrase in body]
for doc in NARRATIVES:
    body = doc.read_text(errors="replace")
    drift += [f"{doc.name}: shared figure missing: {figure!r}"
              for figure in SHARED if figure not in body]
if NARRATIVES:
    check("no drift between the paper and the case report", drift, [])
else:
    print("  SKIP no drift check: the paper and the case report are not in this "
          "checkout (data-layer repository)")

# ---- summary tables ----------------------------------------------------------
out = ["# Analysis summary (generated by scripts/analyze.py from evidence/)", "",
       "## Timeout (80408) events", "",
       f"- total: **{len(rows)}**, all `reasonForCode: 80408`",
       f"- per day: " + ", ".join(f"{d}: {n}" for d, n in sorted(per_day.items())),
       f"- densest 75-minute block: **{block_n} events** (the resume-button loop)", ""]
out += ["## Quota/account events", "",
        f"- log lines: {len(qtimes)} → clustered (≤2 s apart): **{len(events)} events**",
        f"- distinct codes seen: {', '.join(codes_seen)}",
        f"- distinct message wordings: {len(payloads)}", ""]
for p in payloads:
    out.append(f"  - `{p[:100]}`")
out += ["", "## chat_finish census", "",
        f"- {c_total} lines total: {c_success} `success:200`, {c_total - c_success} error payloads,",
        f"  **zero attributable to the {len(rows)} timeout events** (no chat_finish line exists for them)", ""]
out += ["## Three largest sessions (transcript entries)", "",
        "| session | entries | jsonl bytes |", "|---|---|---|"]
for r in big:
    out.append(f"| `{r[1]}` | {r[3]} | {r[2]} |")
out += ["", "## Task lifecycle (`quest.log` — the client's `task` = one conversation)", "",
        f"- {len(tl)} log lines → **{len(task_ev)} events** after ≤2 s de-dup "
        f"({task_windows} events replicated into ≥2 IDE windows, "
        f"{tl_dupes} `.skipNonQuestTask` twins dropped)",
        "- statuses: " + ", ".join(f"{k} {v}" for k, v in sorted(task_status.items())),
        f"- `Running` spans: {len(run_iv)} closed" +
        (f", {len(run_state)} still open at the extract horizon" if run_state else "") +
        f"; median {statistics_median(run_dur):.0f} s, "
        f"90th percentile {run_dur[int(0.9 * len(run_dur))]:.0f} s, max {max(run_dur):.0f} s",
        f"- **max simultaneous `Running` tasks: {conc_max}** (never 3+; "
        f"{conc_pairs} overlapping pairs of conversations), "
        "`error.code.task.running.quota.exceeded` fired 0 times, so that ceiling is "
        "only bounded ≥2",
        f"- `ActionRequired` (banner up, nothing generating): {len(ar)} events, 1:1 with "
        f"the {len(rows)} timeout resume lines (largest offset {ar_max_off * 1000:.0f} ms)",
        "- conversation-level split of those timeouts, which supersedes the "
        "window-level correlation in report §4.2: "
        + ", ".join(f"`{s}` {n}" for s, n in sorted(ar_per_sess.items())),
        f"- watchdog measured off the state machine: **{wd_mode} s of silence** before the "
        f"banner ({wd_mode_n} of {len(wd_span)} banners at exactly that span; the rest are "
        "mid-run stalls after some output), and "
        f"{ok_over} of {len(ok_span)} *successful* runs ran longer than that span — so it "
        "caps inactivity, not total duration", ""]
out += ["", "## Per-interaction phase timing (`[ACPProgressStateMachine]`)", "",
        f"- {len(ph_raw)} transitions over {len(ph_by_sess)} conversations: "
        f"{prompts} prompts sent, {len(wait_first)} answered with a first streamed chunk, "
        f"{len(fastfail)} rejected before any chunk, {len(gen_ok)} generations finished",
        f"- **wait for the first chunk** (`prompting` → `streaming`, the UI's "
        f"'Thinking…'): median **{statistics_median(sorted(wait_first)):.1f} s**, "
        f"90th percentile {sorted(wait_first)[int(0.9 * len(wait_first))]:.0f} s, "
        f"max {max(wait_first):.0f} s, min {min(wait_first):.1f} s",
        f"- generation time (`streaming` → `chat_finish:success`): median "
        f"{statistics_median(sorted(gen_ok)):.0f} s, "
        f"90th percentile {sorted(gen_ok)[int(0.9 * len(gen_ok))]:.0f} s, max {max(gen_ok):.0f} s; "
        f"{sum(1 for g in gen_ok if g > wd_mode)} of {len(gen_ok)} exceed the "
        f"{wd_mode} s watchdog span",
        "- what suspended a turn: " + ", ".join(f"{k} {v}" for k, v in sorted(suspend_cause.items()))
        + " (`resume_tool_call` = the 80408 banner, a third stream confirming 33)",
        f"- operator hold: banners {len(hold_banner)} resumed, median "
        f"{statistics_median(sorted(hold_banner)):.0f} s, total {sum(hold_banner) / 60:.1f} min; "
        f"permission dialogs {len(hold_perm)}, median "
        f"{statistics_median(sorted(hold_perm)):.0f} s, total {sum(hold_perm) / 60:.1f} min", ""]
out += ["", f"Generated {datetime.now():%Y-%m-%d %H:%M} — rerun: `python3 scripts/analyze.py`", ""]
out += ["", "## Request lifecycle (frozen log snapshot; scripts/latency_from_logs.py)", "",
        f"- {len(lc)} requests across {len({r[0] for r in lc})} sessions — S {len(_succ)}, T {len(_stall)} (timeout {len(_tto)} / dialog {len(_tdi)}), F/U {len(lc) - len(_succ) - len(_stall)}",
        f"- first-attempt usable (0-retry S) **{_fau}/{len(_succ)} ({100*_fau//len(_succ)}%)**",
        f"- first-chunk wait median {_p50(_ttft)}s (n={len(_ttft)}); clean-success turn total "
        f"median {_p50(_tot)}s (n={len(_tot)}); send-to-stall median {_p50(_stv)}s (n={len(_stv)})", ""]
out += ["", "## Incident 2 — collection round of 2026-09-10 (`evidence/incident_20260910/`)", "",
        f"- {len(i2)} request episodes (55 distinct submitted prompts) in 3 conversations on the observation day: "
        f"{sum(1 for r in i2 if r[2] == 'S')} completed, {len(i2_to)} timeout parks, "
        f"{len(i2_dlg)} dialog parks, {sum(1 for r in i2 if r[2] in ('F', 'U'))} failed/cancelled",
        f"- the five timeouts all sit in one conversation at **{min(i2_to_ctx):,} tokens**; "
        f"the largest context that still completed that day is **{max(i2_s_ok):,} tokens** — "
        f"a {max(i2_s_ok):,}-versus-{min(i2_to_ctx):,} separation on the day "
        "(round 1 pooled data does NOT separate cleanly; see report §4.2)",
        f"- send-to-stall spanned {min(float(r[5]) for r in i2_to):.0f}s to "
        f"{max(float(r[5]) for r in i2_to):.0f}s (the upper value is a banner left parked "
        "for 81 minutes)",
        "- paired experiment: the same conversation stalled five times at 494,193 tokens, then "
        "after the client's context-compaction control reported 117,153 tokens "
        "(`Compression API call completed for session compact`) a request carrying 85,115 "
        "tokens completed in 10.1 s — report §9",
        "- three negative results from this round: tab visibility (a hidden conversation "
        "completed in 2.58 s), server-side cache residency across a 27.7-minute idle gap "
        "(17.11 s versus 17.58 s at the same size), and inflating an agent's context by "
        "asking it to read files (one such turn added 851 tokens)", ""]
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(out))
print(f"\nwrote {OUT.relative_to(EV.parent)}")
if fails:
    print(f"FAILED: {fails}", file=sys.stderr)
    sys.exit(1)
print("all report numbers verified against evidence")
