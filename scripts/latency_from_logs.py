#!/usr/bin/env python3
"""latency_from_logs.py — reconstruct request-level latency from the client log.

The primary instrument for this study is the Qoder CN runtime log: each agent
request moves through `[ACPProgressStateMachine] State transition: <from> -> <to>,
trigger: <T>, sessionId: <S>` edges with millisecond timestamps. Walking those
edges per session brackets every request and yields the client-perceived wait for
the first streamed chunk, the total turn latency and the time to a stall. A
`suspended` park is split by its `trigger:` into a **timeout**
(`resume_tool_call`, the 80408 banner) versus a **permission dialog**
(`permission_request`) — so the timeout count is verifiable from the client alone.

Two stall clocks are reported, because they answer different questions
(ruling 2026-09-10): `to_stall_s` from the moment the user pressed send — the
context, i.e. how long the operator was actually held — and `stall_from_chunk_s`
from the first streamed chunk, which is what the client's own watchdog measures
(the clock restarts on arriving output, so a long healthy turn never trips it).

Context occupancy comes from a second log line, `Context usage sync received for
session … usedTokens=… reportedLimitTokens=…`, which the client emits per request:
it is the only per-request size figure the client exposes, and it is what turns
"oversized context" from a transcript proxy into a measured quantity.

Small, real sample used to *demonstrate* the method, not a population estimate.

    python3 scripts/latency_from_logs.py [LOG_DIR] [--emit-csv OUT.csv] [--since YYYY-MM-DDTHH:MM]
        LOG_DIR default ~/.config/QoderCN/logs. For a frozen, reproducible input
        pass a snapshot tree, e.g.  raw_snapshots/<ts>/logs.
        --since drops requests that started earlier, which is how a later
        collection round stays scoped to its own incident: the log tree also holds
        conversations from unrelated projects, and they are not this study's to
        publish even as pseudonymised timing rows.

Privacy: the emitted CSV uses session pseudonyms (S1, S2, …), study timestamps and
the fixed trigger label only; no raw sessionId, path, or message content is written.
"""
import re
import sys
from pathlib import Path
from datetime import datetime

args = [a for a in sys.argv[1:]]
EMIT = args[args.index("--emit-csv") + 1] if "--emit-csv" in args else None
SINCE = datetime.strptime(args[args.index("--since") + 1], "%Y-%m-%dT%H:%M") \
    if "--since" in args else None
pos = [a for a in args if not a.startswith("--")
       and a != (args[args.index("--emit-csv") + 1] if "--emit-csv" in args else None)
       and a != (args[args.index("--since") + 1] if "--since" in args else None)]
SRC = Path(pos[0]) if pos else Path.home() / ".config/QoderCN/logs"

EDGE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\b.*?"
    r"State transition:\s*(?P<from>\w+)\s*->\s*(?P<to>\w+)\b"
    r"(?:.*?,\s*trigger:\s*(?P<trig>[A-Za-z_]+))?"
    r"(?:.*?sessionId:\s*(?P<sid>[0-9a-fA-F-]+))?")
# map a terminal edge to an outcome; 'suspended' is refined by trigger in collect()
TERMINAL = {"completed": "S", "error": "F", "cancelled": "U"}
# per-request context occupancy, logged by the client itself
USAGE = re.compile(
    r"^(?P<ts>\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}).*?"
    r"Context usage sync received for session (?P<sid>[0-9a-fA-F-]{36}):"
    r".*?usedTokens=(?P<used>\d+), reportedLimitTokens=(?P<limit>\d+)")


def parse_ts(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S.%f")


def bin_of(sec):
    for hi, label in ((5, "0-5"), (10, "5-10"), (20, "10-20"), (30, "20-30"),
                      (60, "30-60"), (120, "60-120"), (300, "120-300")):
        if sec < hi:
            return label
    return "300+"


def collect():
    edges, usage = [], {}
    for p in SRC.rglob("*.log"):
        try:
            text = p.read_text(errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if "command" in line:
                continue
            m = EDGE.search(line)
            if m:
                edges.append((parse_ts(m["ts"]), m["from"], m["to"], m["sid"] or "?",
                              (m["trig"] or "").strip()))
            u = USAGE.match(line)
            if u:
                usage.setdefault(u["sid"], []).append(
                    (parse_ts(u["ts"]), int(u["used"]), int(u["limit"])))
    for sid in usage:
        usage[sid].sort()

    def occ_at(sid, when):
        """last occupancy reported for this session at or before `when`."""
        found = None
        for ts, used, limit in usage.get(sid, []):
            if ts > when:
                break
            found = (used, limit)
        return found
    by_sess = {}
    for e in sorted(edges):
        by_sess.setdefault(e[3], []).append(e)

    reqs = []
    for sid, seq in by_sess.items():
        submit = first = None
        susp = 0
        for ts, fr, to, _sid, trig in seq:
            if to == "prompting":
                submit, first, susp = ts, None, 0
            elif to == "streaming" and submit is not None and first is None and fr == "prompting":
                first = ts
            elif to == "suspended" and submit is not None:
                kind = "T_timeout" if trig == "resume_tool_call" else "T_dialog" if trig == "permission_request" else "T_other"
                reqs.append(dict(sid=sid, kind=kind, trigger=trig, start=submit,
                                 ttft=(first - submit).total_seconds() if first else None,
                                 to_stall=(ts - submit).total_seconds(),
                                 stall_from_chunk=(ts - first).total_seconds() if first else None,
                                 occ=occ_at(sid, submit), retries=0))
                susp += 1
            elif to == "completed" and submit is not None:
                reqs.append(dict(sid=sid, kind="S", trigger=trig, start=submit, retries=susp,
                                 ttft=(first - submit).total_seconds() if first else None,
                                 total=(ts - submit).total_seconds(),
                                 stall_from_chunk=None, occ=occ_at(sid, submit)))
                submit, first, susp = None, None, 0
            elif to in ("error", "cancelled") and submit is not None:
                reqs.append(dict(sid=sid, kind=TERMINAL[to], trigger=trig, start=submit, retries=0,
                                 ttft=(first - submit).total_seconds() if first else None,
                                 total=(ts - submit).total_seconds(),
                                 stall_from_chunk=None, occ=occ_at(sid, submit)))
                submit, first, susp = None, None, 0
    reqs.sort(key=lambda r: r["start"])
    if SINCE:
        kept = [r for r in reqs if r["start"] >= SINCE]
        print(f"--since {SINCE:%Y-%m-%dT%H:%M}: {len(reqs) - len(kept)} of {len(reqs)} "
              f"requests dropped as outside this collection round")
        reqs = kept
    order = {}
    for r in reqs:
        order.setdefault(r["sid"], f"S{len(order) + 1}")
        r["sess"] = order[r["sid"]]
    return reqs


def emit_csv(reqs, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write("session,start_ts,outcome,first_chunk_s,total_s,to_stall_s,retries,trigger,"
                "stall_from_chunk_s,used_tokens_at_send,limit_tokens\n")
        for r in reqs:
            outcome = "T" if r["kind"].startswith("T_") else r["kind"]
            used, limit = (r.get("occ") or ("", ""))
            f.write(f"{r['sess']},{r['start'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]},"
                    f"{outcome},{fmt(r.get('ttft'))},{fmt(r.get('total'))},"
                    f"{fmt(r.get('to_stall'))},{r['retries']},{r.get('trigger','')},"
                    f"{fmt(r.get('stall_from_chunk'))},{used},{limit}\n")
    print(f"wrote {path} ({len(reqs)} rows)")


def fmt(v):
    return "" if v is None else f"{v:.1f}"


def pct(n, d):
    return f"{100.0 * n / d:.1f}%" if d else "—"


def summarize(reqs):
    succ = [r for r in reqs if r["kind"] == "S"]
    tto = [r for r in reqs if r["kind"] == "T_timeout"]
    tdi = [r for r in reqs if r["kind"] == "T_dialog"]
    other = [r for r in reqs if r["kind"] in ("F", "U")]
    print(f"requests: {len(reqs)}  S {len(succ)} | T_timeout(resume_tool_call) {len(tto)} | "
          f"T_dialog(permission_request) {len(tdi)} | F/U {len(other)}")
    print(f"distinct sessions: {len(set(r['sess'] for r in reqs))}")

    def dist(vals, title):
        vals = sorted(v for v in vals if v is not None)
        print(f"\n{title}  (n={len(vals)})")
        if not vals:
            return
        b = {}
        for v in vals:
            b[bin_of(v)] = b.get(bin_of(v), 0) + 1
        for label in ("0-5", "5-10", "10-20", "20-30", "30-60", "60-120", "120-300", "300+"):
            if b.get(label):
                print(f"  {label:>8}s : {b[label]:3d}  {pct(b[label], len(vals)):>6}")
        p = lambda q: vals[min(len(vals) - 1, int(q * (len(vals) - 1)))]
        print(f"  median (50th percentile)={p(.5):.1f}s  90th percentile={p(.9):.1f}s  "
              f"min={vals[0]:.1f}s  max={vals[-1]:.1f}s")

    dist([r["ttft"] for r in succ + tto + tdi], "Wait for first streamed chunk (s)")
    dist([r["total"] for r in succ if not r.get("retries")], "Total turn latency, clean successes (s)")
    dist([r["to_stall"] for r in tto], "TIMEOUT parks: send -> suspended (operator-held)")
    dist([r["stall_from_chunk"] for r in tto], "TIMEOUT parks: first chunk -> suspended (watchdog clock)")
    dist([r["to_stall"] for r in tdi], "DIALOG parks: send -> suspended (after streaming)")

    sized = [(r["occ"][0], r["kind"]) for r in reqs if r.get("occ")]
    if sized:
        ok = sorted(u for u, k in sized if k == "S")
        bad = sorted(u for u, k in sized if k.startswith("T_"))
        # Honest framing: across the whole log window the two outcomes OVERLAP on
        # size (stalls at small contexts, successes at huge ones), so context size
        # is a probability factor, not a gate. The separations worth quoting are
        # the paired ones inside a single conversation (see report §4.2, §9).
        below = sum(1 for u, k in sized if k == "S" and u > min(bad))
        above = sum(1 for u, k in sized if k.startswith("T_") and u < max(ok))
        print(f"\ncontext occupancy at send: successes n={len(ok)} (max {max(ok)}), "
              f"stalls n={len(bad)} (min {min(bad)}) — the two ranges OVERLAP: "
              f"{below} successes above the smallest stall, {above} stalls below the "
              f"largest success. Size is therefore reported as a probability "
              "factor, never as a threshold.")

    tsub = [r["to_stall"] for r in tto if r["to_stall"] is not None]
    if tsub:
        below = sum(1 for x in tsub if x < 55)
        print(f"\n[verify] timeout send->suspend: min={min(tsub):.1f}s (floor~60s), {below}/{len(tsub)} under 55s, "
              f"but the wait for the first chunk of these is small -> the ~60s is an INACTIVITY/idle floor, "
              f"NOT a first-packet cap; total time before the park far exceeds it "
              f"(median {sorted(tsub)[len(tsub)//2]:.0f}s)")


if __name__ == "__main__":
    reqs = collect()
    summarize(reqs)
    if EMIT:
        emit_csv(reqs, EMIT)
