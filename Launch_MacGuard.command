#!/usr/bin/env bash
#
# MacGuard Quick Launcher for macOS Finder
# Double-click this file in Finder to immediately launch the on-demand deep clean mission!
#

DIR="$(cd "$(dirname "$0")" && pwd)"
"${DIR}/macguard" deep-clean

echo ""
read -p "Mission finished. Press Enter to close this window..."
