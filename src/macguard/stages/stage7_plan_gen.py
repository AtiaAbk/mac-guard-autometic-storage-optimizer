"""
Stage 7: Comprehensive Markdown & JSON Report Generator.

Generates:
1. Machine-readable JSON dictionary
2. Beautiful human-readable Markdown report
Includes:
- Initial & final available disk space
- Storage breakdown by directory & category
- Automatic safe cache cleanup summary (allowlist only)
- Largest files and directories (ranked with apparent vs allocated size)
- Old installer candidates & duplicate candidates (original vs copies)
- Deep VMware host-side vs guest findings
- Inaccessible/protected locations with reasons
- Potential vs actual storage savings
- Performance & battery health recommendations
"""

from __future__ import annotations

import json
import time
from typing import Dict, Any, List
from macguard.utils.disk import format_bytes

def generate_plan_and_report(
    env_info: Dict[str, Any],
    storage_scan: Dict[str, Any],
    vmware_scan: Dict[str, Any],
    health_perf: Dict[str, Any],
    groups: List[Dict[str, Any]],
    savings: Dict[str, Any],
    autoclean_summary: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Builds the consolidated plan and report structure.
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    iso_timestamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    report_data = {
        "metadata": {
            "version": "2.2.0",
            "mission_timestamp": timestamp,
            "iso_timestamp": iso_timestamp,
            "command": "macguard deep-clean",
            "trigger_mode": "user_explicit_on_demand",
            "is_purely_on_demand": env_info.get("schedule_validation", {}).get("is_purely_on_demand", True)
        },
        "environment": env_info,
        "storage_scan": storage_scan,
        "vmware_findings": vmware_scan,
        "health_and_performance": health_perf,
        "automatic_safe_cleanup": autoclean_summary or {},
        "classification_groups": groups,
        "potential_savings": savings,
        "execution_summary": {
            "executed": False,
            "approved_groups": [],
            "rejected_groups": [],
            "skipped_items": [],
            "failed_items": [],
            "actual_savings_bytes": 0,
            "actual_savings_human": "0 B"
        }
    }

    # Build detailed Markdown report
    root_storage = env_info.get("storage", {}).get("root", {})
    md = [
        "# MacGuard Deep Cleaning & Storage Intelligence Report",
        f"**Date:** {timestamp} | **Execution Command:** `macguard deep-clean` | **Mode:** Strictly On-Demand",
        "",
        "## 1. System Environment & Validation",
        f"- **Operating System:** {env_info.get('os', {}).get('ProductName', 'macOS')} {env_info.get('os', {}).get('ProductVersion', '')} (Build {env_info.get('os', {}).get('BuildVersion', '')})",
        f"- **Hardware Architecture:** {env_info.get('hardware', {}).get('cpu_model', 'Apple Silicon')} ({env_info.get('hardware', {}).get('cpu_cores', 1)} cores, {env_info.get('hardware', {}).get('ram_gb', 0)} GB RAM)",
        f"- **SIP Status:** {env_info.get('sip', 'Enabled')}",
        f"- **Initial Root Storage:** Free {root_storage.get('free_human', 'N/A')} of {root_storage.get('total_human', 'N/A')} ({root_storage.get('pct_used', 0)}% used)",
        f"- **Scheduler Validation:** {'PASSED: Zero background launchd daemons or automatic jobs active' if env_info.get('schedule_validation', {}).get('is_purely_on_demand') else 'WARNING: Background schedulers found'}",
        "",
        "## 2. Automatic Safe Cache Cleanup (Predefined Allowlist)",
    ]

    if autoclean_summary and autoclean_summary.get("cleaned_items"):
        md.append(f"Automatically and safely cleaned {len(autoclean_summary['cleaned_items'])} allowlist item(s) (Processes verified inactive):")
        for item in autoclean_summary["cleaned_items"]:
            md.append(f"- **{item['name']}**: Cleaned {format_bytes(item['apparent_bytes'])} (`{item['path']}`)")
        md.append(f"- **Verified Space Gained via Auto-Clean:** {autoclean_summary.get('verified_disk_gain_human', '0 B')}")
    else:
        md.append("- No eligible allowlist caches required automatic cleanup (or associated application processes were actively running).")

    if autoclean_summary and autoclean_summary.get("skipped_items"):
        md.append("\n### Skipped Auto-Clean Targets (Safety Guarantees):")
        for sk in autoclean_summary["skipped_items"]:
            md.append(f"- {sk.get('reason', 'Skipped')}")

    md.extend([
        "",
        "## 3. Storage Analysis by Category",
        "### User Directories Breakdown:",
    ])

    for dir_name, dir_info in storage_scan.get("user_directories", {}).items():
        md.append(f"- **{dir_name}:** Apparent {dir_info.get('apparent_human')} (Allocated on Disk: {dir_info.get('allocated_human')}), {dir_info.get('file_count')} files")

    md.extend([
        "",
        "### Discovered Artifacts & Candidates:",
        f"- **Application Caches:** {len(storage_scan.get('caches', []))} item(s)",
        f"- **Web Browser Caches:** {len(storage_scan.get('browser_caches', []))} item(s)",
        f"- **Diagnostic Logs & Crash Reports:** {len(storage_scan.get('logs', []))} log(s), {len(storage_scan.get('crash_reports', []))} crash report bundle(s)",
        f"- **Old Installers (.dmg, .pkg, .iso, .zip):** {len(storage_scan.get('installers', []))} candidate(s)",
        f"- **Duplicate File Candidates:** {len(storage_scan.get('duplicates', []))} cluster(s)",
        f"- **Developer Build Caches:** {len(storage_scan.get('developer_artifacts', []))} target(s)",
        f"- **Local AI Models:** {len(storage_scan.get('local_ai_models', []))} repository(s)",
        f"- **Docker Storage:** {storage_scan.get('docker_storage', {}).get('status', 'N/A')}",
        "",
        "## 4. Top Largest Files (Ranked by Storage)",
        "| Rank | File Name | Extension | Apparent Size | Allocated Space | Path |",
        "|:---:|:---|:---:|:---|:---|:---|"
    ])

    for rk, f in enumerate(storage_scan.get("large_files", [])[:15], start=1):
        md.append(f"| {rk} | `{f.get('name')}` | `{f.get('extension')}` | {f.get('apparent_human')} | {f.get('allocated_human')} | `{f.get('path')}` |")

    md.extend([
        "",
        "## 5. VMware Fusion Deep Storage Findings (Strictly Protected)",
    ])

    vms = vmware_scan.get("discovered_vms", [])
    if vms:
        md.append(f"Discovered {len(vms)} VM bundle(s) utilizing {vmware_scan.get('total_host_storage_human', '0 B')} host disk storage:")
        for vm in vms:
            md.append(
                f"### VM: {vm['display_name']} (Guest OS: `{vm['guest_os']}`)\n"
                f"- **Bundle Location:** `{vm['bundle_path']}`\n"
                f"- **Host Disk Space:** Apparent {vm['apparent_human']} | Allocated {vm['allocated_human']}\n"
                f"- **Virtual Disks:** {len(vm['virtual_disks'])} `.vmdk` disk(s)\n"
                f"- **Snapshot Chains:** {vm['snapshot_chains']['snapshot_count']} snapshot(s), {vm['snapshot_chains']['delta_disks_count']} delta disk(s) utilizing {vm['snapshot_chains']['delta_storage_human']}\n"
                f"- **Running State:** {'Running (Active)' if vm['is_running'] else 'Powered Off'}\n"
                f"- **Guest Filesystem Status:** {vm['guest_os_status']['inspection_mode']} *(Kept strictly separate from host per policy)*\n"
                f"- **Policy:** Marked `PROTECTED`. Disks and snapshots are never automatically modified or deleted."
            )
    else:
        md.append("- No VMware Fusion virtual machine bundles discovered in standard or Spotlight paths.")

    md.extend([
        "",
        "## 6. Duplicate File Candidates (Original vs Copies)",
    ])

    dups = storage_scan.get("duplicates", [])
    if dups:
        for idx, d in enumerate(dups, start=1):
            md.append(
                f"- **Cluster #{idx}** ({d['total_copies']} copies, {d['size_human']} each, Recoverable: {d['potential_savings_human']}):\n"
                f"  - **Original (KEEP):** `{d['original_path']}`\n"
                f"  - **Candidate Copy:** `{', '.join(d['duplicate_paths'])}`"
            )
    else:
        md.append("- No duplicate files exceeding the minimum threshold detected.")

    md.extend([
        "",
        "## 7. Storage Savings Calculation (No Double-Counting)",
        f"- **Gross Potential:** {savings.get('gross_potential_human', '0 B')}",
        f"- **Net Realistic Potential:** {savings.get('net_potential_human', '0 B')}",
        f"- **Recommended Safe Savings (Low-Risk only):** {savings.get('recommended_savings_human', '0 B')}",
        "",
        "## 8. Proposed Optional Action Plan (Requires User Approval)",
        "| # | Group ID | Category | Risk Tier | Items | Potential Recovery | Recommendation |",
        "|---|---|---|---|---|---|---|"
    ])

    for idx, grp in enumerate(groups, start=1):
        md.append(
            f"| {idx} | `{grp['group_id']}` | {grp['category_name']} | {grp['risk_level']} | "
            f"{grp['file_count']} | {grp['total_human']} | {grp['recommended_action']} |"
        )

    if storage_scan.get("inaccessible_locations"):
        md.extend([
            "",
            "## 9. Inaccessible & Protected Locations",
        ])
        for inacc in storage_scan["inaccessible_locations"]:
            p = inacc.get("path", inacc) if isinstance(inacc, dict) else inacc
            r = inacc.get("reason", "Restricted permissions") if isinstance(inacc, dict) else "Restricted"
            md.append(f"- `{p}`: {r}")

    report_data["markdown_report"] = "\n".join(md)
    return report_data
