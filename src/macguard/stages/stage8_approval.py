"""
Stage 8: Interactive Consolidated Approval and File-by-File Review Interface.

Features:
- Live terminal action proposal presentation
- Grouped category approvals & rejections
- Granular per-file review for installers (.dmg/.pkg) and duplicate candidates
- Explicit confirmation enforcement: Never treats Enter, empty input, or Ctrl+C as approval
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Tuple

from macguard.utils.ui import Colors, style, print_header, print_divider
from macguard.utils.disk import format_bytes

def display_plan_table(
    groups: List[Dict[str, Any]],
    approved_group_ids: Set[str],
    custom_approved_files: Dict[str, Set[str]]
) -> None:
    """Displays the styled consolidated action proposal table."""
    print_divider("CONSOLIDATED ACTION PROPOSAL")
    print(
        f"{style('#', Colors.BOLD):<4} "
        f"{style('STATUS', Colors.BOLD):<14} "
        f"{style('RISK', Colors.BOLD):<10} "
        f"{style('ITEMS', Colors.BOLD):<8} "
        f"{style('RECOVERABLE', Colors.BOLD):<13} "
        f"{style('CATEGORY', Colors.BOLD)}"
    )
    print(style("─" * 80, Colors.GRAY))

    for idx, grp in enumerate(groups, start=1):
        gid = grp["group_id"]
        risk = grp.get("risk_level", "LOW")

        # Colorize risk
        if risk == "LOW":
            risk_badge = style("LOW", Colors.GREEN)
        elif risk == "MEDIUM":
            risk_badge = style("MEDIUM", Colors.YELLOW)
        elif risk == "HIGH":
            risk_badge = style("HIGH", Colors.MAGENTA)
        else:
            risk_badge = style("PROTECTED", Colors.CYAN)

        # Status badge
        if grp.get("risk_level") == "PROTECTED":
            status_badge = style("[PROTECTED]", Colors.GRAY)
        elif gid in custom_approved_files and custom_approved_files[gid]:
            cnt = len(custom_approved_files[gid])
            total_items = len(grp.get("items", []))
            status_badge = style(f"[CUSTOM {cnt}/{total_items}]", Colors.CYAN)
        elif gid in approved_group_ids:
            status_badge = style("[APPROVED]", Colors.GREEN, Colors.BOLD)
        else:
            status_badge = style("[REJECTED]", Colors.RED)

        # Calculate displayed size
        if gid in custom_approved_files and custom_approved_files[gid]:
            approved_paths = custom_approved_files[gid]
            custom_bytes = 0
            for it in grp.get("items", []):
                if it.get("path") in approved_paths:
                    custom_bytes += it.get("size_bytes", 0)
            sz_str = format_bytes(custom_bytes)
            items_str = str(len(approved_paths))
        else:
            sz_str = grp.get("total_human", "0 B")
            items_str = str(grp.get("file_count", 0))

        print(f"[{idx:<2}] {status_badge:<23} {risk_badge:<19} {items_str:<8} {sz_str:<13} {style(grp['category_name'], Colors.BOLD)}")
        print(style(f"     ID: {gid} | Action: {grp.get('recommended_action')} | {grp.get('description')}", Colors.GRAY))

    print(style("─" * 80, Colors.GRAY))

def review_installer_files(group: Dict[str, Any], currently_approved: Set[str]) -> Set[str]:
    """Interactive file-by-file review mode for installer candidates."""
    items = group.get("items", [])
    if not items:
        print("\nNo installer items to review.")
        return currently_approved

    approved = set(currently_approved)

    while True:
        print("\n" + "=" * 80)
        print(style(f"  FILE REVIEW: {group['category_name']} ({len(items)} files)", Colors.BOLD, Colors.CYAN))
        print("=" * 80)
        print(f"{'#':<4} {'STATUS':<12} {'SIZE':<11} {'AGE':<10} {'INSTALLER NAME / PATH'}")
        print("-" * 80)

        for i, it in enumerate(items, start=1):
            p = it.get("path", "")
            status = style("[APPROVED]", Colors.GREEN) if p in approved else style("[KEEP]", Colors.GRAY)
            sz = it.get("size_human", format_bytes(it.get("size_bytes", 0)))
            age = f"{it.get('age_days', 0)}d old"
            name = it.get("name", Path(p).name)
            print(f"[{i:<2}] {status:<21} {sz:<11} {age:<10} {style(name, Colors.BOLD)}")
            print(style(f"     Path: {p}", Colors.GRAY))

        print("-" * 80)
        print("File Selection Commands:")
        print("  • 'select <#>' (e.g. 'select 1' or 'select 1,2') to mark installer(s) for deletion")
        print("  • 'deselect <#>' to unmark installer(s)")
        print("  • 'select all' to mark all installers")
        print("  • 'select none' to clear selection")
        print("  • 'done' to save selection and return to main proposal menu")

        try:
            cmd = input(style("\nInstallers Review > ", Colors.BOLD)).strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nReturning without saving additional installer changes.")
            return approved

        if not cmd:
            print("Empty input. Type 'done' to return or 'select <#>' to toggle.")
            continue

        if cmd in {"done", "back", "save"}:
            break
        elif cmd == "select all":
            for it in items:
                approved.add(it["path"])
            print("-> Marked all installers for deletion.")
        elif cmd == "select none":
            approved.clear()
            print("-> Cleared all installer selections.")
        elif cmd.startswith("select "):
            parts = cmd.split(None, 1)[1].replace(",", " ").split()
            for part in parts:
                if part.isdigit():
                    num = int(part)
                    if 1 <= num <= len(items):
                        approved.add(items[num - 1]["path"])
                        print(f"-> Marked for deletion: {items[num - 1]['name']}")
                    else:
                        print(f"Invalid index: {num}")
        elif cmd.startswith("deselect "):
            parts = cmd.split(None, 1)[1].replace(",", " ").split()
            for part in parts:
                if part.isdigit():
                    num = int(part)
                    if 1 <= num <= len(items):
                        approved.discard(items[num - 1]["path"])
                        print(f"-> Unmarked: {items[num - 1]['name']}")
                    else:
                        print(f"Invalid index: {num}")
        else:
            print("Unrecognized command. Type 'select <#>', 'deselect <#>', or 'done'.")

    return approved

def review_duplicate_files(group: Dict[str, Any], currently_approved: Set[str]) -> Set[str]:
    """Interactive review mode for duplicate clusters (guarantees at least 1 file kept)."""
    items = group.get("items", [])
    if not items:
        print("\nNo duplicate clusters to review.")
        return currently_approved

    approved = set(currently_approved)

    while True:
        print("\n" + "=" * 80)
        print(style(f"  FILE REVIEW: Duplicate File Sets ({len(items)} clusters)", Colors.BOLD, Colors.CYAN))
        print("=" * 80)

        for cluster_idx, it in enumerate(items, start=1):
            dup_paths = it.get("duplicates", [])
            sz = it.get("size_human", "N/A")
            print(style(f"\n[Cluster #{cluster_idx}] Matching SHA256 ({len(dup_paths)} identical copies, {sz} each):", Colors.BOLD))

            for f_idx, f_path in enumerate(dup_paths, start=1):
                is_del = f_path in approved
                status = style("[DELETE CANDIDATE]", Colors.RED) if is_del else style("[KEEP ORIGINAL]", Colors.GREEN)
                print(f"  ({f_idx}) {status} {f_path}")

        print("\n" + "-" * 80)
        print("Duplicate Selection Commands:")
        print("  • 'delete <cluster>.<file>' (e.g. 'delete 1.2') to mark specific copy for deletion")
        print("  • 'keep <cluster>.<file>' (e.g. 'keep 1.2') to keep that specific copy")
        print("  • 'default' to automatically mark all except the first copy in each set")
        print("  • 'keep all' to unmark all duplicates (delete none)")
        print("  • 'done' to save selection and return to main proposal menu")

        try:
            cmd = input(style("\nDuplicates Review > ", Colors.BOLD)).strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nReturning without saving duplicate changes.")
            return approved

        if not cmd:
            print("Empty input. Type 'done' to return or 'delete <cluster>.<file>'.")
            continue

        if cmd in {"done", "back", "save"}:
            break
        elif cmd == "default":
            # Mark all except the first file in each cluster
            for it in items:
                dup_paths = it.get("duplicates", [])
                for p in dup_paths[1:]:
                    approved.add(p)
            print("-> Selected default: First file in each set kept, secondary copies marked for deletion.")
        elif cmd in {"keep all", "clear"}:
            approved.clear()
            print("-> Cleared all duplicate deletion selections.")
        elif cmd.startswith("delete "):
            target = cmd.split(None, 1)[1].strip()
            try:
                c_str, f_str = target.split(".")
                c_num, f_num = int(c_str), int(f_str)
                if 1 <= c_num <= len(items):
                    cluster = items[c_num - 1].get("duplicates", [])
                    if 1 <= f_num <= len(cluster):
                        # Ensure we don't mark all files in the cluster (must keep at least 1!)
                        marked_in_cluster = [p for p in cluster if p in approved or p == cluster[f_num - 1]]
                        if len(marked_in_cluster) == len(cluster):
                            print(style("Warning: You cannot delete all copies! At least 1 copy must be kept.", Colors.YELLOW))
                        else:
                            approved.add(cluster[f_num - 1])
                            print(f"-> Marked for deletion: {cluster[f_num - 1]}")
                    else:
                        print(f"Invalid file number: {f_num}")
                else:
                    print(f"Invalid cluster number: {c_num}")
            except ValueError:
                print("Format should be 'delete <cluster>.<file>', e.g. 'delete 1.2'")
        elif cmd.startswith("keep "):
            target = cmd.split(None, 1)[1].strip()
            try:
                c_str, f_str = target.split(".")
                c_num, f_num = int(c_str), int(f_str)
                if 1 <= c_num <= len(items):
                    cluster = items[c_num - 1].get("duplicates", [])
                    if 1 <= f_num <= len(cluster):
                        approved.discard(cluster[f_num - 1])
                        print(f"-> Will KEEP: {cluster[f_num - 1]}")
            except ValueError:
                print("Format should be 'keep <cluster>.<file>', e.g. 'keep 1.2'")
        else:
            print("Unrecognized command.")

    return approved

def review_and_approve(
    groups: List[Dict[str, Any]],
    non_interactive: bool = False,
    auto_approve_groups: Optional[List[str]] = None,
    approve_low_risk: bool = False,
    reject_all: bool = False
) -> Tuple[Set[str], Dict[str, Set[str]]]:
    """
    Consolidated interactive approval interface.
    Returns:
      (approved_group_ids, custom_approved_files)
    """
    approved_group_ids: Set[str] = set()
    custom_approved_files: Dict[str, Set[str]] = {}

    # Handle scripted flags
    if reject_all:
        print("\n[MacGuard] User policy: Reject all proposed modifications. Zero files will be modified.")
        return set(), {}

    if approve_low_risk:
        for grp in groups:
            if grp.get("risk_level") == "LOW" and grp.get("is_selectable", False):
                approved_group_ids.add(grp["group_id"])

    if auto_approve_groups:
        valid_selectable = {g["group_id"] for g in groups if g.get("is_selectable", False)}
        for gid in auto_approve_groups:
            if gid in valid_selectable:
                approved_group_ids.add(gid)

    if non_interactive:
        display_plan_table(groups, approved_group_ids, custom_approved_files)
        return approved_group_ids, custom_approved_files

    # Interactive Loop
    while True:
        display_plan_table(groups, approved_group_ids, custom_approved_files)
        print("\n" + style("Review & Approval Commands:", Colors.BOLD))
        print("  • 'approve <# or id>'       -> Approve entire group (e.g. 'approve 1' or 'approve 1,2')")
        print("  • 'approve low-risk'        -> Approve all low-risk disposable cache groups")
        print("  • 'reject <# or id>'        -> Reject / uncheck group")
        print("  • 'review installers' (or #) -> Inspect and select individual installer files")
        print("  • 'review duplicates' (or #) -> Inspect and select specific duplicate files")
        print("  • 'details <#>'             -> Inspect file list for a group")
        print("  • 'proceed'                 -> Move to confirmation & execution of approved items")
        print("  • 'quit'                    -> Exit safely with zero modifications")
        print(style("  * Note: Pressing Enter with empty input will NEVER approve modifications.", Colors.GRAY))

        try:
            choice = input(style("\nMacGuard Action > ", Colors.BOLD, Colors.CYAN)).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n[MacGuard] Review cancelled by user. Zero files modified.")
            return set(), {}

        # Rule: Never treat Enter, an empty response, or quit as approval
        if not choice:
            print(style("\n[MacGuard] Empty input received. Enter is never treated as approval. No action taken.", Colors.YELLOW))
            continue

        if choice in {"quit", "exit", "cancel", "q"}:
            print("\n[MacGuard] User chose to quit. Zero files modified. Saving report.")
            return set(), {}

        if choice in {"proceed", "execute", "run"}:
            # Combine whole-group approvals and custom file approvals
            active_approved = set(approved_group_ids)
            for gid, files in custom_approved_files.items():
                if files:
                    active_approved.add(gid)

            if not active_approved:
                print(style("\n[MacGuard] No groups or files were approved. Exiting without modifying any data.", Colors.YELLOW))
                return set(), {}

            return active_approved, custom_approved_files

        if choice == "approve low-risk":
            for grp in groups:
                if grp.get("risk_level") == "LOW" and grp.get("is_selectable", False):
                    approved_group_ids.add(grp["group_id"])
            print(style("-> Approved all LOW risk disposable groups.", Colors.GREEN))
            continue

        if choice.startswith("review "):
            target = choice.split(None, 1)[1].strip()
            target_clean = target.rstrip("s")
            matched_grp = None

            if target.isdigit():
                num = int(target)
                if 1 <= num <= len(groups):
                    matched_grp = groups[num - 1]
            else:
                for g in groups:
                    gid_l = g["group_id"].lower()
                    cat_l = g["category_name"].lower()
                    if (target in gid_l or target_clean in gid_l or
                        target in cat_l or target_clean in cat_l or
                        (target in {"dup", "duplicate", "duplicates"} and "duplicate" in gid_l) or
                        (target in {"inst", "installer", "installers"} and "installer" in gid_l)):
                        matched_grp = g
                        break

            if not matched_grp:
                print(f"Could not find group matching '{target}'.")
                continue

            gid = matched_grp["group_id"]
            if gid == "old_installers":
                existing = custom_approved_files.get(gid, set())
                selected = review_installer_files(matched_grp, existing)
                custom_approved_files[gid] = selected
                if selected:
                    approved_group_ids.discard(gid)
                else:
                    custom_approved_files.pop(gid, None)
            elif gid == "duplicate_candidates":
                existing = custom_approved_files.get(gid, set())
                selected = review_duplicate_files(matched_grp, existing)
                custom_approved_files[gid] = selected
                if selected:
                    approved_group_ids.discard(gid)
                else:
                    custom_approved_files.pop(gid, None)
            else:
                print(f"Granular file review is specialized for installers and duplicates. Use 'details {groups.index(matched_grp) + 1}' to view paths.")
            continue

        if choice.startswith("details "):
            target = choice.split(None, 1)[1].strip()
            if target.isdigit():
                num = int(target)
                if 1 <= num <= len(groups):
                    grp = groups[num - 1]
                    print_divider(f"DETAILS: {grp['category_name']}")
                    for it in grp.get("items", [])[:15]:
                        print(f"  • {it.get('name', Path(it.get('path', '')).name)} ({it.get('size_human', 'N/A')})")
                        if "path" in it:
                            print(style(f"    Path: {it['path']}", Colors.GRAY))
                else:
                    print(f"Invalid group number: {num}")
            continue

        if choice.startswith("approve "):
            args = choice.split(None, 1)[1].replace(",", " ").split()
            for arg in args:
                if arg.isdigit():
                    num = int(arg)
                    if 1 <= num <= len(groups):
                        grp = groups[num - 1]
                        if grp.get("is_selectable", False):
                            gid = grp["group_id"]
                            approved_group_ids.add(gid)
                            custom_approved_files.pop(gid, None)
                            print(style(f"-> Approved: {grp['category_name']}", Colors.GREEN))
                        else:
                            print(style(f"-> Group '{grp['category_name']}' is PROTECTED and cannot be approved.", Colors.RED))
                else:
                    matched = [g for g in groups if g["group_id"] == arg]
                    if matched and matched[0].get("is_selectable", False):
                        gid = matched[0]["group_id"]
                        approved_group_ids.add(gid)
                        custom_approved_files.pop(gid, None)
                        print(style(f"-> Approved: {matched[0]['category_name']}", Colors.GREEN))
            continue

        if choice.startswith("reject "):
            args = choice.split(None, 1)[1].replace(",", " ").split()
            for arg in args:
                if arg.isdigit():
                    num = int(arg)
                    if 1 <= num <= len(groups):
                        gid = groups[num - 1]["group_id"]
                        approved_group_ids.discard(gid)
                        custom_approved_files.pop(gid, None)
                        print(style(f"-> Rejected: {groups[num - 1]['category_name']}", Colors.YELLOW))
                else:
                    approved_group_ids.discard(arg)
                    custom_approved_files.pop(arg, None)
                    print(style(f"-> Rejected: {arg}", Colors.YELLOW))
            continue

        print(style("Unrecognized option. Type 'approve <#>', 'review installers', 'review duplicates', 'proceed', or 'quit'.", Colors.YELLOW))
