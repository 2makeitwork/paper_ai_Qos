#!/usr/bin/env python3
"""build_data_layer.py — stage exactly the published data layer, and nothing else.

The manifest is imported from `check_release_sync.py`, so the set of files this script
stages, the set the sync checker compares and the set that is actually published are the
same list defined once.

This exists because an ad-hoc staging command once crashed half way through - after the
upload had already run - and put six files that belong to the source repository into the
public dataset repository. A builder that refuses to produce a partial payload is the
structural fix for a mistake that a checklist would not have caught:

    python3 scripts/build_data_layer.py --out dist/dataset            # from the working tree
    python3 scripts/build_data_layer.py --ref v0.3.0-pre.2 --out dist # from a tag
    python3 scripts/build_data_layer.py --list                        # just the manifest

Then, and only then:

    hf upload 2makeitwork/paper_ai_Qos dist/dataset . --type dataset --commit-message "…"
"""
from __future__ import annotations

import argparse
import io
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_release_sync import (CARD_SOURCE, PAYLOAD, PAYLOAD_DIRS, ROOT,
                                published_card)  # noqa: E402


def source_tree(ref: str | None, dest: Path) -> Path:
    """The files to stage: a tag or revision extracted from git, or the working tree."""
    if ref is None:
        return ROOT
    dest.mkdir(parents=True, exist_ok=True)
    run = subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar", ref],
                         capture_output=True, timeout=300)
    if run.returncode != 0:
        raise SystemExit(f"git archive {ref!r} failed: {run.stderr.decode(errors='replace')[:200]}")
    with tarfile.open(fileobj=io.BytesIO(run.stdout)) as tar:
        safe = [m for m in tar.getmembers() if not (m.name.startswith("/") or ".." in m.name)]
        tar.extractall(dest, members=safe, filter="data")   # no absolute paths, no mode surprises
    return dest


def stage(src: Path, out: Path) -> list[str]:
    missing = []
    for name in PAYLOAD:
        card = name == "README.md" and (src / CARD_SOURCE).exists()
        if not (src / (CARD_SOURCE if card else name)).exists():
            missing.append(name)
    for d in PAYLOAD_DIRS:
        if not (src / d).is_dir():
            missing.append(d + "/")
    if missing:
        raise SystemExit(f"REFUSED: the source tree is missing {missing} - staging a partial "
                         f"payload is how the published set drifts")
    out.mkdir(parents=True, exist_ok=True)
    for name in PAYLOAD:
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if name == "README.md" and (src / CARD_SOURCE).exists():
            target.write_text(published_card(src / CARD_SOURCE))
        else:
            shutil.copy(src / name, target)
    for d in PAYLOAD_DIRS:
        if (out / d).exists():
            shutil.rmtree(out / d)
        shutil.copytree(src / d, out / d)
    return sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ref", help="git revision to stage (default: the working tree)")
    ap.add_argument("--out", default="dist/dataset", help="directory to stage into")
    ap.add_argument("--list", action="store_true", help="print the manifest and exit")
    args = ap.parse_args()

    if args.list:
        print("\n".join(PAYLOAD + [d + "/*" for d in PAYLOAD_DIRS]))
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        src = source_tree(args.ref, Path(tmp) / "src")
        out = Path(args.out).resolve()
        # A staging directory is disposable, so it must be somewhere disposable: outside the
        # repository, or under tmp/ or dist/. Anything else could be a tracked path, and wiping
        # a working tree to build a copy of it is not a mistake worth being able to make.
        disposable = out != ROOT and (not out.is_relative_to(ROOT)
                                      or out.relative_to(ROOT).parts[0] in ("tmp", "dist"))
        if not disposable:
            raise SystemExit(f"REFUSED: {out} is inside the repository but not under tmp/ or "
                             f"dist/; stage the payload somewhere disposable")
        shutil.rmtree(out, ignore_errors=True)
        files = stage(src, out)
    total = sum((out / f).stat().st_size for f in files)
    print(f"staged {len(files)} files, {total:,} bytes into {out}"
          + (f" from {args.ref}" if args.ref else " from the working tree"))
    unexpected = [f for f in files if not (f in PAYLOAD or f.startswith(tuple(PAYLOAD_DIRS)))
                  and f != ".gitattributes"]
    if unexpected:
        raise SystemExit(f"REFUSED: staged files outside the manifest: {unexpected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
