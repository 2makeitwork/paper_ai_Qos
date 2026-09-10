#!/usr/bin/env bash
# watcher-drain.sh — locate the Node.js interpreter, then drain the Qoder CN chat
# watcher queue once. Used by qoder-watcher-drain.service; written as a script
# because systemd's own command parsing strips the quotes a `bash -lc '…'` form
# needs, which silently truncated the command (exit status 127).
#
# systemd gives user units a PATH that excludes version managers (nvm, fnm, pnpm),
# so a login shell is not enough: Ubuntu's ~/.bashrc returns early for
# non-interactive shells and never sources nvm. Fall back to the installed
# version directory instead of hard-coding a version number.
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
WATCHER="$REPO/scripts/watcher/cdp_watch.js"

NODE="$(command -v node || true)"
if [ -z "$NODE" ]; then
    NODE="$(ls -1 "$HOME"/.nvm/versions/node/*/bin/node 2>/dev/null | tail -1)"
fi
if [ -z "$NODE" ]; then
    NODE="$(ls -1 "$HOME"/.local/share/fnm/node-versions/*/installation/bin/node 2>/dev/null | tail -1)"
fi
if [ -z "$NODE" ]; then
    echo "watcher-drain: no node binary found (PATH=$PATH)" >&2
    exit 127
fi
exec "$NODE" "$WATCHER" drain
