"""
Stage 6: Realistic Storage Savings Calculator.

Calculates realistic potential storage savings without double-counting:
- Normalizes canonical paths (Path.resolve())
- Resolves parent-child folder hierarchies (parent inclusion supersedes child items)
- Deduplicates file overlap across scan groups
- Calculates accurate duplicate savings: (N - 1) * size
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List, Set
from macguard.utils.disk import format_bytes

def calculate_savings(groups: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes accurate, non-double-counted potential storage savings.
    """
    resolved_targeted_dirs: Set[Path] = set()
    unique_targeted_files: Set[Path] = set()

    gross_bytes = 0
    net_bytes = 0
    recommended_bytes = 0

    category_savings: Dict[str, int] = {}

    # Pre-collect all paths to detect parent-child directory hierarchies
    all_candidate_paths: List[Path] = []
    for g in groups:
        if not g.get("is_selectable", False):
            continue
        for it in g.get("items", []):
            raw = it.get("path")
            if raw and it.get("action") in {"DELETE_CACHE_DIR", "DELETE_DIR"} or (raw and Path(raw).is_dir()):
                try:
                    all_candidate_paths.append(Path(raw).resolve())
                except Exception:
                    pass

    for group in groups:
        gid = group["group_id"]
        group_total = group.get("total_bytes", 0)
        gross_bytes += group_total
        category_savings[gid] = 0

        # Protected and unselectable groups do NOT contribute to potential cleanup savings
        if not group.get("is_selectable", False):
            continue

        # If duplicate group, savings is already calculated as (N-1)*size
        if gid == "duplicate_candidates":
            category_savings[gid] = group_total
            net_bytes += group_total
            continue

        group_net = 0
        for item in group.get("items", []):
            raw_path = item.get("path")
            if not raw_path:
                continue

            try:
                p = Path(raw_path).resolve()
            except Exception:
                continue

            # Check if this path is already inside an already-targeted directory
            is_nested = False
            for parent_dir in resolved_targeted_dirs:
                if p != parent_dir and (parent_dir in p.parents or str(p).startswith(str(parent_dir) + "/")):
                    is_nested = True
                    break

            if is_nested:
                # Subordinate item already covered by parent directory
                continue

            item_bytes = item.get("size_bytes", 0)
            is_dir_item = (
                item.get("action") in {"DELETE_CACHE_DIR", "DELETE_DIR"}
                or p.is_dir()
                or any(str(other).startswith(str(p) + "/") for other in all_candidate_paths if other != p)
            )

            if is_dir_item:
                resolved_targeted_dirs.add(p)
                group_net += item_bytes
            else:
                if p not in unique_targeted_files:
                    unique_targeted_files.add(p)
                    group_net += item_bytes

        category_savings[gid] = group_net
        net_bytes += group_net

        if group.get("recommended_action") == "APPROVE":
            recommended_bytes += group_net

    return {
        "gross_potential_bytes": gross_bytes,
        "gross_potential_human": format_bytes(gross_bytes),
        "net_potential_bytes": net_bytes,
        "net_potential_human": format_bytes(net_bytes),
        "recommended_savings_bytes": recommended_bytes,
        "recommended_savings_human": format_bytes(recommended_bytes),
        "category_savings": {
            k: {"bytes": v, "human": format_bytes(v)}
            for k, v in category_savings.items()
        }
    }
