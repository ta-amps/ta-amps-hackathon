#!/usr/bin/env bash
# Install Meta's Muse Code CLI the careful way: download the official installer, show what it is, then run it only if
# you say yes. Nothing is piped straight into a shell.
# Usage: scripts/install-muse-code.sh
# Docs: https://dev.meta.ai/docs/muse-code (the installer is a bash script).
set -euo pipefail

URL="https://dev.meta.ai/install.sh"
tmp="$(mktemp -t muse-install.XXXXXX)"
trap 'rm -f "$tmp"' EXIT

echo "Downloading $URL"
curl -fsSL --proto '=https' --tlsv1.2 -o "$tmp" "$URL"

echo
echo "SHA-256: $(sha256sum "$tmp" | cut -d' ' -f1)"
echo "Size:    $(wc -c < "$tmp") bytes"
echo
echo "First 40 lines:"
echo "----------------------------------------------------------------"
head -n 40 "$tmp"
echo "----------------------------------------------------------------"
echo
echo "Useful settings before you run it:"
echo "  MUSE_NO_MODIFY_PATH=1   don't edit your shell rc files"
echo "  MUSE_NO_AUTO_UPDATE=1   don't auto-update (set this while recording a demo)"
echo
read -r -p "Run this installer with bash now? [y/N] " answer
case "$answer" in
  y|Y|yes|YES)
    bash "$tmp"
    echo
    echo "Installed. Before any headless run:"
    echo "  - keep the sandbox on (never --yolo or --disable-sandbox)"
    echo "  - pass --contributor-mode off (subscriptions default to Contributor mode)"
    ;;
  *)
    echo "Not run. The installer was deleted."
    ;;
esac
