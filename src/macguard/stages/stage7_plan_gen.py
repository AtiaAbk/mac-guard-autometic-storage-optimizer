"""
Stage 7: Consolidated Report and Proposed-Action Plan Generator.

Produces:
1. Machine-readable JSON dictionary
2. Human-readable Markdown report
Consolidates environment, storage scan, VMware findings, health/battery stats,
classification groups, and potential non-double-counted savings.
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
    savings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Builds the consolidated plan and report structure.
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    iso_timestamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    report_data = {
        "metadata": {
            "version": "2.0.0",
            "mission_timestamp": timestamp,
            "iso_timestamp": iso_timestamp,
            "trigger_mode": "user_explicit_on_demand",
            "is_purely_on_demand": env_info.get("schedule_validation", {}).get("is_purely_on_demand", True)
        },
        "environment": env_info,
        "storage_scan": storage_scan,
        "vmware_findings": vmware_scan,
        "health_and_performance": health_perf,
        "classification_groups": groups,
        "potential_savings": savings,
        "execution_summary": {
            "executed": False,
            "approved_groups": [],
            "rejected_groups": [],
            "skipped_groups": [],
            "failed_operations": [],
            "actual_savings_bytes": 0,
            "actual_savings_human": "0 B"
        }
    }

    # Generate Markdown representation
    md_lines = [
        f"# MacGuard Mission Consolidated Report",
        f"**Date:** {timestamp} | **Trigger:** Exclusively User-Triggered On-Demand",
        f"",
        f"## 1. Environment & Configuration Inspection",
        f"- **OS:** macOS {env_info.get('os', {}).get('ProductVersion', 'Unknown')} (Build {env_info.get('os', {}).get('BuildVersion', 'Unknown')})",
        f"- **Hardware:** {env_info.get('hardware', {}).get('cpu_model', 'Apple Silicon')} ({env_info.get('hardware', {}).get('cpu_cores', 1)} cores, {env_info.get('hardware', {}).get('ram_gb', 0)} GB RAM)",
        f"- **SIP Status:** {env_info.get('sip', 'Unknown')}",
        f"- **Initial Root Storage:** Free {env_info.get('storage', {}).get('root', {}).get('free_human', 'N/A')} / {env_info.get('storage', {}).get('root', {}).get('total_human', 'N/A')} ({env_info.get('storage', {}).get('root', {}).get('pct_used', 0)}% used)",
        f"- **Automated Schedulers Check:** {'PASSED (Zero background schedulers/daemons active)' if env_info.get('schedule_validation', {}).get('is_purely_on_demand') else 'WARNING: Background schedulers found'}",
        f"",
        f"## 2. Health & Performance Assessment",
    ]

    batt = health_perf.get("battery", {})
    if batt.get("has_battery"):
        cycle_str = f", {batt['cycle_count']} cycles" if batt.get("cycle_count") else ""
        md_lines.append(f"- **Battery:** {batt.get('percentage')}% ({batt.get('status')}) on {batt.get('power_source')}{cycle_str} [Condition: {batt.get('condition')}]")
    else:
        md_lines.append(f"- **Battery:** No internal battery detected (Desktop Mac)")

    md_lines.append(f"- **CPU Load Averages:** {health_perf.get('cpu', {}).get('load_averages', [])}")
    md_lines.append(f"- **Memory Pressure:** {health_perf.get('memory', {}).get('pressure_level', 'Normal')}")
    if health_perf.get("login_items"):
        md_lines.append(f"- **Active Login Items / Agents:** {len(health_perf['login_items'])} detected")

    if health_perf.get("recommendations"):
        md_lines.append(f"\n### Recommendations:")
        for rec in health_perf["recommendations"]:
            md_lines.append(f"- {rec}")

    md_lines.extend([
        f"",
        f"## 3. Storage Analysis by Category",
        f"- **Disposable Application Caches:** {len(storage_scan.get('caches', []))} targets",
        f"- **Application & User Logs:** {len(storage_scan.get('logs', []))} files",
        f"- **Old Installers (.dmg / .pkg):** {len(storage_scan.get('installers', []))} files",
        f"- **Duplicate Candidates:** {len(storage_scan.get('duplicates', []))} sets",
        f"- **Developer Artifacts:** {len(storage_scan.get('developer_artifacts', []))} items",
        f"- **Local AI Models (Ollama/HF/LM Studio):** {len(storage_scan.get('local_ai_models', []))} items",
        f"- **Docker Storage:** {storage_scan.get('docker_storage', {}).get('status', 'N/A')}",
        f"",
        f"## 4. VMware Virtual Machine Inspection (Strictly Protected)",
    ])

    vms = vmware_scan.get("discovered_vms", [])
    if vms:
        md_lines.append(f"Discovered {len(vms)} VM bundle(s) utilizing {vmware_scan.get('total_vm_storage_human', '0 B')}:")
        for vm in vms:
            md_lines.append(
                f"- **{vm['display_name']}** (`{vm['guest_os']}`): {vm['size_human']}, "
                f"{vm['snapshots_count']} snapshots, running: {vm['is_running']} *(Protected - No changes)*"
            )
    else:
        md_lines.append("- No VMware virtual machine bundles found in standard user paths.")

    md_lines.extend([
        f"",
        f"## 5. Potential Storage Savings (No Double-Counting)",
        f"- **Gross Potential:** {savings.get('gross_potential_human', '0 B')}",
        f"- **Net Realistic Potential:** {savings.get('net_potential_human', '0 B')}",
        f"- **Recommended Safe Savings (Low-Risk Disposable only):** {savings.get('recommended_savings_human', '0 B')}",
        f"",
        f"## 6. Proposed Action Plan (Grouped for Consolidated Review)",
        f"| # | Group ID | Category | Risk Level | Items | Estimated Size | Recommendation |",
        f"|---|---|---|---|---|---|---|"
    ])

    for idx, grp in enumerate(groups, start=1):
        md_lines.append(
            f"| {idx} | `{grp['group_id']}` | {grp['category_name']} | {grp['risk_level']} | "
            f"{grp['file_count']} | {grp['total_human']} | {grp['recommended_action']} |"
        )

    md_report = "\n".join(md_lines)
    report_data["markdown_report"] = md_report
    return report_data
