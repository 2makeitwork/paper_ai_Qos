#!/usr/bin/env python3
"""verify_dataset_card.py — check that DATASET_CARD.md describes the bundle truthfully.

The card is the public interface of the dataset: it declares which files load as
which configs and states how many rows each holds. A card that lies is worse than
no card, so every claim it makes in machine-readable form is checked here:

  1. the YAML front matter parses (PyYAML if installed, minimal fallback otherwise);
  2. every `configs[].data_files[].path` exists in this repository;
  3. every declared file is a well-formed comma-separated table with a non-empty
     header, consistent field counts, and one split (train);
  4. every row count stated in the card body equals the count measured here;
  5. the sections the Hugging Face dataset-card evaluation looks for are present;
  6. the license is declared under a key the hub actually reads, and agrees with
     `CITATION.cff` and the root `LICENSE` notice (this repository is dual-licensed
     by path: Creative Commons Attribution 4.0 for text and data, MIT for `scripts/`);
  7. the card carries no internal instruction text — no "paste this file" note, no
     pointer to a file that is deliberately not published (both once shipped, in the
     YAML comment block, where the hub renders nothing but the raw file shows all);
  8. every `python3 <script>` command inside a fenced block names a script that exists
     in whichever repository the card is published into, or the block says the command
     belongs to the other one — an instruction a reader cannot run is a defect in the
     publication, not in the reader.

Exit code 0 = all eight hold. Run it before `hf upload`.

    python3 scripts/verify_dataset_card.py
"""
from __future__ import annotations

import csv
import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _tracked() -> set[str] | None:
    """The paths git tracks in this checkout, or None when it is not a repository."""
    try:
        run = subprocess.run(["git", "-C", str(ROOT), "ls-files"],
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return set(run.stdout.split()) if run.returncode == 0 else None


GIT_TRACKED = _tracked()
# The card is DATASET_CARD.md in the source repository and README.md once it is
# published into the dataset repository; either is accepted.
CARD = next((p for p in (ROOT / "DATASET_CARD.md", ROOT / "README.md") if p.exists()),
             ROOT / "DATASET_CARD.md")

REQUIRED_SECTIONS = ["## Dataset details", "### Composition", "### Collection process",
                     "## Personal and private content", "## Uses", "## Limitations",
                     "## Citation", "## License"]
fails: list[str] = []


def front_matter(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        fails.append("card has no YAML front matter block")
        return ""
    return m.group(1)


def parse_configs(yaml_text: str) -> list[tuple[str, str, str]]:
    """Return [(config_name, split, path)]; PyYAML when available, else regex."""
    out: list[tuple[str, str, str]] = []
    try:
        import yaml  # type: ignore
        doc = yaml.safe_load(yaml_text) or {}
        for cfg in doc.get("configs") or []:
            for df in cfg.get("data_files") or []:
                out.append((cfg["config_name"], df.get("split", "?"), df["path"]))
        return out
    except ImportError:
        cur = "?"
        for line in yaml_text.splitlines():
            if (m := re.match(r"\s*-\s*config_name:\s*(\S+)", line)):
                cur = m.group(1)
            elif (m := re.match(r"\s*path:\s*(\S+)", line)):
                out.append((cur, "train", m.group(1)))
        if not out:
            fails.append("no configs declared in the front matter")
        return out


def declared_licenses(yaml_text: str) -> list[str]:
    """Values of the `license` key, in list or scalar form, comments stripped."""
    block = re.search(r"^license:\n((?:[ \t]+-[^\n]*\n?)+)", yaml_text, re.M)
    if block:
        return [line.strip().lstrip("-").strip().split("#")[0].strip()
                for line in block.group(1).splitlines()]
    scalar = re.search(r"^license:[ \t]+(\S+)", yaml_text, re.M)
    return [scalar.group(1)] if scalar else []


def check_licenses(yaml_text: str) -> None:
    for wrong in ("licenses:", "cfg_types:"):
        if re.search(rf"^{wrong}", yaml_text, re.M):
            fails.append(f"front matter key `{wrong[:-1]}` is not read by the hub — the "
                         f"documented key is `license` (it accepts a list)")
    declared = declared_licenses(yaml_text)
    if "cc-by-4.0" not in declared:
        fails.append(f"front matter declares license(s) {declared}; the data is CC-BY-4.0")
    cff = (ROOT / "CITATION.cff").read_text() if (ROOT / "CITATION.cff").exists() else ""
    if "CC-BY-4.0" not in cff or "MIT" not in cff:
        fails.append("CITATION.cff no longer states both halves of the license split")
    root_license = (ROOT / "LICENSE").read_text() if (ROOT / "LICENSE").exists() else ""
    if "dual-licensed by path" not in root_license:
        fails.append("root LICENSE does not state which paths are MIT and which are CC-BY-4.0")


INTERNAL_MARKERS = ("Paste this file", "How to publish", "how to publish",
                    "PUBLICATION.md", "prior-works.md", "reposition.md", "methodology_guidance")
# A fenced command is an instruction the reader will try. Every script it names must be
# present in whichever repository this card is published into, or the line has to say who it
# belongs to - which is how the tools/ gate and the paste-in note escaped into the open.
CMD_RE = re.compile(r"^\s*python3\s+([A-Za-z0-9_./-]+\.py)")


def check_no_internal_instructions(text: str) -> list[str]:
    hits = []
    for marker in INTERNAL_MARKERS:
        for n, line in enumerate(text.splitlines(), 1):
            if marker in line:
                hits.append(f"line {n}: internal instruction marker {marker!r} in the published card")
    return hits


def tracked_or_present(rel: str) -> bool:
    """Does this path belong to the *published* set?

    Testing the disk is not enough - `tools/` sits on this workstation and is deliberately
    never published, which is precisely how an unrunnable instruction survived review. Where
    the checkout is a git repository, ask git what is tracked; otherwise (the published data
    layer has no git) fall back to file presence.
    """
    if GIT_TRACKED is not None:
        return rel in GIT_TRACKED
    return (ROOT / rel).exists()


def check_commands_run(text: str) -> list[str]:
    blocks, inside, buf = [], False, []
    for line in text.splitlines():
        if line.startswith("```"):
            if inside:
                blocks.append(buf)
            inside, buf = not inside, []
            continue
        if inside:
            buf.append(line)
    problems = []
    for block in blocks:
        for line in block:
            m = CMD_RE.match(line)
            if not m:
                continue
            target = m.group(1)
            if not tracked_or_present(target) and "not published" not in "\n".join(block):
                problems.append(f"command names {m.group(1)!r}, which is not in this repository "
                                f"and is not marked as belonging to the other one")
    return problems


def main() -> int:
    if not CARD.exists():
        print(f"FAIL no {CARD.name} at {CARD}", file=sys.stderr)
        return 1
    text = CARD.read_text()
    body = text.split("\n---\n", 1)[1] if "\n---\n" in text else text
    yaml_text = front_matter(text)
    configs = parse_configs(yaml_text)
    check_licenses(yaml_text)

    measured: dict[str, int] = {}
    for name, split, rel in configs:
        p = ROOT / rel
        if not p.exists():
            fails.append(f"{name}: declared file missing: {rel}")
            continue
        rows = list(csv.reader(io.StringIO(p.read_text(errors="replace"))))
        rows = [r for r in rows if r]
        if len(rows) < 2:
            fails.append(f"{name}: {rel} has no data rows")
            continue
        header, data = rows[0], rows[1:]
        if any(not c.strip() for c in header):
            fails.append(f"{name}: empty column name in header {header}")
        ragged = [i for i, r in enumerate(data, 2) if len(r) != len(header)]
        if ragged:
            fails.append(f"{name}: {len(ragged)} row(s) with the wrong field count, "
                         f"first at line {ragged[0]}")
        if split != "train":
            fails.append(f"{name}: unexpected split {split!r} (the card declares train only)")
        measured[name] = len(data)

    # row counts stated in prose must match the files
    for name, n in re.findall(r"`([a-z0-9_]+)`[^`\n]{0,40}?(\d+)\s+rows", body):
        if name in measured and measured[name] != int(n):
            fails.append(f"{name}: card says {n} rows, file has {measured[name]}")

    for sec in REQUIRED_SECTIONS:
        if sec not in body:
            fails.append(f"missing card section: {sec}")

    fails.extend(check_no_internal_instructions(text))
    fails.extend(check_commands_run(body))

    print(f"verify_dataset_card: {len(configs)} configs declared")
    for name in sorted(measured):
        print(f"  {name:28s} {measured[name]:4d} rows")
    if fails:
        print("\n".join("FAIL " + f for f in fails), file=sys.stderr)
        return 1
    print("dataset card is consistent with the files it declares")
    return 0


if __name__ == "__main__":
    sys.exit(main())
