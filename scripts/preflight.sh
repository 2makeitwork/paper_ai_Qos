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
skip() { printf '  SKIP  %s\n' "$1"; SKIP=$((SKIP+1)); }

echo "=== 1. the published documents and their claims ==="
step "every figure re-derives from evidence/ and the assertions pass" python3 scripts/analyze.py
step "the dataset card tells the truth about the files it declares" python3 scripts/verify_dataset_card.py
step "working tree is clean (the author's step is to commit - an agent must not act on this)" bash -c '
  test -z "$(git status --porcelain)" || { echo "uncommitted, so a green run describes a tree that no longer exists: $(git status --porcelain | head -3)"; exit 1; }'

echo "=== 2. what a reader would actually receive ==="
if [[ -f tools/verify_docs.py ]]; then
  step "links resolve, no personal data, ignore rules in place" python3 tools/verify_docs.py
else
  # tools/ is the author's local-only document gate; it is deliberately not published. Absent, it
  # is a skip, not a failure: a stranger who clones this repository and runs the gate must not end
  # with a red light caused by tooling that was never given to them.
  skip "links/personal-data/ignore gate needs tools/verify_docs.py, which is author-side tooling and is not published"
fi
step "no private file is reachable from the tracked set"      bash -c '
  hit=$(git ls-files | grep -E "PUBLICATION\.md|prior-works\.md|methodology_guidance|NESTING_WORKFLOW|__pycache__|raw_evidence|logs_mirror|raw_snapshots" || true)
  test -z "$hit" || { echo "tracked but should not be published: $hit"; exit 1; }'
step "the staged data layer stages completely AND passes its own scripts" bash -c "
  d=\"\$(mktemp -d)/payload\"; trap 'rm -rf \"\$(dirname \"\$d\")\"' EXIT
  python3 scripts/build_data_layer.py --out \"\$d\" --ref '${REF:-HEAD}'
  # The card's commands are checked where the reader runs them. A pass in the source
  # repository proves nothing about the published subset: 'tools/' and the unpublished
  # log-side scripts all exist here, and that is how an un-runnable instruction reached
  # the card twice.
  cd \"\$d\" || exit 1
  python3 scripts/verify_dataset_card.py >/dev/null || { echo 'card check fails inside the staged payload'; exit 1; }
  python3 scripts/analyze.py >/dev/null || { echo 'assertions fail inside the staged payload'; exit 1; }"
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
  step "CITATION.cff names this tag as the citable snapshot" python3 -c "
import re, sys
found = re.search(r'^version: \"([^\"]+)\"', open('CITATION.cff').read(), re.M).group(1)
if found != sys.argv[1]:
    print(f'CITATION.cff says version {found}, this release is {sys.argv[1]}'); sys.exit(1)
" "${REF#v}"
  behind="$(git rev-list --count "$REF"..HEAD 2>/dev/null || echo '?')"
  if [[ "$behind" != "0" ]]; then
    warn "$REF is $behind commit(s) behind main; the release note, the builder or a gate may"
    warn "not be in the tree the tag names. Tag again if that matters, or accept the older text."
  fi
  # The files a reader actually receives: the data-layer payload plus the source-repository
  # documents published alongside it. Named rather than given as `scripts`, because most of
  # scripts/ is collector tooling that exists only on GitHub — editing this release gate should
  # not read as though the release were missing something a reader needs.
  PUBLISHED_PATHS="evidence analysis CITATION.cff LICENSE LICENSE-code.md LICENSE-content.md
    methodology.md anonymization.md README.md DATASET_CARD.md RELEASE_NOTES.md
    scripts/analyze.py scripts/verify_dataset_card.py scripts/check_release_sync.py
    scripts/build_data_layer.py"
  if git diff --quiet "$REF" -- $PUBLISHED_PATHS 2>/dev/null; then
    note "no published file differs between $REF and main"
  else
    warn "these files differ between $REF and main, so the published copies must be rebuilt from $REF:"
    git diff --name-only "$REF" -- $PUBLISHED_PATHS | sed 's/^/          /'
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
  # Measured, not recited. This list used to assert "publish the draft release" after the release
  # had been published, and "enable the integration first" after it was too late for that version:
  # instructions that contradict the world are worse than none, so each line is conditional on what
  # the APIs say right now.
  hooks="?"; rel="absent"
  if command -v gh >/dev/null 2>&1; then
    hooks="$(gh api repos/2makeitwork/paper_ai_Qos/hooks --jq 'length' 2>/dev/null || echo '?')"
    rel="$(gh release view "$REF" --json isDraft --jq 'if .isDraft then "draft" else "published" end' 2>/dev/null || echo absent)"
  fi
  n=1
  # The acts below name that account's archive record, release and token. Printed into a fork's
  # terminal they would instruct a stranger to publish someone else's submission, so they appear
  # only when this checkout really is the project's own repository.
  origin="$(git remote get-url origin 2>/dev/null || true)"
  if [[ "$origin" != *"2makeitwork/paper_ai_Qos"* ]]; then
    echo
    echo "  (the remaining acts are for whoever maintains 2makeitwork/paper_ai_Qos — they name"
    echo "   that account's archive record, release and access token. This checkout's origin is"
    echo "   elsewhere, so they do not apply; what a fork owns is its own tags and records.)"
    exit 0
  fi
  echo
  echo "Remaining acts, in order — each is public or irreversible, so none is automated:"
  if [[ "$hooks" == "0" ]]; then
    echo "  $n. No Zenodo webhook exists on this repository (measured just now), so the integration"
    echo "     is not installed: your account -> Applications -> GitHub -> authorize -> switch this"
    echo "     repository On, which is what creates the hook."
    if [[ "$rel" == "published" ]]; then
      echo "     $REF is already published, so enabling now cannot archive this version - a manual"
      echo "     deposit is the remaining way to a software identifier for it (zenodo/README.md)."
    fi
    n=$((n+1))
  elif [[ "$hooks" == "?" ]]; then
    echo "  $n. gh is unavailable here: whether the Zenodo webhook exists could not be measured."
    n=$((n+1))
  fi
  if [[ "$rel" != "published" ]]; then
    echo "  $n. GitHub: publish the release for $REF (gh release edit $REF --draft=false"
    echo "     --notes-file RELEASE_NOTES.md) — that event is what the integration would archive."
    n=$((n+1))
  fi
  if grep -q '^# dataset-doi: pending' CITATION.cff; then
    echo "  $n. Zenodo: publish record 22699009 (https://zenodo.org/deposit/22699009) — the evidence"
    echo "     bundle. Correctable afterwards, never deletable. Then replace the pending marker in"
    echo "     CITATION.cff with the identifier and re-run this script."
    n=$((n+1))
  fi
  [[ -n "${ZENODO_TOKEN:-}" ]] && echo "  $n. Revoke the Zenodo access token in use: it was typed into a chat transcript."
  exit 0
fi
exit 0
