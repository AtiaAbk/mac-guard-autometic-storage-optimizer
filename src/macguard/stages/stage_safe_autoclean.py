"""
Automatic Safe Cache & Temporary File Cleanup Engine.

Cleans ONLY a predefined allowlist of strictly verified, regenerable,
disposable caches and temporary files.

Safety Guarantees:
1. Exact path match against a hardcoded, verified allowlist.
2. Process liveness check: If an application is currently running, its cache is SKIPPED.
3. Cannot affect personal documents, databases, credentials, or system files.
4. Records exactly what was cleaned and measures verified before-and-after storage.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Set, Optional

from macguard.safety import SafetyPolicy
from macguard.utils.disk import get_path_detailed_size, format_bytes, get_disk_usage
from macguard.utils.system import run_cmd
from macguard.utils.audit import AuditLogger
from macguard.utils.ui import Colors, style

def get_running_process_names() -> Set[str]:
    """Retrieve set of active process command names."""
    rc, stdout, _ = run_cmd(["ps", "-A", "-o", "comm"], timeout=5)
    if rc == 0 and stdout:
        names = set()
        for line in stdout.splitlines():
            line = line.strip()
            if line:
                names.add(Path(line).name.lower())
                names.add(line.lower())
        return names
    return set()

def is_process_running(proc_names: List[str], running_procs: Set[str]) -> Tuple[bool, Optional[str]]:
    """Checks if any of the given process names are active."""
    for proc in proc_names:
        proc_lower = proc.lower()
        for active in running_procs:
            if proc_lower in active:
                return True, proc
    return False, None

# Predefined Strict Allowlist of Verified Disposable Targets
# Every rule specifies the exact target, whether it is regenerable, and what processes must NOT be running.
SAFE_AUTOCLEAN_ALLOWLIST = [
    {
        "id": "apple_helpd_cache",
        "name": "Apple Help Viewer Disposable Cache",
        "category": "SYSTEM_DISPOSABLE_CACHE",
        "path_relative": "Library/Caches/com.apple.helpd",
        "required_inactive_processes": ["HelpViewer"],
        "description": "Transient help viewer caches, safely regenerated on demand."
    },
    {
        "id": "homebrew_downloads_cache",
        "name": "Homebrew Downloaded Package Cache",
        "category": "DEVELOPER_PACKAGE_CACHE",
        "path_relative": "Library/Caches/Homebrew/downloads",
        "required_inactive_processes": ["brew"],
        "description": "Completed bottle and formula tarball downloads. Re-downloaded if needed."
    },
    {
        "id": "pip_http_cache",
        "name": "Python Pip HTTP Download Cache",
        "category": "DEVELOPER_PACKAGE_CACHE",
        "path_relative": ".cache/pip/http",
        "required_inactive_processes": ["pip", "pip3"],
        "description": "Cached HTTP wheel responses for pip. Regenerated on next package install."
    },
    {
        "id": "cocoapods_downloads_cache",
        "name": "CocoaPods Release Download Cache",
        "category": "DEVELOPER_PACKAGE_CACHE",
        "path_relative": "Library/Caches/CocoaPods/Pods/Release",
        "required_inactive_processes": ["pod"],
        "description": "Unpacked pod release tarballs. Regenerated automatically by pod install."
    },
    {
        "id": "npm_cacache",
        "name": "NPM / Yarn Package Content Cache",
        "category": "DEVELOPER_PACKAGE_CACHE",
        "path_relative": ".npm/_cacache",
        "required_inactive_processes": ["npm", "yarn", "pnpm"],
        "description": "NPM package download cache. Automatically regenerated."
    },
    {
        "id": "quicklook_thumbnails",
        "name": "QuickLook Thumbnail Cache",
        "category": "SYSTEM_DISPOSABLE_CACHE",
        "path_relative": "Library/Caches/com.apple.QuickLook.thumbnailcache",
        "required_inactive_processes": ["quicklookd"],
        "description": "Transient icon and file preview thumbnails, recreated by Finder when browsing."
    },
    {
        "id": "chrome_browser_cache",
        "name": "Google Chrome Web Cache",
        "category": "BROWSER_CACHE",
        "path_relative": "Library/Caches/Google/Chrome/Default/Cache",
        "required_inactive_processes": ["Google Chrome", "Google Chrome Helper"],
        "description": "Downloaded web page assets, images, and scripts. Re-downloaded during browsing."
    },
    {
        "id": "safari_browser_cache",
        "name": "Apple Safari Web Page Cache",
        "category": "BROWSER_CACHE",
        "path_relative": "Library/Caches/com.apple.Safari",
        "required_inactive_processes": ["Safari", "SafariTechnologyPreview"],
        "description": "Safari browser temporary web caches. Rebuilt when browsing."
    }
]

def execute_safe_autoclean(
    base_dir: Optional[Path] = None,
    dry_run: bool = False,
    allow_synthetic: bool = False,
    audit_logger: Optional[AuditLogger] = None
) -> Dict[str, Any]:
    """
    Executes automatic safe cleanup against only the predefined allowlist.
    Checks process liveness and enforces strict safety policy.
    """
    user_home = base_dir if base_dir else Path.home()
    running_procs = get_running_process_names()

    initial_disk = get_disk_usage(user_home)

    summary: Dict[str, Any] = {
        "status": "COMPLETED",
        "dry_run": dry_run,
        "eligible_rules_evaluated": len(SAFE_AUTOCLEAN_ALLOWLIST),
        "cleaned_items": [],
        "skipped_items": [],
        "failed_items": [],
        "total_apparent_bytes_cleaned": 0,
        "total_allocated_bytes_cleaned": 0,
        "total_cleaned_human": "0 B",
        "initial_free_bytes": initial_disk.get("free_bytes", 0),
        "final_free_bytes": 0,
        "verified_disk_gain_bytes": 0,
        "verified_disk_gain_human": "0 B"
    }

    print(style("\n  [Automatic Safe Cache Cleanup: Predefined Allowlist Verification]", Colors.CYAN, Colors.BOLD))

    for rule in SAFE_AUTOCLEAN_ALLOWLIST:
        rule_id = rule["id"]
        target_path = user_home / rule["path_relative"]

        if not target_path.exists():
            continue

        # 1. Process Liveness Check: Is app running?
        proc_running, active_proc = is_process_running(rule["required_inactive_processes"], running_procs)
        if proc_running:
            skip_msg = f"Skipped '{rule['name']}': Process '{active_proc}' is actively running."
            print(style(f"  • {skip_msg}", Colors.YELLOW))
            summary["skipped_items"].append({
                "rule_id": rule_id,
                "path": str(target_path),
                "reason": skip_msg
            })
            continue

        # 2. Strict Safety Policy Check
        is_safe, refusal_reason = SafetyPolicy.validate_for_deletion(target_path, allow_synthetic=allow_synthetic)
        if not is_safe:
            print(style(f"  • Safety refusal for '{target_path}': {refusal_reason}", Colors.RED))
            summary["skipped_items"].append({
                "rule_id": rule_id,
                "path": str(target_path),
                "reason": refusal_reason
            })
            continue

        # 3. Calculate target apparent and allocated space
        app_bytes, alloc_bytes, count = get_path_detailed_size(target_path)
        if app_bytes == 0 and alloc_bytes == 0:
            continue

        summary["total_apparent_bytes_cleaned"] += app_bytes
        summary["total_allocated_bytes_cleaned"] += alloc_bytes

        if dry_run:
            print(style(f"  [Dry-Run Auto-Clean] Would clean: {rule['name']} ({format_bytes(app_bytes)}) -> {target_path}", Colors.GRAY))
            summary["cleaned_items"].append({
                "rule_id": rule_id,
                "name": rule["name"],
                "path": str(target_path),
                "apparent_bytes": app_bytes,
                "allocated_bytes": alloc_bytes,
                "file_count": count,
                "status": "SIMULATED_DRY_RUN"
            })
            if audit_logger:
                audit_logger.log_event("AUTOCLEAN_DRY_RUN", {"rule": rule_id, "path": str(target_path), "bytes": app_bytes})
            continue

        # 4. Perform Real Safe Cleanup
        try:
            if target_path.is_dir() and not target_path.is_symlink():
                shutil.rmtree(target_path)
            else:
                target_path.unlink()

            print(style(f"  ✓ Automatically Cleaned: {rule['name']} ({format_bytes(app_bytes)})", Colors.GREEN))
            summary["cleaned_items"].append({
                "rule_id": rule_id,
                "name": rule["name"],
                "path": str(target_path),
                "apparent_bytes": app_bytes,
                "allocated_bytes": alloc_bytes,
                "file_count": count,
                "status": "CLEANED_VERIFIED"
            })
            if audit_logger:
                audit_logger.log_event("AUTOCLEAN_SUCCESS", {"rule": rule_id, "path": str(target_path), "bytes": app_bytes})
        except Exception as e:
            err_msg = f"Failed to clean '{target_path}': {e}"
            print(style(f"  ✗ {err_msg}", Colors.RED))
            summary["failed_items"].append({
                "rule_id": rule_id,
                "path": str(target_path),
                "error": str(e)
            })
            if audit_logger:
                audit_logger.log_event("AUTOCLEAN_FAILED", {"rule": rule_id, "path": str(target_path), "error": str(e)})

    # Final storage verification after autoclean
    final_disk = get_disk_usage(user_home)
    summary["final_free_bytes"] = final_disk.get("free_bytes", 0)
    gain = max(0, summary["final_free_bytes"] - summary["initial_free_bytes"])
    summary["verified_disk_gain_bytes"] = gain
    summary["verified_disk_gain_human"] = format_bytes(gain)
    summary["total_cleaned_human"] = format_bytes(summary["total_apparent_bytes_cleaned"])

    if not summary["cleaned_items"]:
        print(style("  • No allowlist cache items required automatic cleanup.", Colors.GRAY))

    return summary
