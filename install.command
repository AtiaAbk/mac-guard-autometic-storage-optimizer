#!/usr/bin/env bash
#
# MacGuard Double-Click Installer for macOS Finder
# Double-click this file in Finder to automatically configure your PATH and install MacGuard!
#

DIR="$(cd "$(dirname "$0")" && pwd)"
bash "${DIR}/install.sh"

echo ""
read -p "Press Enter to close this window..."
