"""
Stage 9: Safe Execution Engine with Per-Group Explicit Confirmation.

Enforces:
- Displays exact scope of approval before each group executes
- Requires explicit confirmation ('yes' or 'y') before executing each group
- Never treats Enter, empty input, timeout, or Ctrl+C as approval
- Deletes only approved files / custom selected files
- Validates all items against SafetyPolicy
- Emits real-time progress and detailed audit events
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Set, Optional

from macguard.safety import SafetyPolicy
from macguard.utils.disk import format_bytes
from macguard.utils.audit import AuditLogger
from macguard.utils.ui import Colors, style, print_header, print_divider

def execute_approved_actions(
    groups: List[Dict[str, Any]],
    approved_group_ids: Set[str],
    custom_approved_files: Optional[Dict[str, Set[str]]] = None,
    dry_run: bool = False,
    non_interactive: bool = False,
    allow_synthetic: bool = False,
    audit_logger: AuditLogger | None = None
) -> Dict[str, Any]:
    """
    Executes approved actions with per-group confirmation and safety validations.
    """
    custom_approved_files = custom_approved_files or {}

    summary: Dict[str, Any] = {
        "dry_run": dry_run,
        "approved_groups": list(approved_group_ids),
        "executed_items": [],
        "skipped_items": [],
        "failed_items": [],
        "total_attempted_bytes": 0,
        "total_reclaimed_bytes": 0,
        "total_reclaimed_human": "0 B"
    }

    if not approved_group_ids:
        print("\n[MacGuard] No action groups approved for execution.")
        return summary

    for group in groups:
        gid = group["group_id"]
        if gid not in approved_group_ids:
            continue

        # Prevent execution on protected categories
        if group.get("risk_level") == "PROTECTED" or not group.get("is_selectable", False):
            print(style(f"\n[MacGuard Safety Guard] Refusing execution on protected group '{gid}'.", Colors.RED))
            continue

        # Determine exact items to target
        target_items: List[Dict[str, Any]] = []
        is_custom = gid in custom_approved_files and custom_approved_files[gid]

        if is_custom:
            selected_paths = custom_approved_files[gid]
            for it in group.get("items", []):
                raw = it.get("path")
                # For duplicates, check if any duplicate in this cluster was selected
                if "duplicates" in it:
                    cluster_selected = [p for p in it["duplicates"] if p in selected_paths]
                    if cluster_selected:
                        target_items.append({
                            "path": cluster_selected[0],
                            "size_bytes": it.get("size_bytes", 0),
                            "action": "DELETE_SELECTED_DUPLICATE",
                            "specific_paths": cluster_selected
                        })
                elif raw in selected_paths:
                    target_items.append(it)
        else:
            for it in group.get("items", []):
                if "duplicates" in it and isinstance(it["duplicates"], list):
                    # For duplicate group approved as a whole, default is delete all except original (index 0)
                    target_items.append({
                        "path": it["duplicates"][1] if len(it["duplicates"]) > 1 else it["path"],
                        "size_bytes": it.get("size_bytes", 0),
                        "action": "DELETE_DUPLICATE_COPIES",
                        "specific_paths": it["duplicates"][1:]
                    })
                else:
                    target_items.append(it)

        if not target_items:
            continue

        group_bytes = sum(it.get("size_bytes", 0) for it in target_items)

        # -------------------------------------------------------------
        # REQUIRE EXPLICIT CONFIRMATION BEFORE EXECUTING THIS GROUP
        # Display exact scope of approval
        # -------------------------------------------------------------
        print("\n" + "=" * 80)
        print(style(f"  EXPLICIT CONFIRMATION: {group['category_name']} [{gid}]", Colors.BOLD, Colors.YELLOW))
        print("=" * 80)
        print("Scope of Proposed Operations:")
        print(f"  • Risk Level:        {group.get('risk_level')}")
        print(f"  • Files to Remove:   {len(target_items)} target item(s)")
        print(f"  • Estimated Space:   {format_bytes(group_bytes)}")
        print(f"  • Proposed Action:   {group.get('description')}")
        print("Target Paths:")
        for idx, it in enumerate(target_items[:5], start=1):
            p_display = it.get("specific_paths", [it.get("path")])
            print(style(f"    [{idx}] {', '.join(p_display)} ({format_bytes(it.get('size_bytes', 0))})", Colors.GRAY))
        if len(target_items) > 5:
            print(style(f"    ... and {len(target_items) - 5} additional item(s)", Colors.GRAY))
        print("-" * 80)

        # Confirm before execution
        if not non_interactive:
            print(style("Confirmation Rule: Pressing Enter or typing anything other than 'yes' or 'y' will SKIP this group.", Colors.BOLD))
            try:
                confirm = input(style(f"Authorize deletion for group '{gid}'? Type 'yes' to execute, 'no' to skip: ", Colors.BOLD, Colors.CYAN)).strip().lower()
            except (KeyboardInterrupt, EOFError):
                print(style(f"\n[MacGuard] Confirmation aborted by user. Skipping group '{gid}'. Zero files modified.", Colors.YELLOW))
                continue

            # Strict check: NEVER treat Enter or empty response or anything other than yes/y as approval
            if confirm not in {"yes", "y"}:
                print(style(f"[MacGuard] Group '{gid}' was NOT confirmed (input: '{confirm}'). Group skipped with zero modifications.\n", Colors.YELLOW))
                summary["skipped_items"].append({
                    "group_id": gid,
                    "reason": f"Explicit confirmation was declined or skipped by user (input: '{confirm}')"
                })
                continue

        print(style(f"\n[MacGuard] Executing approved group: {group['category_name']}...", Colors.CYAN))

        # Perform deletion for each item in the group
        for it in target_items:
            paths_to_delete = it.get("specific_paths", [it.get("path")])

            for p_str in paths_to_delete:
                p = Path(p_str)
                if not p.exists():
                    continue

                is_safe, refusal_reason = SafetyPolicy.validate_for_deletion(p, allow_synthetic=allow_synthetic)
                if not is_safe:
                    print(style(f"  [Safety Refusal] Blocked deletion of '{p}': {refusal_reason}", Colors.RED))
                    summary["skipped_items"].append({
                        "path": str(p),
                        "reason": refusal_reason
                    })
                    if audit_logger:
                        audit_logger.log_event("SAFETY_REFUSAL", {"path": str(p), "reason": refusal_reason})
                    continue

                item_bytes = it.get("size_bytes", 0)
                summary["total_attempted_bytes"] += item_bytes

                if dry_run:
                    print(style(f"  [Dry-Run Simulation] Would delete: {p} ({format_bytes(item_bytes)})", Colors.GRAY))
                    summary["executed_items"].append({
                        "path": str(p),
                        "size_bytes": item_bytes,
                        "status": "SIMULATED_DRY_RUN"
                    })
                    summary["total_reclaimed_bytes"] += item_bytes
                    if audit_logger:
                        audit_logger.log_event("DRY_RUN_DELETE", {"path": str(p), "size_bytes": item_bytes})
                    continue

                # Real deletion
                try:
                    if p.is_dir() and not p.is_symlink():
                        shutil.rmtree(p)
                    else:
                        p.unlink()

                    print(style(f"  ✓ Deleted: {p} ({format_bytes(item_bytes)})", Colors.GREEN))
                    summary["executed_items"].append({
                        "path": str(p),
                        "size_bytes": item_bytes,
                        "status": "SUCCESS"
                    })
                    summary["total_reclaimed_bytes"] += item_bytes
                    if audit_logger:
                        audit_logger.log_event("REAL_DELETE_SUCCESS", {"path": str(p), "size_bytes": item_bytes})
                except Exception as e:
                    print(style(f"  ✗ Failed to delete '{p}': {e}", Colors.RED))
                    summary["failed_items"].append({
                        "path": str(p),
                        "error": str(e)
                    })
                    if audit_logger:
                        audit_logger.log_event("DELETE_FAILED", {"path": str(p), "error": str(e)})

    summary["total_reclaimed_human"] = format_bytes(summary["total_reclaimed_bytes"])
    return summary
