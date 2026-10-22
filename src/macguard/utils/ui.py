"""
Terminal UI formatting, colors, progress bars, and interactive presentation.
"""

from __future__ import annotations

import sys
import time
from typing import Optional, List

class Colors:
    """ANSI terminal styling."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"

    BG_DARK = "\033[40m"
    BG_BLUE = "\033[44m"

def is_tty() -> bool:
    """Check if stdout is an interactive terminal."""
    return sys.stdout.isatty()

def style(text: str, *styles: str) -> str:
    """Apply ANSI styles if in a TTY."""
    if not is_tty():
        return text
    return "".join(styles) + text + Colors.RESET

def print_header(title: str, subtitle: Optional[str] = None) -> None:
    """Prints a styled box header."""
    width = 80
    border = "═" * width
    print(style(border, Colors.CYAN, Colors.BOLD))
    print(style(f"  {title.center(width - 4)}", Colors.BOLD, Colors.WHITE))
    if subtitle:
        print(style(f"  {subtitle.center(width - 4)}", Colors.GRAY))
    print(style(border, Colors.CYAN, Colors.BOLD))

def print_divider(label: Optional[str] = None) -> None:
    width = 80
    if label:
        fill_len = max(0, width - len(label) - 6)
        left = "─" * 4
        right = "─" * fill_len
        print(style(f"{left} [ {label} ] {right}", Colors.CYAN))
    else:
        print(style("─" * width, Colors.GRAY))

def storage_bar(used_pct: float, width: int = 24) -> str:
    """Renders a graphical storage progress bar."""
    filled = int(round((used_pct / 100.0) * width))
    filled = max(0, min(width, filled))
    empty = width - filled

    # Color based on utilization
    if used_pct >= 90.0:
        bar_color = Colors.RED
    elif used_pct >= 75.0:
        bar_color = Colors.YELLOW
    else:
        bar_color = Colors.GREEN

    bar = style("█" * filled, bar_color) + style("░" * empty, Colors.GRAY)
    return f"[{bar}] {used_pct:.1f}%"

def live_progress_step(stage_num: int, total_stages: int, step_name: str, delay: float = 0.04) -> None:
    """Displays a clean live step transition in terminal."""
    prefix = style(f"[{stage_num}/{total_stages}]", Colors.CYAN, Colors.BOLD)
    print(f"\n{prefix} {style(step_name, Colors.BOLD)}", flush=True)
    if is_tty() and delay > 0:
        time.sleep(delay)
