#!/usr/bin/env bash
# deposit.sh — create a Zenodo DRAFT record for the Case Study 1 evidence bundle.
#
# Nothing is published unless --publish is passed, and nothing touches the production
# site unless --allow-production is passed. A draft can be discarded; a published
# record can never be deleted, which is why the two flags are separate.
#
#   export ZENODO_TOKEN=...                     # Zenodo -> avatar -> Applications -> Tokens
#   ./zenodo/deposit.sh                          # sandbox host, draft only
#   ZENODO_HOST=https://zenodo.org ./zenodo/deposit.sh --allow-production
#   ... --allow-production --publish            # the only form that mints a DOI
#
# Endpoint note, learned against record 22699009 on 2026-09-11: the documented legacy
# route /api/deposit/depositions/{id}/files answers 400 on the current site, and
# files-archive answers 405. Files go to /api/records/{id}/draft/files: the init body
# must be a LIST of {"key": ...} objects, bytes go to each entry's links.content, and
# each file needs its own links.commit call.
set -euo pipefail
HOST="${ZENODO_HOST:-https://sandbox.zenodo.org}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
META="$ROOT/zenodo/deposit-dataset.json"
PUBLISH=0; PROD=0
for a in "$@"; do
  case "$a" in
    --publish) PUBLISH=1 ;;
    --allow-production) PROD=1 ;;
    *) echo "REFUSED: unknown argument: $a" >&2; exit 2 ;;
  esac
done
[[ -n "${ZENODO_TOKEN:-}" ]] || { echo "REFUSED: ZENODO_TOKEN is not set (host: $HOST). Create one at Zenodo -> avatar -> Applications -> Tokens; scope deposit:write creates drafts, deposit:actions is additionally required to publish. sandbox.zenodo.org is a separate site with its own tokens." >&2; exit 2; }
[[ -f "$META" ]] || { echo "REFUSED: metadata file missing: $META" >&2; exit 2; }
[[ "$HOST" == *sandbox* || "$PROD" == 1 ]] || { echo "REFUSED: $HOST is not the sandbox; pass --allow-production to work against it." >&2; exit 2; }
[[ "$HOST" != *sandbox* || "$PROD" == 0 ]] || { echo "REFUSED: --allow-production on a sandbox host is contradictory." >&2; exit 2; }
echo "host: $HOST   metadata: $(basename "$META")   publish: $PUBLISH"

TMP="$(mktemp -d)"; PAYLOAD="$TMP/ai-qos-case-study-1"
mkdir -p "$PAYLOAD/scripts"; cd "$ROOT"
for f in methodology.md anonymization.md LICENSE LICENSE-content.md LICENSE-code.md CITATION.cff DATASET_CARD.md; do
  [[ -f "$f" ]] || { echo "REFUSED: expected file missing: $f" >&2; exit 2; }
done
cp methodology.md anonymization.md LICENSE LICENSE-content.md LICENSE-code.md CITATION.cff "$PAYLOAD/"
cp -r evidence analysis "$PAYLOAD/"
cp scripts/analyze.py scripts/verify_dataset_card.py "$PAYLOAD/scripts/"
python3 - "$PAYLOAD/README.md" <<'PYCARD'
import sys
from pathlib import Path
t = Path("DATASET_CARD.md").read_text().splitlines()
keep, i = [t[0]], 1
while i < len(t) and not t[i].startswith("#"): keep.append(t[i]); i += 1
while i < len(t) and (t[i].startswith("#") or not t[i].strip()): i += 1
Path(sys.argv[1]).write_text("\n".join(keep + t[i:]) + "\n")
PYCARD
echo "payload: $(find "$PAYLOAD" -type f | wc -l) files, $(du -sh "$PAYLOAD" | cut -f1)"

AUTH=(-H "Content-Type: application/json" -H "Authorization: Bearer $ZENODO_TOKEN")
DEP="$(curl -sS -X POST "${AUTH[@]}" -d '{"metadata":{}}' "$HOST/api/deposit/depositions")"
ID="$(printf '%s' "$DEP" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')" \
  || { echo "REFUSED: the host did not accept the token. Response:" >&2; printf '%s\n' "$DEP" >&2; exit 3; }
echo "draft id: $ID"
python3 - "$META" "$TMP/meta.json" "$PUBLISH" <<'PYMETA'
import json, sys
from datetime import date
from pathlib import Path
d = json.loads(Path(sys.argv[1]).read_text())
d.pop("_fill_in_before_deposit", None)
# Zenodo's publication_date is the date the record becomes citable, so it is stamped only on a
# run that will publish: a draft revised on one day and published on a later one would otherwise
# archive the earlier date.
if sys.argv[3] == "1":
    d["publication_date"] = date.today().isoformat()
print(f"publication_date to be sent: {d.get('publication_date')}")
Path(sys.argv[2]).write_text(json.dumps({"metadata": d}))
PYMETA
curl -sS -X PUT "${AUTH[@]}" -d @"$TMP/meta.json" "$HOST/api/records/$ID/draft" >/dev/null && echo "metadata attached"
if ! python3 - "$ID" "$HOST" "$PAYLOAD" <<'PYUPLOAD'
import json, os, pathlib, sys, urllib.error, urllib.request
pid, host, root = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
base = f"{host}/api/records/{pid}/draft"
def call(method, url, body=None, ctype="application/json"):
    r = urllib.request.Request(url, data=body, method=method,
        headers={"Authorization": f"Bearer {os.environ['ZENODO_TOKEN']}", "Content-Type": ctype})
    try:
        with urllib.request.urlopen(r) as f: return f.status, f.read()
    except urllib.error.HTTPError as e: return e.code, e.read()
keys = [str(p.relative_to(root.parent)) for p in sorted(root.rglob("*")) if p.is_file()]
st, body = call("POST", base + "/files", json.dumps([{"key": k} for k in keys]).encode())
if st not in (200, 201):
    print(f"REFUSED: file init failed ({st}): {body[:200].decode(errors='replace')}", file=sys.stderr); sys.exit(3)
done = 0
ents = json.loads(body)["entries"]
for e in ents:
    local = root / e["key"].split("/", 1)[1]
    s1, _ = call("PUT", e["links"]["content"], local.read_bytes(), "application/octet-stream")
    s2, _ = call("POST", e["links"]["commit"])
    done += 1 if s1 in (200, 201) and s2 in (200, 201, 202) else 0
print(f"files uploaded and committed: {done}/{len(ents)}")
sys.exit(0 if done == len(ents) else 3)
PYUPLOAD
then echo "REFUSED: the file upload did not complete; the draft is left as a draft." >&2; exit 3; fi
echo "inspect: $HOST/deposit/$ID"
if [[ "$PUBLISH" == 1 ]]; then
  curl -sS -X POST "${AUTH[@]}" "$HOST/api/deposit/depositions/$ID/actions/publish" >/dev/null \
    && echo "PUBLISHED record $ID — write the DOI into CITATION.cff and the dataset card, then re-run the gates."
else
  echo "left as a draft (no --publish). Discard it at the link above, or publish deliberately."
fi
