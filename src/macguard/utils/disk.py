"""
Disk and storage utility functions.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict, Any, Tuple

def format_bytes(num_bytes: int) -> str:
    """Format bytes into human readable string (B, KB, MB, GB, TB)."""
    if num_bytes < 0:
        return f"-{format_bytes(-num_bytes)}"
    if num_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    val = float(num_bytes)
    unit_index = 0
    while val >= 1024.0 and unit_index < len(units) - 1:
        val /= 1024.0
        unit_index += 1
    if unit_index == 0:
        return f"{int(val)} B"
    return f"{val:.2f} {units[unit_index]}"

def get_disk_usage(path: str | Path = "/") -> Dict[str, Any]:
    """Get total, used, free storage and percentage for a given path."""
    try:
        stat = os.statvfs(str(path))
        block_size = stat.f_frsize or stat.f_bsize
        total = stat.f_blocks * block_size
        free = stat.f_bavail * block_size
        used = total - (stat.f_bfree * block_size)
        pct_used = (used / total * 100.0) if total > 0 else 0.0
        return {
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "pct_used": round(pct_used, 1),
            "total_human": format_bytes(total),
            "used_human": format_bytes(used),
            "free_human": format_bytes(free),
        }
    except Exception:
        # Fallback to shutil.disk_usage
        try:
            usage = shutil.disk_usage(str(path))
            pct_used = (usage.used / usage.total * 100.0) if usage.total > 0 else 0.0
            return {
                "total_bytes": usage.total,
                "used_bytes": usage.used,
                "free_bytes": usage.free,
                "pct_used": round(pct_used, 1),
                "total_human": format_bytes(usage.total),
                "used_human": format_bytes(usage.used),
                "free_human": format_bytes(usage.free),
            }
        except Exception as e:
            return {
                "total_bytes": 0,
                "used_bytes": 0,
                "free_bytes": 0,
                "pct_used": 0.0,
                "total_human": "Unknown",
                "used_human": "Unknown",
                "free_human": "Unknown",
                "error": str(e)
            }

def get_path_size(path: Path) -> Tuple[int, int]:
    """
    Calculate the total size and file count of a file or directory.
    Follows symlinks only to calculate the symlink itself, not recursive target loops.
    Returns (total_bytes, file_count).
    """
    if not path.exists():
        return 0, 0
    if path.is_file():
        try:
            return path.stat().st_size, 1
        except Exception:
            return 0, 0

    total_bytes = 0
    file_count = 0
    try:
        for entry in os.scandir(str(path)):
            try:
                if entry.is_symlink():
                    continue
                if entry.is_file(follow_symlinks=False):
                    total_bytes += entry.stat().st_size
                    file_count += 1
                elif entry.is_dir(follow_symlinks=False):
                    sub_bytes, sub_count = get_path_size(Path(entry.path))
                    total_bytes += sub_bytes
                    file_count += sub_count
            except (PermissionError, FileNotFoundError, OSError):
                continue
    except (PermissionError, FileNotFoundError, OSError):
        pass

    return total_bytes, file_count
