#!/usr/bin/env bash
#
# MacGuard CLI Installation Helper
# Links `macguard` into your user PATH.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MACGUARD_EXEC="${SCRIPT_DIR}/macguard"

echo "Installing MacGuard CLI from ${SCRIPT_DIR}..."

# Candidate install directories
INSTALL_DIR=""
if [ -d "$HOME/.gemini/antigravity/bin" ] && [ -w "$HOME/.gemini/antigravity/bin" ]; then
    INSTALL_DIR="$HOME/.gemini/antigravity/bin"
elif [ -d "$HOME/.local/bin" ] && [ -w "$HOME/.local/bin" ]; then
    INSTALL_DIR="$HOME/.local/bin"
elif [ -d "/usr/local/bin" ] && [ -w "/usr/local/bin" ]; then
    INSTALL_DIR="/usr/local/bin"
else
    mkdir -p "$HOME/.local/bin"
    INSTALL_DIR="$HOME/.local/bin"
fi

TARGET="${INSTALL_DIR}/macguard"
ln -sf "${MACGUARD_EXEC}" "${TARGET}"
chmod +x "${TARGET}"

echo "✓ Successfully installed MacGuard to: ${TARGET}"
echo ""
echo "You can now run MacGuard anywhere with:"
echo "    macguard mission"
