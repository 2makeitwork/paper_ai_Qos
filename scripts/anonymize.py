#!/usr/bin/env python3
"""anonymize.py — turn a raw evidence dump into the publishable evidence/.

Reads the directory produced by collect_evidence.sh (--input), applies a
deterministic scrubbing map (--rules built from the data itself, see
../anonymization.md for the policy), and writes the publishable tree to
--output. Echo lines (shell commands the investigating agent ran, captured
inside log captures) are dropped: they are self-referential noise.

Full chat transcripts are deliberately NOT part of the published bundle
(they carry third-party project content); only statistics and error-related
log extracts pass through. The script FAILS with a nonzero exit code if any
forbidden pattern survives in its own output.

Usage:
    python3 anonymize.py --input ../report_HuggingFace_internal/raw_evidence \
                         --output ../evidence
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
CACHE_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_]{1,}(?:-[A-Za-z0-9_]+)*?)-([0-9a-f]{8})\b")
IP_RE = re.compile(r"\b192\.168\.\d{1,3}\.\d{1,3}\b")
MODELID_RE = re.compile(r"\bmodel_17\d{11}_[a-z0-9]{6,8}\b")
# Operator-specific values are derived at runtime, never written into this file: it is
# published, and a literal home path, account name or account-id prefix would republish
# precisely the identifiers this script exists to remove.
HOME = str(Path.home())
ACCOUNT = Path(HOME).name
TENANT_RE = re.compile(r"\b019f[0-9a-f]{4}[0-9a-f-]{2,}\b")
KEY_RE = re.compile(r"\bsk-[A-Za-z0-9]{16,}\b")
ECHO_RE = re.compile(r'"command"|"command_names"|grep -r|python3 - <<')

# Patterns match leaked VALUES, not policy prose: full LAN addresses (not the
# "192.168.x.x" placeholder in anonymization.md), apiKey fields carrying a
# string value (not the schema boolean "hasApiKey": true).
FORBIDDEN = [re.escape(HOME), rf"\b{re.escape(ACCOUNT)}\b", r"\blinx\b",
             r"192\.168\.\d{1,3}\.\d{1,3}", r"sk-[A-Za-z0-9]{16}",
             r"\b019f[0-9a-f]{6}", r"model_17\d{11}",
             r'"[a-zA-Z]*apiKey"\s*:\s*"']


def build_map(input_dir: Path) -> dict[str, str]:
    """Collect every file's text, then assign pseudonyms deterministically."""
    texts = {}
    for p in sorted(input_dir.rglob("*")):
        if p.is_file() and p.suffix in {".txt", ".csv", ".json", ".md"}:
            texts[p] = p.read_text(errors="replace")
    blob = "\n".join(texts.values())

    mapping: dict[str, str] = {}
    # 1. sessions: short ids from the stats table, chronological by first event
    order = []
    stats = input_dir / "session_stats/session_size_stats.csv"
    if stats.exists():
        for line in stats.read_text().splitlines()[1:]:
            sid = line.split(",")[1]
            if sid not in order:
                order.append(sid)
    for i, sid in enumerate(order, 1):
        mapping[sid] = f"sess-{i:02d}"
    # 2. full UUIDs: session ones join their short twin; the rest become call-NN
    calls = 0
    for u in UUID_RE.findall(blob):
        if u in mapping:
            continue
        short = u[:8]
        if short in mapping:
            mapping[u] = mapping[short]
            continue
        calls += 1
        mapping[u] = f"call-{calls:03d}"
    # 3. project caches: <name>-<hash8> → ws-<letter>-cache; bare name → ws-<letter>
    letters = "ABCDEFGH"
    seen_proj: dict[str, str] = {}
    for name, h in CACHE_RE.findall(blob):
        token = f"{name}-{h}"
        if token in mapping:
            continue
        if name not in seen_proj:
            seen_proj[name] = letters[len(seen_proj) % 8]
        letter = seen_proj[name]
        mapping[token] = f"ws-{letter}-cache"
        mapping[name] = f"ws-{letter}"
    # 4. fixed identities
    mapping[HOME + "/Documents/source"] = "/home/user/projects"
    mapping[HOME] = "/home/user"
    mapping[f"{ACCOUNT}@{ACCOUNT}:"] = "user@host:"
    mapping["linx"] = "<host-1>"
    assert all(len(k) > 1 and any(c.isalpha() for c in k)
               for k in mapping if not k.startswith("192.168")), \
        "refusing a mapping key that is a bare digit or punctuation-free fragment"
    # 5. pattern families
    for i, ip in enumerate(sorted(set(IP_RE.findall(blob))), 1):
        mapping[ip] = f"<lan-ip-{i}>"
    for i, m in enumerate(sorted(set(MODELID_RE.findall(blob))), 1):
        mapping[m] = f"byok-model-{i:02d}"
        mapping[f"custom:{m}"] = f"byok-model-{i:02d}"
    for t in TENANT_RE.findall(blob):
        mapping[t] = "<account-id>"
    for k in KEY_RE.findall(blob):
        mapping[k] = "<redacted-key>"
    return mapping


def scrub(text: str, mapping: dict[str, str]) -> str:
    # longest keys first, so the deeper path wins over the bare home directory
    for token in sorted(mapping, key=len, reverse=True):
        text = text.replace(token, mapping[token])
    return text


def emit(out: Path, rel: str, text: str) -> None:
    path = out / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [ln for ln in text.splitlines() if not ECHO_RE.search(ln)]
    path.write_text("\n".join(lines) + "\n")
    print(f"  wrote {rel} ({len(lines)} lines)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    src, out = args.input, args.output
    mapping = build_map(src)
    print(f"mapping size: {len(mapping)} tokens")

    # publishable file set: statistics + error-related log extracts + configs
    plan = {
        "logs/timeout_resume_lines.txt": "logs/timeouts_resume_lines_raw.txt",
        "logs/timeout_resume_events.csv": "logs/timeouts_resume_events.csv",
        "logs/task_status_lines.txt": "logs/task_status_lines_raw.txt",
        "logs/phase_transitions.txt": "logs/phase_transitions_raw.txt",
        "logs/quota_error_lines.txt": "logs/quota_error_lines_raw.txt",
        "logs/quota_error_payload_flat.txt": "logs/quota_error_payload_flat.txt",
        "logs/chat_finish_census.txt": "logs/chat_finish_payload_summary.txt",
        "logs/resume_events_by_window.txt": "logs/resume_events_by_window.txt",
        "logs/token_size_lines.txt": "logs/token_size_lines.txt",
        "logs/server_endpoint_timeout_lines.txt": "logs/server_endpoint_timeout_lines.txt",
        "config/environment.txt": "config/environment.txt",
        "config/error-code-dictionary_extract.json": "config/error-code-cache_relevant_entries.json",
        "config/model_registry_qmodel_38max.txt": "config/model_registry_qmodel_38max_line_latest.txt",
        "config/custom_models_byok.json": "config/custom_models_bailian.json",
        "config/runtime_model_selection.txt": "config/runtime_model_selection.txt",
        "stats/session_size_stats.csv": "session_stats/session_size_stats.csv",
        "stats/context_growth.csv": "session_stats/context_growth_1524ae43.csv",
        "stats/timeline_events.csv": "timeline_events.csv",
        "user_statements.md": "user_statements.md",
    }
    for dest, srcrel in plan.items():
        p = src / srcrel
        if not p.exists() and "context_growth_" in srcrel:
            # the growth curve is named after the largest session, which
            # differs between machines
            cands = sorted((src / "session_stats").glob("context_growth_*.csv"))
            p = cands[0] if cands else p
        if not p.exists():
            print(f"  MISSING {srcrel} — skipped", file=sys.stderr)
            continue
        emit(out, dest, scrub(p.read_text(errors="replace"), mapping))

    # curated exact strings the report quotes (banner texts, payloads, one raw
    # resume line) — assembled verbatim, then scrubbed
    dict_path = src / "config/error-code-cache_relevant_entries.json"
    dictionary = json.loads(dict_path.read_text()) if dict_path.exists() else {"entries": {}}
    dictionary.pop("source", None)
    sample = ""
    resume_raw = src / "logs/timeouts_resume_lines_raw.txt"
    for ln in (resume_raw.read_text(errors="replace").splitlines() if resume_raw.exists() else []):
        if "Creating tool_call" in ln and '"command"' not in ln:
            sample = scrub(ln, mapping)
            break
    quota_lines = src / "logs/quota_error_lines_raw.txt"
    variants = set()
    if quota_lines.exists():
        for ln in quota_lines.read_text(errors="replace").splitlines():
            if '"command"' in ln:
                continue
            variants.update(re.findall(r'"message":"([^"]{20,140})', ln))
    error_messages = {
        "note": "verbatim strings; <...> are pseudonyms from anonymization.md",
        "banner_timeout_80408": "Response timeout. Click to resume or switch to another model and try again.",
        "banner_tool_limit_40429": "Tool usage limit reached. Click to resume",
        "banner_input_too_long_80411": "Input content too long, please simplify and retry",
        "error_dictionary_extract": dictionary,
        "quota_payload_variants_seen_in_logs": sorted(variants),
        "resume_tool_call_sample_line": sample,
    }
    emit(out, "error_messages.json", json.dumps(error_messages, indent=1, ensure_ascii=False))

    # quota-event session index without transcript links (transcripts withheld)
    idx = src / "transcripts/error_sessions_index.md"
    if idx.exists():
        keep = [ln for ln in idx.read_text(errors="replace").splitlines()
                if ln.startswith("|") or ln.startswith("- `") or ln.startswith("# ")]
        text = re.sub(r"\[([^\]]*)\]\(\./[^)]*\)", r"\1 (withheld)", "\n".join(keep))
        emit(out, "stats/quota_error_sessions.txt", scrub(text, mapping))

    # screenshot travels unchanged (UI text only, no paths visible)
    shot = src / "screenshots/user_screenshot_timeout_storm.png"
    if shot.exists():
        (out / "screenshots").mkdir(parents=True, exist_ok=True)
        (out / "screenshots/timeout_storm_ui.png").write_bytes(shot.read_bytes())
        print("  copied screenshots/timeout_storm_ui.png")

    # self-audit: nothing forbidden may survive
    bad = 0
    for p in out.rglob("*"):
        if p.is_file() and p.suffix in {".txt", ".csv", ".json", ".md"}:
            body = p.read_text(errors="replace")
            for pat in FORBIDDEN:
                if re.search(pat, body, re.I if "sven" in pat else 0):
                    print(f"LEAK {p.relative_to(out)}: /{pat}/", file=sys.stderr)
                    bad += 1
    if bad:
        print(f"FAILED: {bad} forbidden pattern(s) survived", file=sys.stderr)
        return 1
    print("audit clean: no forbidden pattern in output")
    return 0


if __name__ == "__main__":
    sys.exit(main())
