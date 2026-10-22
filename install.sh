#!/usr/bin/env bash
#
# MacGuard One-Click Installation & PATH Configuration Script
#

set -e

# ANSI Color codes
BOLD="\033[1m"
GREEN="\033[32m"
CYAN="\033[36m"
YELLOW="\033[33m"
RESET="\033[0m"

echo -e "${CYAN}${BOLD}════════════════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}          🛡️  MacGuard One-Click Setup & PATH Installer          ${RESET}"
echo -e "${CYAN}${BOLD}════════════════════════════════════════════════════════════════${RESET}\n"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MACGUARD_EXEC="${SCRIPT_DIR}/macguard"

if [ ! -f "${MACGUARD_EXEC}" ]; then
    echo -e "${YELLOW}Error: 'macguard' binary not found in ${SCRIPT_DIR}${RESET}"
    exit 1
fi

chmod +x "${MACGUARD_EXEC}"

# 1. Determine best system binary location
mkdir -p "$HOME/.local/bin"
TARGET_LINK="$HOME/.local/bin/macguard"
ln -sf "${MACGUARD_EXEC}" "${TARGET_LINK}"
chmod +x "${TARGET_LINK}"

# Also link into Homebrew bin or /usr/local/bin if writable
if [ -d "/opt/homebrew/bin" ] && [ -w "/opt/homebrew/bin" ]; then
    ln -sf "${MACGUARD_EXEC}" "/opt/homebrew/bin/macguard" 2>/dev/null || true
fi
if [ -d "/usr/local/bin" ] && [ -w "/usr/local/bin" ]; then
    ln -sf "${MACGUARD_EXEC}" "/usr/local/bin/macguard" 2>/dev/null || true
fi
if [ -d "$HOME/.gemini/antigravity/bin" ] && [ -w "$HOME/.gemini/antigravity/bin" ]; then
    ln -sf "${MACGUARD_EXEC}" "$HOME/.gemini/antigravity/bin/macguard" 2>/dev/null || true
fi

echo -e "  ${GREEN}✓ Linked executable:${RESET} ${TARGET_LINK}"

# 2. Configure Shell Profiles (~/.zshrc and ~/.bash_profile)
SHELL_CONFIGS=("$HOME/.zshrc" "$HOME/.bash_profile" "$HOME/.bashrc")

for CONF in "${SHELL_CONFIGS[@]}"; do
    if [ -f "$CONF" ] || [ "$CONF" = "$HOME/.zshrc" ]; then
        touch "$CONF"
        
        # Add ~/.local/bin to PATH if missing
        if ! grep -q 'HOME/.local/bin' "$CONF" && ! grep -q '\$HOME/\.local/bin' "$CONF"; then
            echo -e '\n# MacGuard CLI PATH' >> "$CONF"
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$CONF"
            echo -e "  ${GREEN}✓ Configured PATH in:${RESET} ${CONF}"
        fi

        # Add fallback alias to guarantee instant recognition
        if ! grep -q 'alias macguard=' "$CONF"; then
            echo "alias macguard='\"${MACGUARD_EXEC}\"'" >> "$CONF"
            echo -e "  ${GREEN}✓ Registered global alias in:${RESET} ${CONF}"
        fi
    fi
done

echo -e "\n${CYAN}${BOLD}════════════════════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}  🎉 SUCCESS: MacGuard is installed and ready to use!${RESET}"
echo -e "${CYAN}${BOLD}════════════════════════════════════════════════════════════════${RESET}\n"

echo -e "To start your maintenance mission right now, type:\n"
echo -e "    ${BOLD}macguard mission${RESET}\n"
echo -e "*(If in an already-open terminal window, run: ${YELLOW}source ~/.zshrc${RESET} or open a new window)*\n"
