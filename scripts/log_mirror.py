#!/usr/bin/env python3
"""log_mirror.py — tamper-evident local mirror of the Qoder CN runtime logs.

Why this exists
---------------
The IDE rotates each window's log at 5 MiB and keeps only ONE backup generation
(`agent.log` -> `agent.1.log`; the *next* rotation overwrites the old
`agent.1.log`). That means the 08:48-14:51 timeout "storm" evidence is destroyed
on window3's next rotation. This service copies the live log tree into this repo
on a fixed interval, captures every file the moment it rotates out, and --
because a log file must be append-only -- re-hashes every already-committed
region on each scan so an in-place rewrite of history is DETECTED, not trusted.

Stdlib only. Read-only against the sources; all writes stay under
`<repo>/logs_mirror/` (gitignored, carries local paths/ids like the raw dump).

Usage
-----
    python3 scripts/log_mirror.py scan                # daemon: scan every 180s
    python3 scripts/log_mirror.py scan --once         # single pass (cron/timer)
    python3 scripts/log_mirror.py scan --interval 60
    python3 scripts/log_mirror.py verify              # re-hash committed regions, list alerts
    python3 scripts/log_mirror.py status              # tracked/finalized/alert summary
    python3 scripts/log_mirror.py snapshot            # full timestamped tree copy + SHA256SUMS

Integrity model
---------------
* A *stream* is one (path, dev, inode). Its mirror file lives under
  `logs_mirror/mirror/` named per-(path,inode) and is append-only, so a
  rotation that renames or recreates a path can never clobber a generation we
  already captured.
* `state.json` holds, per stream, the committed byte length and the SHA-256 of
  that committed region. `ledger.jsonl` is a hash-chained, append-only record of
  every capture / rotation-out / alert event. Committing `ledger.jsonl` to git
  turns it into an externally-timestamped, tamper-evident log the operator
  cannot silently rewrite either.
* Alert kinds written to `alerts.log` + ledger:
    APPEND_ONLY_VIOLATION  committed bytes of a live stream changed in place
    ROTATION_MISMATCH      source vs mirror disagree as a file rotates out
    VANISHED_UNFINALIZED   a tracked live stream's path disappeared
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = Path.home() / ".config" / "QoderCN" / "logs"
MIRROR_ROOT = REPO / "logs_mirror"
MIRROR_DIR = MIRROR_ROOT / "mirror"
STATE_FILE = MIRROR_ROOT / "state.json"
LEDGER_FILE = MIRROR_ROOT / "ledger.jsonl"
ALERTS_FILE = MIRROR_ROOT / "alerts.log"
SNAP_DIR = REPO / "raw_snapshots"
DEFAULT_INTERVAL = 180  # 3 minutes, per spec


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def sha256_range(path: Path, start: int, length: int) -> str:
    """SHA-256 of bytes [start, start+length) of `path`, read in chunks."""
    h = hashlib.sha256()
    remaining = length
    with path.open("rb") as f:
        f.seek(start)
        while remaining > 0:
            block = f.read(min(1 << 20, remaining))
            if not block:
                break
            h.update(block)
            remaining -= len(block)
    return h.hexdigest()


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"streams": {}, "head": None, "seq": 0, "alerts": 0}


def save_state(state: dict) -> None:
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True))
    tmp.replace(STATE_FILE)


def ledger_append(state: dict, event: str, detail: dict) -> None:
    """Append a hash-chained record to the ledger (chained on prior head)."""
    state["seq"] = int(state.get("seq", 0)) + 1
    rec = {
        "seq": state["seq"],
        "ts": now_iso(),
        "event": event,
        "prev": state.get("head"),
        **detail,
    }
    body = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    rec["sha256"] = hashlib.sha256(body.encode()).hexdigest()
    state["head"] = rec["sha256"]
    with LEDGER_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")


def alert(state: dict, kind: str, detail: dict) -> None:
    state["alerts"] = int(state.get("alerts", 0)) + 1
    line = f"[{now_iso()}] {kind} {json.dumps(detail, sort_keys=True)}"
    with ALERTS_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    ledger_append(state, "ALERT", {"kind": kind, **detail})
    print(f"  !! ALERT {kind}: {detail}", file=sys.stderr)


def rel_of(path: Path) -> str:
    return str(path.relative_to(SOURCE))


def mirror_name_for(relpath: str, inode: int) -> Path:
    safe = relpath.replace("/", "__")
    return MIRROR_DIR / f"{safe}.i{inode}"


def discover() -> list[Path]:
    if not SOURCE.exists():
        print(f"source missing: {SOURCE}", file=sys.stderr)
        return []
    return sorted(p for p in SOURCE.rglob("*.log") if p.is_file())


def commit_stream(state: dict, skey: str, rec: dict, src: Path, target_len: int) -> None:
    """Append src bytes [rec['offset'], target_len) to the mirror; update hashes."""
    mpath = Path(rec["mirror"])
    start = int(rec["offset"])
    if target_len < start:
        target_len = start
    delta_len = target_len - start
    written = 0
    with src.open("rb") as fin, mpath.open("ab") as fout:
        fin.seek(start)
        left = delta_len
        while left > 0:
            block = fin.read(min(1 << 20, left))
            if not block:
                break  # short read: file shrank under us; commit what we got
            fout.write(block)
            written += len(block)
            left -= len(block)
    rec["offset"] = start + written
    rec["size"] = int(src.stat().st_size)
    delta_sha = sha256_range(mpath, start, written) if written > 0 else ""
    rec["committed_sha"] = sha256_range(mpath, 0, int(rec["offset"]))
    rec["chunks"].append({"start": start, "end": int(rec["offset"]), "sha256": delta_sha})
    rec["last_seen"] = now_iso()
    if written > 0:
        ledger_append(
            state,
            "CAPTURE",
            {"path": rec["path"], "inode": rec["inode"], "bytes": written,
             "committed_sha": rec["committed_sha"]},
        )


def open_stream(state: dict, src: Path, st: os.stat_result) -> dict:
    rel = rel_of(src)
    skey = f"{rel}|{st.st_dev}|{st.st_ino}"
    MIRROR_DIR.mkdir(parents=True, exist_ok=True)
    mpath = mirror_name_for(rel, st.st_ino)
    if mpath.exists():
        mpath.unlink()  # fresh inode -> fresh mirror
    rec = {
        "path": rel, "dev": st.st_dev, "inode": st.st_ino,
        "mirror": str(mpath), "offset": 0, "size": 0,
        "committed_sha": "", "chunks": [],
        "first_seen": now_iso(), "last_seen": now_iso(), "finalized": False,
    }
    state["streams"][skey] = rec
    ledger_append(state, "OPEN", {"path": rel, "inode": st.st_ino})
    return rec


def finalize(state: dict, rec: dict, reason: str) -> None:
    if rec.get("finalized"):
        return
    rec["finalized"] = True
    rec["finalized_ts"] = now_iso()
    ledger_append(state, "ROTATE_OUT" if "rotat" in reason else "FINALIZE",
                  {"path": rec["path"], "inode": rec["inode"], "reason": reason,
                   "mirror": rec["mirror"], "final_bytes": int(rec["offset"]),
                   "final_sha256": rec["committed_sha"]})


def scan_once(state: dict) -> None:
    seen = set()
    for src in discover():
        try:
            st = src.stat()
        except OSError as exc:
            alert(state, "VANISHED_UNFINALIZED", {"path": rel_of(src), "err": str(exc)})
            continue
        rel = rel_of(src)
        skey = f"{rel}|{st.st_dev}|{st.st_ino}"
        seen.add(skey)
        rec = state["streams"].get(skey)

        if rec is None:
            # New (path,inode): either a brand-new log or a rotated-in file.
            # Before mirroring, close any OTHER live stream at the same path whose
            # inode changed -> that is the file that just rotated out.
            for k, other in state["streams"].items():
                if other["path"] == rel and not other["finalized"] and k != skey:
                    # cross-check source vs mirror as it rotates out, if still readable
                    if Path(other["mirror"]).exists():
                        committed = int(other["offset"])
                        try:
                            src_sha = sha256_range(src, 0, committed) if src.stat().st_ino == other["inode"] else other["committed_sha"]
                        except OSError:
                            src_sha = other["committed_sha"]
                        if src.stat().st_ino == other["inode"] and src_sha != other["committed_sha"]:
                            alert(state, "ROTATION_MISMATCH",
                                  {"path": rel, "inode": other["inode"],
                                   "mirror": other["mirror"]})
                    finalize(state, other, "rotated-out (inode replaced)")
            rec = open_stream(state, src, st)

        elif not rec["finalized"]:
            if st.st_ino != rec["inode"] or st.st_size < int(rec["offset"]):
                finalize(state, rec, "truncated/recreated")
                rec = open_stream(state, src, st)
            else:
                # APPEND-ONLY CHECK: re-hash the committed region from source.
                committed = int(rec["offset"])
                if committed > 0:
                    src_committed_sha = sha256_range(src, 0, committed)
                    if src_committed_sha != rec["committed_sha"]:
                        alert(state, "APPEND_ONLY_VIOLATION",
                              {"path": rel, "inode": rec["inode"],
                               "region": [0, committed],
                               "expected": rec["committed_sha"],
                               "found": src_committed_sha})
                        rec["committed_sha"] = src_committed_sha  # adopt & keep watching

        if rec is not None and not rec["finalized"] and st.st_size > int(rec["offset"]):
            commit_stream(state, skey, rec, src, st.st_size)

    # Any live stream whose path is no longer present -> it rotated/deleted away.
    present_paths = {rel_of(p) for p in discover()}
    for rec in state["streams"].values():
        if not rec["finalized"] and rec["path"] not in present_paths:
            finalize(state, rec, "path vanished (rotated out / deleted)")

    save_state(state)


def cmd_scan(args: argparse.Namespace) -> int:
    MIRROR_ROOT.mkdir(parents=True, exist_ok=True)
    state = load_state()
    interval = args.interval
    if args.once:
        scan_once(state)
        print(f"[{now_iso()}] single scan done (streams={len(state['streams'])}, "
              f"alerts={state.get('alerts', 0)})")
        return 0
    print(f"[{now_iso()}] mirroring {SOURCE} -> {MIRROR_ROOT} every {interval}s (Ctrl-C to stop)")
    try:
        while True:
            scan_once(state)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nstopped.")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    state = load_state()
    problems = 0
    for rec in sorted(state["streams"].values(), key=lambda r: (r["path"], r["inode"])):
        mpath = Path(rec["mirror"])
        committed = int(rec["offset"])
        if committed == 0:
            continue
        # (a) our mirror copy still matches what we recorded
        mirror_ok = mpath.exists() and sha256_range(mpath, 0, committed) == rec["committed_sha"]
        # (b) for live streams, the source's committed region still matches (append-only)
        src_ok = True
        src = SOURCE / rec["path"]
        if not rec["finalized"] and src.exists() and src.stat().st_ino == rec["inode"]:
            src_ok = sha256_range(src, 0, committed) == rec["committed_sha"]
        status = "OK" if (mirror_ok and src_ok) else "MISMATCH"
        if status != "OK":
            problems += 1
        print(f"  {status:8} {rec['path']} i{rec['inode']} "
              f"{'(finalized)' if rec['finalized'] else '(live)'} "
              f"bytes={committed} mirror_ok={mirror_ok} src_ok={src_ok}")
    print(f"verify: {len(state['streams'])} streams, {problems} problem(s). "
          f"See {ALERTS_FILE} for the alert history.")
    return 1 if problems else 0


def cmd_status(args: argparse.Namespace) -> int:
    state = load_state()
    live = [r for r in state["streams"].values() if not r["finalized"]]
    fin = [r for r in state["streams"].values() if r["finalized"]]
    total = sum(int(r["offset"]) for r in state["streams"].values())
    print(f"source      : {SOURCE}")
    print(f"mirror root : {MIRROR_ROOT}")
    print(f"streams     : {len(state['streams'])} total ({len(live)} live, {len(fin)} finalized)")
    print(f"mirrored    : {total/1e6:.2f} MB captured")
    print(f"ledger head : seq={state.get('seq', 0)} alerts={state.get('alerts', 0)}")
    if ALERTS_FILE.exists():
        print(f"last alerts :\n" + "".join("  " + l for l in ALERTS_FILE.read_text().splitlines(True)[-5:]))
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    ts = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")
    dest = SNAP_DIR / ts
    dest.mkdir(parents=True, exist_ok=True)
    manifest = dest / "SHA256SUMS"
    n = 0
    with manifest.open("w", encoding="utf-8") as mf:
        for src in discover():
            st = src.stat()
            out = dest / "logs" / rel_of(src)
            out.parent.mkdir(parents=True, exist_ok=True)
            with src.open("rb") as fin, out.open("wb") as fout:
                sha = hashlib.sha256()
                for block in iter(lambda: fin.read(1 << 20), b""):
                    fout.write(block)
                    sha.update(block)
            mf.write(f"{sha.hexdigest()}  {st.st_size}  ./{rel_of(src)}\n")
            n += 1
    state = load_state()
    ledger_append(state, "SNAPSHOT", {"dir": str(dest.relative_to(REPO)), "files": n})
    save_state(state)
    print(f"[{now_iso()}] snapshot: {dest} ({n} files, manifest SHA256SUMS)")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Tamper-evident mirror of the Qoder CN runtime logs.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sc = sub.add_parser("scan", help="mirror the log tree on an interval")
    sc.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help="seconds between scans (default 180)")
    sc.add_argument("--once", action="store_true", help="do a single scan and exit (for cron/systemd timer)")
    sc.set_defaults(func=cmd_scan)
    sub.add_parser("verify", help="re-hash committed regions; report append-only violations").set_defaults(func=cmd_verify)
    sub.add_parser("status", help="show mirror/status summary").set_defaults(func=cmd_status)
    sub.add_parser("snapshot", help="write a full timestamped tree copy + SHA256SUMS").set_defaults(func=cmd_snapshot)
    args = ap.parse_args(argv[1:])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
