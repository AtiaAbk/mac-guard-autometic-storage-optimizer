"""
System utilities and command execution wrappers for macOS.
"""

from __future__ import annotations

import subprocess
from typing import Tuple, Optional, List, Dict, Any

def run_cmd(args: List[str], timeout: int = 15) -> Tuple[int, str, str]:
    """Execute a system command safely with a timeout and return (rc, stdout, stderr)."""
    try:
        proc = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", f"Command {' '.join(args)} timed out after {timeout}s"
    except FileNotFoundError:
        return -2, "", f"Command {args[0]} not found"
    except Exception as e:
        return -3, "", str(e)
