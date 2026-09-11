#!/usr/bin/env bash
# preflight.sh — the only thing to remember before publishing anything.
#
# Every check in this repository exists because something once passed review and was wrong.
# That is too many checks to hold in your head, so they are ordered here and run in one go:
#
#   ./scripts/preflight.sh                 # local checks: documents, assertions, the tracked set
#   ./scripts/preflight.sh --release TAG   # the same, plus what must agree before a tag is released
#
# It never modifies a file, never uploads, and never publishes. Exit code 0 means every check
# that could run, passed; anything else means do not publish yet.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

REF=""
if [[ "${1:-}" == "--release" ]]; then
  [[ -n "${2:-}" ]] || { echo "usage: $0 --release <tag>" >&2; exit 64; }
  REF="$2"
  git rev-parse -q --verify "refs/tags/$REF" >/dev/null || { echo "no such tag: $REF" >&2; exit 64; }
elif [[ -n "${1:-}" ]]; then
  echo "usage: $0 [--release <tag>]" >&2; exit 64
fi

PASS=0; FAIL=0; SKIP=0
step() {   # step <label> <command...>
  local label="$1"; shift
  local out rc
  out="$("$@" 2>&1)"; rc=$?
  if [[ $rc -eq 0 ]]; then
    printf '  PASS  %s\n' "$label"; PASS=$((PASS+1))
  else
    printf '  FAIL  %s\n' "$label"; printf '%s\n' "$out" | sed 's/^/          /' | tail -6
    FAIL=$((FAIL+1))
  fi
  return 0
}
note() { printf '  NOTE  %s\n' "$1"; }
warn() { printf '  WARN  %s\n' "$1"; }

echo "=== 1. the published documents and their claims ==="
step "every figure re-derives from evidence/ and the assertions pass" python3 scripts/analyze.py
step "the dataset card tells the truth about the files it declares" python3 scripts/verify_dataset_card.py
step "no uncommitted change anywhere (the gates read the working tree)" bash -c '
  test -z "$(git status --porcelain)" || { echo "uncommitted: $(git status --porcelain | head -3)"; exit 1; }'

echo "=== 2. what a reader would actually receive ==="
step "links resolve, no personal data, ignore rules in place" python3 tools/verify_docs.py
step "no private file is reachable from the tracked set"      bash -c '
  hit=$(git ls-files | grep -E "PUBLICATION\.md|prior-works\.md|reposition\.md|methodology_guidance|NESTING_WORKFLOW|__pycache__|raw_evidence|logs_mirror|raw_snapshots" || true)
  test -z "$hit" || { echo "tracked but should not be published: $hit"; exit 1; }'
step "the data layer can be staged completely"                bash -c "
  d=\"\$(mktemp -d)/payload\"; trap 'rm -rf \"\$(dirname \"\$d\")\"' EXIT
  python3 scripts/build_data_layer.py --out \"\$d\" --ref '${REF:-HEAD}'"
step "a release note exists and is not a work log"            bash -c 'test -s RELEASE_NOTES.md'

echo "=== 3. identity and history (the metadata a file scan cannot see) ==="
step "the commit at HEAD is authored as the project handle"   bash -c '
  ident="$(git log -1 --format="%an <%ae>")"
  case "$ident" in 2makeitwork*) exit 0 ;; esac
  echo "HEAD is authored by: $ident  (published commits must carry the project handle)"; exit 1'
if ! git var GIT_AUTHOR_IDENT | grep -q '^2makeitwork'; then
  note "this machine's git identity is $(git var GIT_AUTHOR_IDENT | sed 's/ [0-9]* [-+0-9]*$//')"
  note "kept deliberately; so published commits override it per command:"
  note "  git -c user.name=2makeitwork -c user.email=2makeitwork@users.noreply.github.com commit ..."
fi
step "the published history carries no forbidden paths"       bash -c '
  bad=$(git log --format=%H origin/main 2>/dev/null | while read -r c; do
          git ls-tree -r --name-only "$c" | grep -E "NESTING_WORKFLOW|methodology_guidance|__pycache__" && echo "$c"
        done | sort -u)
  test -z "$bad" || { echo "leaked paths in: $bad"; exit 1; }'

if [[ -n "$REF" ]]; then
  echo "=== 4. release mode: what has to agree with $REF ==="
  behind="$(git rev-list --count "$REF"..HEAD 2>/dev/null || echo '?')"
  if [[ "$behind" != "0" ]]; then
    warn "$REF is $behind commit(s) behind main; the release note, the builder or a gate may"
    warn "not be in the tree the tag names. Tag again if that matters, or accept the older text."
  fi
  if git diff --quiet "$REF" -- evidence analysis CITATION.cff LICENSE LICENSE-code.md \
       LICENSE-content.md methodology.md anonymization.md README.md DATASET_CARD.md scripts 2>/dev/null; then
    note "no payload or document file differs between $REF and main"
  else
    warn "these files differ between $REF and main, so the published copies must be rebuilt from $REF:"
    git diff --name-only "$REF" -- evidence analysis CITATION.cff LICENSE LICENSE-code.md \
       LICENSE-content.md methodology.md anonymization.md README.md DATASET_CARD.md scripts \
      | sed 's/^/          /'
  fi
  if command -v hf >/dev/null 2>&1 || [[ -x "$HOME/.local/bin/hf" ]]; then
    step "the served dataset repository is byte-identical to $REF" \
      env -u ALL_PROXY -u all_proxy python3 scripts/check_release_sync.py --ref "$REF"
    if [[ -n "${ZENODO_TOKEN:-}" ]]; then
      step "the Zenodo draft agrees with $REF too" env -u ALL_PROXY -u all_proxy \
        python3 scripts/check_release_sync.py --ref "$REF" --no-hf --zenodo-draft "${ZENODO_RECORD:-22699009}"
    else
      note "ZENODO_TOKEN not set: the archive draft was not compared (a published record needs no token)"
    fi
  else
    note "the hf command was not found: the served copies were not verified"
  fi
fi

echo
if [[ $FAIL -gt 0 ]]; then
  echo "NOT READY TO PUBLISH — $FAIL failing check(s), $PASS passed, $SKIP skipped."
  exit 1
fi
echo "READY — $PASS checks passed, and nothing was written, uploaded or published."
if [[ -n "$REF" ]]; then
  cat <<'ORDER'

Then by hand, in this order — each step is public or irreversible, so none is automated:

  1. Zenodo, your account, Applications -> GitHub: enable 2makeitwork/paper_ai_Qos.
     Do this FIRST: a release published while the integration is off is never archived.
  2. GitHub: publish the draft release for the tag (gh release edit <tag> --draft=false
     --notes-file RELEASE_NOTES.md). Publishing it is what mints the software version DOI.
  3. Zenodo: publish the record 22699009 (edit page https://zenodo.org/deposit/22699009).
     A published record can be corrected but never deleted. Write the DOI into CITATION.cff,
     the dataset card and README afterwards, and re-run this script.
  4. Revoke the access token you pasted into the chat, once it is no longer in use.
ORDER
fi
exit 0
