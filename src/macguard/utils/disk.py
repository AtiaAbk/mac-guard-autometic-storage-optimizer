"""
Disk and storage utility functions for macOS.
Supports calculating apparent size (logical bytes) and allocated disk space (physical blocks).
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
    Backward-compatible wrapper returning (apparent_bytes, file_count).
    """
    apparent, _, count = get_path_detailed_size(path)
    return apparent, count

def get_path_detailed_size(path: Path) -> Tuple[int, int, int]:
    """
    Calculate (apparent_bytes, allocated_bytes, file_count).
    - apparent_bytes: Logical file size (st_size)
    - allocated_bytes: Physical disk space occupied on blocks (st_blocks * 512 on POSIX/macOS)
    - file_count: Total files inspected
    """
    if not path.exists():
        return 0, 0, 0

    if path.is_file():
        try:
            st = path.stat()
            apparent = st.st_size
            allocated = getattr(st, "st_blocks", 0) * 512
            # allocated space might be 0 for empty files; for non-sparse, min is apparent
            return apparent, max(allocated, 0), 1
        except Exception:
            return 0, 0, 0

    total_apparent = 0
    total_allocated = 0
    file_count = 0

    try:
        for entry in os.scandir(str(path)):
            try:
                if entry.is_symlink():
                    continue
                if entry.is_file(follow_symlinks=False):
                    st = entry.stat(follow_symlinks=False)
                    total_apparent += st.st_size
                    total_allocated += getattr(st, "st_blocks", 0) * 512
                    file_count += 1
                elif entry.is_dir(follow_symlinks=False):
                    sub_app, sub_alloc, sub_cnt = get_path_detailed_size(Path(entry.path))
                    total_apparent += sub_app
                    total_allocated += sub_alloc
                    file_count += sub_cnt
            except (PermissionError, FileNotFoundError, OSError):
                continue
    except (PermissionError, FileNotFoundError, OSError):
        pass

    return total_apparent, total_allocated, file_count
