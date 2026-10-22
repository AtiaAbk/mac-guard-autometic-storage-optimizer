#!/usr/bin/env bash
#
# MacGuard Quick Launcher for macOS Finder
# Double-click this file in Finder to immediately launch the interactive maintenance mission!
#

DIR="$(cd "$(dirname "$0")" && pwd)"
"${DIR}/macguard" mission

echo ""
read -p "Mission finished. Press Enter to close this window..."
