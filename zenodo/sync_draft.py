#!/usr/bin/env python3
"""sync_draft.py — bring a Zenodo DRAFT record's files to a git revision.

Publishing a Zenodo record is irreversible, but editing a draft is free, so every release
cycle should end with this script and `scripts/check_release_sync.py --zenodo-draft <id>`
before anyone clicks publish. Files are staged by `scripts/build_data_layer.py`, which owns
the manifest, so what GitHub gets, what the dataset repository gets and what the archive
gets come from one list.

    ZENODO_TOKEN=… python3 zenodo/sync_draft.py --record 22699009 --ref v0.3.0-pre.2
    ZENODO_TOKEN=… python3 zenodo/sync_draft.py --record 22699009 --ref v0.3.0-pre.2 --metadata

`--metadata` additionally sends zenodo/deposit-dataset.json. Nothing here publishes: that is
`zenodo/deposit.sh --allow-production --publish`, or the button on the edit page.

Endpoint note, learned against record 22699009 on 2026-09-11: the documented legacy route
`/api/deposit/depositions/{id}/files` answers 400 on the current site; keys are initialised
as a list on `/api/records/{id}/draft/files`, bytes are PUT to each entry's `links.content`,
each entry is committed separately, and replacing an existing key means deleting it first.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "ai-qos-case-study-1"          # the folder name the published draft uses
sys.path.insert(0, str(ROOT / "scripts"))


def api(method: str, url: str, body=None, ctype="application/json", token="") -> tuple[int, object]:
    data = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()
    headers = {"Content-Type": ctype}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            payload = r.read()
            return r.status, (json.loads(payload or b"{}") if ctype.endswith("json") else payload)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()[:300]


def staged(ref: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="datalayer-"))
    out = tmp / "payload"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_data_layer.py"),
                    "--ref", ref, "--out", str(out)], check=True, timeout=600)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--record", required=True, help="Zenodo draft record id")
    ap.add_argument("--ref", default=None, help="git revision to take the files from")
    ap.add_argument("--host", default=os.environ.get("ZENODO_HOST", "https://zenodo.org"))
    ap.add_argument("--metadata", action="store_true",
                    help="also send zenodo/deposit-dataset.json as the record metadata")
    ap.add_argument("--prefix", default=PREFIX, help="folder name inside the record (default: %s)" % PREFIX)
    args = ap.parse_args()

    token = os.environ.get("ZENODO_TOKEN", "")
    if not token:
        print("REFUSED: ZENODO_TOKEN is not set; a published record needs no token but a draft does.",
              file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as keep:
        src = staged(args.ref) if args.ref else None
        base = src if src is not None else ROOT
        files = {}
        for p in sorted(base.rglob("*")):
            if p.is_file():
                files[p.relative_to(base).as_posix()] = p.read_bytes()
        print(f"staged from {args.ref or 'the working tree'}: {len(files)} files, "
              f"{sum(len(v) for v in files.values()):,} bytes")

        st, listing = api("GET", f"{args.host}/api/records/{args.record}/draft/files", token=token)
        if st != 200:
            print(f"REFUSED: the host answered {st}: {listing}", file=sys.stderr)
            return 3
        have = {e["key"]: e for e in listing["entries"]}
        stale = {f"{args.prefix}/{rel}": blob for rel, blob in files.items()
                 if f"{args.prefix}/{rel}" not in have
                 or "md5:" + hashlib.md5(blob).hexdigest() != (have[f"{args.prefix}/{rel}"].get("checksum") or "")}
        print(f"already identical: {len(files) - len(stale)} | to replace or add: {len(stale)}")

        if stale:
            init = []
            for key in stale:
                if key in have:
                    api("DELETE", f"{args.host}/api/records/{args.record}/draft/files/"
                                  f"{urllib.parse.quote(key, safe='')}", token=token)
                init.append({"key": key})
            st, entries = api("POST", f"{args.host}/api/records/{args.record}/draft/files", init,
                              token=token)
            if st not in (200, 201):
                print(f"REFUSED: initialising keys failed ({st}): {entries}", file=sys.stderr)
                return 4
            links = {e["key"]: e for e in entries["entries"]}
            done = 0
            for key, blob in stale.items():
                e = links.get(key)
                if not e:
                    print(f"  no init entry for {key}", file=sys.stderr)
                    continue
                s1, _ = api("PUT", e["links"]["content"], blob, "application/octet-stream", token)
                s2, _ = api("POST", e["links"]["commit"], None, token=token)
                if s1 == 200 and s2 in (200, 201):
                    done += 1
                else:
                    print(f"  FAILED {key}: content {s1}, commit {s2}")
            print(f"replaced or added {done}/{len(stale)} keys")

        if args.metadata:
            meta = json.loads((ROOT / "zenodo" / "deposit-dataset.json").read_text())
            meta.pop("_fill_in_before_deposit", None)
            st, resp = api("PUT", f"{args.host}/api/deposit/depositions/{args.record}",
                           {"metadata": meta}, token=token)
            print(f"metadata PUT -> {st}"
                  + ("" if st == 200 else f": {resp}"))

        st, fin = api("GET", f"{args.host}/api/records/{args.record}/draft/files", token=token)
        total = sum(int(e.get("size") or 0) for e in fin["entries"])
        print(f"draft {args.record} now: {len(fin['entries'])} files, {total:,} bytes — "
              f"still a draft; publishing is a separate, explicit act")
        if src is not None:
            subprocess.run(["rm", "-rf", str(src.parent)], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
