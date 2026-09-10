#!/usr/bin/env bash
# collect_evidence.sh — dump the raw (pre-anonymization) evidence from a
# Qoder CN installation on this machine into ./raw_local/.
#
# Read-only against the sources; all writes stay under ./raw_local/, which is
# gitignored. Run ./anonymize.py afterwards to produce the publishable
# evidence tree. Requires: bash, grep (GNU), python3.
#
# Sources (standard per-user locations for this product):
#   ~/.config/QoderCN/logs/**                     runtime logs (retention-limited)
#   ~/.config/QoderCN/User/error-code-cache.json  fetched error-code dictionary
#   ~/.config/QoderCN/User/globalStorage/state.vscdb   IDE state DB (SQLite)
#   ~/.qoder-cn/cache/projects/*/conversation-history/ chat transcript JSONL
set -u
LOGS="${LOGSRC:-$HOME/.config/QoderCN/logs}"
#   LOGSRC lets the step below run against a frozen copy (logs_mirror/mirror/)
#   instead of the live tree, so the published extracts stay pinned to the
#   study window even after the installation keeps logging.
EV="$(cd "$(dirname "$0")" && pwd)/raw_local"
GROWTH_SID="${GROWTH_SID:-}"   # short session id whose growth curve to export; default: largest
mkdir -p "$EV"/{logs,config,session_stats}

echo "[1/10] timeout (80408 resume-button) lines"
grep -rhE '"title":"resume"' "$LOGS" --include='*.log' 2>/dev/null \
  > "$EV/logs/timeouts_resume_lines_raw.txt"
grep -rh 'Creating tool_call for permission request' "$LOGS" --include='*.log' 2>/dev/null \
  | grep '"title":"resume"' | grep -v '"command"' \
  | sed -E 's/^([0-9-]+ [0-9:.]+) .*"toolCallId":"([^"]+)".*"reasonForCode":([0-9]+).*/\1,\2,\3/' \
  | sort -u | { echo "timestamp,toolCallId,reasonForCode"; cat; } > "$EV/logs/timeouts_resume_events.csv"

echo "[2/10] quota/account failure-marker lines + chat_finish census"
grep -rhE 'ACP session/prompt failed|State transition:[[:space:]]*streaming -> error|Handling request error for session' \
  "$LOGS" --include='*.log' 2>/dev/null | grep -v '"command"' > "$EV/logs/quota_error_lines_raw.txt"
grep -rhoE 'chat_finish:.{0,110}' "$LOGS" --include='*.log' 2>/dev/null \
  | cut -c1-110 | sort | uniq -c | sort -rn > "$EV/logs/chat_finish_payload_summary.txt"

echo "[3/10] error-code dictionary extract (timeout/quota/access entries)"
python3 - "$EV/config" <<'PY'
import json, re, sys
from pathlib import Path
src = Path.home()/".config"/"QoderCN"/"User"/"error-code-cache.json"
d = json.loads(src.read_text())
keep = {"version": d["version"], "fetchTime": d["fetchTime"], "publishTime": d["publishTime"],
        "source": str(src), "entries": {}}
pat = re.compile(r"resume|timeout|timed out|quota|exceeded|access denied|too long|context", re.I)
for lang, m in d["content"].items():
    for k, v in m.items():
        if pat.search(str(v)):
            keep["entries"].setdefault(lang, {})[k] = v
out = Path(sys.argv[1])/"error-code-cache_relevant_entries.json"
out.write_text(json.dumps(keep, indent=1, ensure_ascii=False))
PY

echo "[4/10] model registry line + BYOK definitions + selected context presets"
grep -rh '"name":"qmodel_38max"' "$LOGS" --include='*.log' 2>/dev/null | grep -v '"command"' \
  | sort | tail -1 > "$EV/config/model_registry_qmodel_38max_line_latest.txt"
python3 - "$EV/config" <<'PY'
import sqlite3, json, sys
from pathlib import Path
out = Path(sys.argv[1])
con = sqlite3.connect(Path.home()/".config"/"QoderCN"/"User"/"globalStorage"/"state.vscdb")
cm = json.loads(con.execute("SELECT value FROM ItemTable WHERE key='aicoding.customModels'").fetchone()[0])
for m in cm: m.pop("apiKey", None)   # keys are never persisted to the dump
(out/"custom_models_bailian.json").write_text(json.dumps(cm, indent=1, ensure_ascii=False))
rows = con.execute("SELECT key,value FROM ItemTable WHERE key LIKE 'aicoding.modelSelector.runtimeConfig.%'").fetchall()
(out/"runtime_model_selection.txt").write_text("\n".join(f"{k} = {v}" for k, v in sorted(rows)) + "\n")
PY

echo "[5/10] session size statistics + context growth curve"
python3 - "$EV/session_stats" "$GROWTH_SID" <<'PY'
import json, sys
from pathlib import Path
out, want = Path(sys.argv[1]), sys.argv[2]
rows, per = [], {}
for f in sorted(Path.home().glob(".qoder-cn/cache/projects/*/conversation-history/*/*.jsonl")):
    entries = [json.loads(l) for l in f.read_text(errors="replace").splitlines() if l.strip()]
    chars = sum(len(json.dumps(e.get("message", ""))) for e in entries)
    rows.append((f.parents[2].name, f.parent.name, f.stat().st_size, len(entries), chars))
    per[f.parent.name] = (f, entries)
rows.sort(key=lambda r: r[1])
(out/"session_size_stats.csv").write_text("project_cache,session,jsonl_bytes,entries,cum_message_chars\n"
    + "\n".join(",".join(map(str, r)) for r in rows) + "\n")
sid = want or max(rows, key=lambda r: r[4])[1]
f, entries = per[sid]
cum, growth = 0, []
for i, e in enumerate(entries, 1):
    cum += len(json.dumps(e.get("message", "")))
    growth.append(f"{i},{e.get('role','?')},{cum}")
(out/f"context_growth_{sid}.csv").write_text("entry_index,role,cumulative_message_chars\n" + "\n".join(growth) + "\n")
PY

echo "[6/10] prompt history (IDE state DB: titles + real timestamps)"
python3 - "$EV" <<'PY'
import sqlite3, json, sys
from pathlib import Path
from datetime import datetime, timezone
out = Path(sys.argv[1])
con = sqlite3.connect(Path.home()/".config"/"QoderCN"/"User"/"globalStorage"/"state.vscdb")
seen, lines = set(), ["timestamp,session,title"]
for (v,) in con.execute("SELECT value FROM ItemTable WHERE key LIKE 'lingma.chat.localHistory.%'"):
    for e in json.loads(v):
        dt = datetime.fromtimestamp(e["timestamp"]/1000, tz=timezone.utc).astimezone()
        row = (f"{dt:%Y-%m-%d %H:%M:%S %Z}", e.get("sessionId", "?")[:8],
               e.get("title", "").replace("\n", " "))
        if row not in seen:
            seen.add(row)
            lines.append('"%s","%s","%s"' % row)
(out/"prompt_history.csv").write_text(
    lines[0] + "\n" + "\n".join(sorted(lines[1:], key=lambda l: l[1:])) + "\n")
PY

echo "[7/10] merged timeline"
{ tail -n +2 "$EV/logs/timeouts_resume_events.csv" | sed 's/$/,timeout_80408_resume_button/' | cut -d, -f1,4
  grep -oE '^[0-9-]+ [0-9:]+' "$EV/logs/quota_error_lines_raw.txt" | sort -u | sed 's/$/,quota_account_error/'; } \
  | { echo "timestamp,event"; sort -t, -k1; } > "$EV/timeline_events.csv"

echo "[8/10] environment"
{ grep -hoE '"(nameShort|nameLong|version|commit)"[^,]*' \
    /usr/share/qoder-cn-ide/resources/app/product.json 2>/dev/null | head -8
  uname -srv; } > "$EV/config/environment.txt"

echo "[9/10] task lifecycle lines (quest.log — one master-mode task per conversation)"
python3 - "$LOGS" "$EV" <<'PY'
import re, sys
from pathlib import Path
logs, ev = Path(sys.argv[1]), Path(sys.argv[2])
# keep only conversations that also have a transcript-stats row, so this extract
# stays inside the same universe as the rest of the published evidence (and so no
# new pseudonym is introduced into the frozen map)
sids = {ln.split(",")[1] for ln in (ev / "session_stats/session_size_stats.csv")
        .read_text().splitlines()[1:]}
ts_re = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})")
line_re = re.compile(r'task\.status\.update(?:\.skipNonQuestTask)? \{'
                     r'"taskId":"([0-9a-f-]{36})","status":"[A-Za-z]+"')
rows = []
for f in sorted(p for p in logs.rglob("*") if p.is_file() and "quest.log" in p.name):
    win = next((p for p in f.parts if re.fullmatch(r"window\d+", p)), None) \
        or (re.search(r"__(window\d+)__", f.name) or [None, "?"])[1]
    for ln in f.read_text(errors="replace").splitlines():
        if '"command"' in ln or "grep -r" in ln or "python3 - <<" in ln:
            continue
        m, t = line_re.search(ln), ts_re.match(ln)
        if not (m and t) or m.group(1)[:8] not in sids:
            continue
        rows.append((t.group(1), f"[{win}] {ln.rstrip()}"))
rows.sort()
out = ev / "logs/task_status_lines_raw.txt"
out.write_text("\n".join([
    "# source: ~/.config/QoderCN/logs/**/quest.log (or that tree's logs_mirror/",
    "#   mirror, when re-collecting after the study window), window-labelled",
    "# anchor: task.status.update {\"taskId\":\"<conversation uuid>\",\"status\":\"...\"}",
    "# note: one event is written by EVERY open IDE window's quest.log (<=0.7 s skew),",
    "#   so de-duplicate by (session, status) within 2 s before any interval math;",
    "#   the .skipNonQuestTask twin marks the conversation as not a Quest-mode task",
    "# filter: task ids without a session_stats/session_size_stats.csv row dropped",
    *(r[1] for r in rows)]) + "\n")
print(f"  wrote logs/task_status_lines_raw.txt ({len(rows)} lines)")
PY

echo "[10/10] per-interaction phase transitions (the client's own state machine)"
python3 - "$LOGS" "$EV" <<'PY'
import os, re, sys
from pathlib import Path
logs, ev = Path(sys.argv[1]), Path(sys.argv[2])
# KEEP_ALL=1 skips the conversation filter (local dumps of a live installation,
# including conversations the published bundle must not introduce: an unknown
# uuid would shift every later pseudonym in anonymize.py's first-appearance map)
keep_all = bool(os.environ.get("KEEP_ALL"))
sids = {ln.split(",")[1] for ln in (ev / "session_stats/session_size_stats.csv")
        .read_text().splitlines()[1:]}
ts_re = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3})")
line_re = re.compile(r"\[ACPProgressStateMachine\] State transition: \w+ -> \w+, "
                     r"trigger: .+, sessionId: ([0-9a-f-]{36})")
rows = []
logname = re.compile(r"agent(\.\d+)?\.log(\.i\d+)?$")     # live and mirror naming
for f in sorted(p for p in logs.rglob("*") if p.is_file() and logname.search(p.name)):
    win = next((p for p in f.parts if re.fullmatch(r"window\d+", p)), None) \
        or (re.search(r"__(window\d+)__", f.name) or [None, "?"])[1]
    for ln in f.read_text(errors="replace").splitlines():
        if '"command"' in ln or "grep -r" in ln or "python3 - <<" in ln:
            continue
        m, t = line_re.search(ln), ts_re.match(ln)
        if not (m and t) or (not keep_all and m.group(1)[:8] not in sids):
            continue
        rows.append((t.group(1), f"[{win}] {ln.rstrip()}"))
rows.sort()
out = ev / "logs/phase_transitions_raw.txt"
out.write_text("\n".join([
    "# source: ~/.config/QoderCN/logs/**/windowN/agent.log, window-labelled",
    "# anchor: [ACPProgressStateMachine] State transition: A -> B, trigger: T, sessionId: S",
    "# reading: user_message_chunk = send pressed; agent_thought_chunk = first streamed",
    "#   chunk (the UI's 'Thinking…'); permission_request = tool approval dialog;",
    "#   resume_tool_call = the 80408 timeout banner; user_resume = Continue clicked;",
    "#   chat_finish:<code> = turn over.  A -> B ends interval A and starts B.",
    "# filter: conversations without a session_stats/session_size_stats.csv row dropped",
    "#   (KEEP_ALL=1 keeps them for a local-only dump)",
    *(r[1] for r in rows)]) + "\n")
print(f"  wrote logs/phase_transitions_raw.txt ({len(rows)} lines)")
PY
echo "done: $EV — now run: python3 anonymize.py --input raw_local --output ../evidence"
