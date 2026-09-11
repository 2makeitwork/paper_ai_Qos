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

Two deliberate tolerances, both narrow and both reported out loud:

  * `analysis/summary_tables.md` is generated, and its footer carries a content hash plus
    a second-precision timestamp. When the hashes differ, the hashes *inside* the two
    files are compared: equal means the same statistics built at different moments, and
    the line says so instead of crying drift.
  * the served text is scanned for internal instructions ("paste this file", pointers to
    files that are deliberately not published). Fixing a document locally is not the same
    as fixing what the hub hands out, and the hub's history keeps every earlier revision.

Usage:
    python3 scripts/check_release_sync.py                      # working tree vs the hub
    python3 scripts/check_release_sync.py --ref v0.3.0-pre     # a tagged tree vs the hub
    ZENODO_TOKEN=… python3 scripts/check_release_sync.py --zenodo-draft 22699009
    python3 scripts/check_release_sync.py --zenodo 1234567     # a published record, no token

Exit code 0 = the manifests agree and the served text is clean; 1 = drift, a text finding,
or a location that could not be reached. The manifest is the data layer: `evidence/`,
`analysis/`, the scripts that make its claims checkable, and the documents and licence
notices listed in PAYLOAD below.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HF_REPO = "2makeitwork/paper_ai_Qos"
# Files that make up the published data layer, relative to its root. The card is
# DATASET_CARD.md in the source tree and README.md once published.
PAYLOAD = ["README.md", "methodology.md", "anonymization.md", "LICENSE", "LICENSE-code.md",
           "LICENSE-content.md", "CITATION.cff", "scripts/analyze.py",
           "scripts/verify_dataset_card.py", "scripts/check_release_sync.py"]
PAYLOAD_DIRS = ["evidence", "analysis"]
CARD_SOURCE = "DATASET_CARD.md"
STAMPED = {"analysis/summary_tables.md"}
STAMP_RE = re.compile(r"sha256:([0-9a-f]{64})")
# Phrasing that is a defect wherever it appears: instructions to whoever maintains the
# repository, shipped inside a document a reader downloads.
ALWAYS_BAD = ("Paste this file", "How to publish", "how to publish")
# Names of files that stay on the author's workstation. Naming one is acceptable only on a
# line that says so, which is what the source repository's own document table does.
PRIVATE_NAMES = ("PUBLICATION.md", "prior-works.md", "methodology_guidance")
DISCLOSED_WORDS = ("not published", "not part of", "deliberately", "private", "ignored",
                   "working notes", "kept local", "no reading obligation", "local-only")


class Manifest:
    """Relative path -> ((md5, size), stamp token), plus where it came from."""

    def __init__(self, base: Path | None = None):
        self.base = base
        self.entries: dict[str, tuple[tuple[str, int], str | None]] = {}
        self.tokens: dict[str, str] = {}

    def add(self, rel: str, blob: bytes) -> None:
        self.entries[rel] = ((hashlib.md5(blob).hexdigest(), len(blob)), None)
        found = STAMP_RE.search(blob.decode("utf-8", errors="replace"))
        if found and rel in STAMPED:
            self.entries[rel] = (self.entries[rel][0], found.group(0))

    def scan(self, base: Path) -> "Manifest":
        for name in PAYLOAD:
            src = base / (CARD_SOURCE if name == "README.md" and (base / CARD_SOURCE).exists()
                          else name)
            if not src.exists():
                continue
            if src.name == CARD_SOURCE:
                self.add(name, published_card(src).encode())
            else:
                self.add(name, src.read_bytes())
        for d in PAYLOAD_DIRS:
            for p in sorted((base / d).rglob("*")) if (base / d).is_dir() else []:
                if p.is_file():
                    self.add(p.relative_to(base).as_posix(), p.read_bytes())
        return self


def published_card(src: Path) -> str:
    """The card as it is published: front matter kept, internal instruction lines dropped."""
    lines = src.read_text().splitlines()
    keep, i = [lines[0]], 1
    while i < len(lines) and not lines[i].startswith("#"):
        keep.append(lines[i]); i += 1
    while i < len(lines) and (lines[i].startswith("#") or not lines[i].strip()):
        i += 1
    return "\n".join(keep + lines[i:]) + "\n"


def reference_manifest(ref: str | None) -> Manifest:
    if not ref:
        return Manifest(ROOT).scan(ROOT)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "-C", str(ROOT), "worktree", "add", "--detach", tmp, ref],
                       check=True, capture_output=True)
        try:
            return Manifest(Path(tmp)).scan(Path(tmp))
        finally:
            subprocess.run(["git", "-C", str(ROOT), "worktree", "remove", "--force", tmp],
                           check=False, capture_output=True)


def scan_text(base: Path, tracked: set[str] | None = None) -> list[str]:
    """What a reader actually receives: internal instructions must not be in it.

    `tracked` limits the scan to files the published set contains; without it the walk would
    read the author's own unpublished notes sitting beside the repository and report them as
    if they had been served.
    """
    problems = []
    for p in sorted(base.rglob("*.md")):
        rel = p.relative_to(base).as_posix()
        if ".cache" in p.parts or ".git" in p.parts:
            continue
        if tracked is not None and rel not in tracked:
            continue
        for n, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
            for marker in ALWAYS_BAD:
                if marker in line:
                    problems.append(f"{rel}:{n} serves internal marker {marker!r}")
            named = [x for x in PRIVATE_NAMES if x in line]
            if named and not any(w in line.lower() for w in DISCLOSED_WORDS):
                problems.append(f"{rel}:{n} names {named[0]} without saying it is unpublished")
    return problems


def hf_download(dest: Path) -> None:
    hf = os.path.expanduser("~/.local/bin/hf")
    cmd = [hf if os.path.exists(hf) else "hf", "download", HF_REPO, "--type", "dataset",
           "--local-dir", str(dest), "--quiet"]
    subprocess.run(cmd, check=True, capture_output=True, timeout=600,
                   env={**os.environ, "ALL_PROXY": "", "all_proxy": ""})


def zenodo_listing(recid: str, draft: bool) -> dict[str, dict]:
    url = (f"https://zenodo.org/api/records/{recid}/draft/files" if draft
           else f"https://zenodo.org/api/records/{recid}/files?size=200")
    tok = os.environ.get("ZENODO_TOKEN", "")
    if draft and not tok:
        raise RuntimeError("--zenodo-draft needs ZENODO_TOKEN (a published record does not)")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"} if tok else {})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.load(r)
    entries = data.get("entries") or data.get("hits", {}).get("hits") or []
    out = {}
    for e in entries:
        key = (e.get("key") or e.get("filename") or "").split("/", 1)[-1]
        out[key] = e
    return out


def zenodo_fetch(recid: str, key: str, draft: bool) -> bytes:
    tok = os.environ.get("ZENODO_TOKEN", "")
    quoted = urllib.parse.quote(f"{PREFIX}/{key}" if draft else key, safe="")
    url = (f"https://zenodo.org/api/records/{recid}/draft/files/{quoted}/content" if draft
           else f"https://zenodo.org/api/records/{recid}/files/{quoted}/content?download=1")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"} if tok else {})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def zenodo_token(recid: str, key: str, draft: bool) -> str | None:
    """The content hash recorded inside a generated file, read back over the wire."""
    try:
        found = STAMP_RE.search(zenodo_fetch(recid, key, draft).decode("utf-8", errors="replace"))
    except (OSError, urllib.error.URLError):
        return None
    return found.group(0) if found else None


PREFIX = "ai-qos-case-study-1"


def compare(title: str, want: Manifest, have: Manifest, fetch=None) -> list[str]:
    findings, notes = [], []
    for rel in sorted(set(want.entries) | set(have.entries)):
        a, b = want.entries.get(rel), have.entries.get(rel)
        if a is None:
            findings.append(f"{rel}: present in {title}, absent from the reference")
            continue
        if b is None:
            findings.append(f"{rel}: in the reference, missing from {title}")
            continue
        if a[0] == b[0]:
            continue
        token_want = a[1]
        token_have = b[1] or (fetch(rel) if fetch and rel in STAMPED else None)
        if token_want and token_have and token_want == token_have:
            notes.append(f"{rel}: identical content, different generation stamp "
                         f"({token_want[:18]}…)")
        else:
            findings.append(f"{rel}: differs (reference {a[0][1]} bytes, {title} {b[0][1]} bytes)")
    same = len(set(want.entries) & set(have.entries)) - len(findings)
    print(f"{title}: {len(have.entries)} files compared, {same} agree, "
          f"{len(notes)} stamped, {len(findings)} findings")
    for line in notes:
        print("    note:", line)
    for line in findings:
        print("    ", line)
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ref", help="git revision to treat as the reference (default: working tree)")
    ap.add_argument("--no-hf", action="store_true", help="skip the Hugging Face dataset repository")
    ap.add_argument("--skip-text", action="store_true", help="do not scan the served text")
    ap.add_argument("--zenodo", help="published Zenodo record id to compare against")
    ap.add_argument("--zenodo-draft", help="Zenodo draft record id (needs ZENODO_TOKEN)")
    args = ap.parse_args()

    want = reference_manifest(args.ref)
    print(f"reference: {args.ref or 'working tree'} — {len(want.entries)} data-layer files")
    problems: list[str] = []

    if not args.no_hf:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                hf_download(Path(tmp))
            except (OSError, subprocess.SubprocessError) as exc:
                problems.append(f"huggingface: could not be downloaded: {exc}")
                print(f"huggingface: unreachable ({exc})")
            else:
                base = Path(tmp)
                problems += ["huggingface: " + p for p in
                             compare("huggingface", want, Manifest(base).scan(base))]
                if not args.skip_text:
                    text = ["huggingface: " + p for p in scan_text(base)]
                    print(f"huggingface text scan: {len(text)} finding(s)")
                    problems += text

    for label, recid, draft in (("zenodo", args.zenodo, False),
                                ("zenodo-draft", args.zenodo_draft, True)):
        if not recid:
            continue
        try:
            listing = zenodo_listing(recid, draft)
            have = Manifest()
            for key, entry in listing.items():
                digest = (entry.get("checksum") or "").replace("md5:", "")
                have.entries[key] = ((digest, int(entry.get("size") or 0)), None)
            problems += [f"{label}: " + p for p in compare(
                label, want, have,
                fetch=lambda rel, r=recid, d=draft: zenodo_token(r, rel, d))]
        except (OSError, urllib.error.URLError, RuntimeError, KeyError,
                subprocess.SubprocessError) as exc:
            problems.append(f"{label} unreachable: {exc}")
            print(f"{label}: unreachable ({exc})")
    if not args.zenodo and not args.zenodo_draft:
        print("zenodo: not compared (pass --zenodo <record id>, or --zenodo-draft <id> with a token)")

    if not args.skip_text and not args.ref:
        try:
            run = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True,
                                 text=True, timeout=60)
            tracked = {line for line in run.stdout.splitlines() if line.endswith(".md")} \
                if run.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            tracked = None
        local_text = scan_text(ROOT, tracked)
        scope = f"{len(tracked)} tracked documents" if tracked else "every markdown file present"
        print(f"working tree text scan ({scope}): {len(local_text)} finding(s)")
        problems += ["reference: " + p for p in local_text]
    print("\nIN SYNC" if not problems else f"\nDRIFT OR TEXT FINDINGS: {len(problems)} finding(s)")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
