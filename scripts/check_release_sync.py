#!/usr/bin/env python3
"""check_release_sync.py — is the published data layer the same bytes in every place?

This project ships the same evidence bundle to three locations that update independently:

  * the source repository on GitHub (the canonical tree, checked out or committed),
  * the Hugging Face dataset repository (`2makeitwork/paper_ai_Qos`),
  * a Zenodo record, either a published record id or a draft id (a draft needs a token).

None of them knows about the others. A file edited in the source tree stays stale
everywhere else until someone re-uploads it, and a Zenodo record can never be deleted
once published — so drift is the normal state, and the only honest response is to
measure it rather than assert it away.

Usage:
    python3 scripts/check_release_sync.py                     # working tree vs hub
    python3 scripts/check_release_sync.py --ref v0.3.0-pre    # a tagged tree vs hub
    ZENODO_TOKEN=… python3 scripts/check_release_sync.py --zenodo-draft 22699009

Exit code 0 = the manifests agree; 1 = drift, or a location could not be reached.
The manifest is the set of files the data layer is defined to contain: `evidence/`,
`analysis/`, the scripts that make its claims checkable, and the documents and
licence notices listed in PAYLOAD below.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HF_REPO = "2makeitwork/paper_ai_Qos"
# Files that make up the published data layer, relative to its root. `README.md` is the
# dataset card: DATASET_CARD.md in the source tree, README.md in the published copy.
PAYLOAD = ["README.md", "methodology.md", "anonymization.md", "LICENSE", "LICENSE-code.md",
           "LICENSE-content.md", "CITATION.cff", "scripts/analyze.py",
           "scripts/verify_dataset_card.py", "scripts/check_release_sync.py"]
PAYLOAD_DIRS = ["evidence", "analysis"]
CARD_SOURCE = "DATASET_CARD.md"


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def local_manifest(ref: str | None) -> dict[str, tuple[str, int]]:
    """{relative path: (md5, size)} for the working tree, or for a git revision."""
    out: dict[str, tuple[str, int]] = {}
    if ref:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "-C", str(ROOT), "worktree", "add", "--detach", tmp, ref],
                           check=True, capture_output=True)
            try:
                return local_manifest_from(Path(tmp))
            finally:
                subprocess.run(["git", "-C", str(ROOT), "worktree", "remove", "--force", tmp],
                               check=False, capture_output=True)
    return local_manifest_from(ROOT)


def local_manifest_from(base: Path) -> dict[str, tuple[str, int]]:
    out: dict[str, tuple[str, int]] = {}
    for name in PAYLOAD:
        # The card is DATASET_CARD.md in the source tree and README.md once published, so the
        # substitution applies only where the source form exists; elsewhere README.md is the card.
        if name == CARD_SOURCE:
            continue
        src = base / (CARD_SOURCE if name == "README.md" and (base / CARD_SOURCE).exists()
                      else name)
        if not src.exists():
            continue
        if name == "README.md" and src.name == CARD_SOURCE:
            # the published card is this file with the internal instruction lines dropped
            lines = src.read_text().splitlines()
            keep, i = [lines[0]], 1
            while i < len(lines) and not lines[i].startswith("#"):
                keep.append(lines[i]); i += 1
            while i < len(lines) and (lines[i].startswith("#") or not lines[i].strip()):
                i += 1
            body = "\n".join(keep + lines[i:]) + "\n"
            out[name] = (hashlib.md5(body.encode()).hexdigest(), len(body.encode()))
            continue
        out[name] = (md5(src), src.stat().st_size)
    for d in PAYLOAD_DIRS:
        for p in sorted((base / d).rglob("*")) if (base / d).is_dir() else []:
            if p.is_file():
                out[str(p.relative_to(base))] = (md5(p), p.stat().st_size)
    return out


def hf_manifest() -> dict[str, tuple[str, int]]:
    """Download the published dataset repository and hash what the hub serves."""
    with tempfile.TemporaryDirectory() as tmp:
        for cmd in ([os.path.expanduser("~/.local/bin/hf"), "download", HF_REPO,
                     "--type", "dataset", "--local-dir", tmp, "--quiet"],
                    ["hf", "download", HF_REPO, "--type", "dataset",
                     "--local-dir", tmp, "--quiet"]):
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=300,
                               env={**os.environ, "ALL_PROXY": "", "all_proxy": ""})
                break
            except (FileNotFoundError, subprocess.SubprocessError):
                continue
        else:
            raise RuntimeError("the hf CLI is unavailable and no download succeeded")
        base = Path(tmp)
        if (base / ".cache").is_dir():
            subprocess.run(["rm", "-rf", str(base / ".cache")], check=False)
        return local_manifest_from(base)


def zenodo_manifest(recid: str, draft: bool) -> dict[str, tuple[str, int]]:
    """Hashes Zenodo already computed: its file listing carries md5 for every key."""
    url = (f"https://zenodo.org/api/records/{recid}/draft/files" if draft
           else f"https://zenodo.org/api/records/{recid}/files?size=100")
    tok = os.environ.get("ZENODO_TOKEN", "")
    if draft and not tok:
        raise RuntimeError("--zenodo-draft needs ZENODO_TOKEN (a published record does not)")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"} if tok else {})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    entries = data.get("entries") or data.get("hits", {}).get("hits") or []
    out = {}
    for e in entries:
        key = e.get("key") or e.get("filename") or ""
        key = key.split("/", 1)[1] if key.startswith("ai-qos-case-study-1/") else key
        digest = (e.get("checksum") or "").replace("md5:", "")
        out[key] = (digest, int(e.get("size") or 0))
    return out


def report(title: str, want: dict, have: dict) -> list[str]:
    diffs = []
    for key in sorted(set(want) | set(have)):
        a, b = want.get(key), have.get(key)
        if a is None:
            diffs.append(f"{key}: in {title}, not in the reference")
        elif b is None:
            diffs.append(f"{key}: in the reference, missing from {title}")
        elif a[0] != b[0]:
            diffs.append(f"{key}: differs (reference {a[1]} bytes, {title} {b[1]} bytes)")
    same = len(set(want) & set(have)) - sum(1 for d in diffs if "differs" in d)
    print(f"{title}: {len(have)} files listed, {same} matching, {len(diffs)} findings")
    for d in diffs:
        print("   ", d)
    return diffs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ref", help="git revision to treat as the reference (default: working tree)")
    ap.add_argument("--no-hf", action="store_true", help="skip the Hugging Face dataset repository")
    ap.add_argument("--zenodo", help="published Zenodo record id to compare against")
    ap.add_argument("--zenodo-draft", help="Zenodo draft record id (needs ZENODO_TOKEN)")
    args = ap.parse_args()

    want = local_manifest(args.ref)
    print(f"reference: {args.ref or 'working tree'} — {len(want)} data-layer files")
    problems: list[str] = []
    if not args.no_hf:
        try:
            problems += [f"huggingface: {d}" for d in report("huggingface", want, hf_manifest())]
        except Exception as exc:                                  # noqa: BLE001
            problems.append(f"huggingface unreachable: {exc}")
    for label, recid, draft in (("zenodo", args.zenodo, False),
                                ("zenodo-draft", args.zenodo_draft, True)):
        if not recid:
            continue
        try:
            problems += [f"{label}: {d}" for d in report(label, want, zenodo_manifest(recid, draft))]
        except Exception as exc:                                  # noqa: BLE001
            problems.append(f"{label} unreachable: {exc}")
    if not args.zenodo and not args.zenodo_draft:
        print("zenodo: not compared (pass --zenodo <record id>, or --zenodo-draft <id> with a token)")
    print("\nIN SYNC" if not problems else f"\nDRIFT: {len(problems)} finding(s)")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
