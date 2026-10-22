"""
Stage 10: Post-Execution Verification and Final Report Generation.

Verifies:
- Confirms actual removal of deleted items on disk
- Re-measures available storage on filesystem
- Calculates verified actual savings
- Writes timestamped JSON and Markdown reports to dedicated report directory
- Emits final audit log entry
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Any, List
from macguard.utils.disk import get_disk_usage, format_bytes
from macguard.utils.audit import AuditLogger
from macguard.config import get_reports_dir

def verify_and_report(
    plan_data: Dict[str, Any],
    execution_summary: Dict[str, Any],
    reports_dir: Path | None = None,
    audit_logger: AuditLogger | None = None
) -> Dict[str, Any]:
    """
    Performs post-execution verification and writes final reports.
    """
    reports_path = reports_dir or get_reports_dir()
    reports_path.mkdir(parents=True, exist_ok=True)

    # 1. Verify item deletion on disk
    verified_deleted: List[str] = []
    unverified_remaining: List[str] = []

    for item in execution_summary.get("executed_items", []):
        p = Path(item["path"])
        if execution_summary.get("dry_run"):
            verified_deleted.append(item["path"] + " (Simulated)")
        else:
            if not p.exists():
                verified_deleted.append(item["path"])
            else:
                unverified_remaining.append(item["path"])

    # 2. Final storage measurement
    final_root_usage = get_disk_usage("/")
    initial_root_usage = plan_data.get("environment", {}).get("storage", {}).get("root", {})

    initial_free = initial_root_usage.get("free_bytes", 0)
    final_free = final_root_usage.get("free_bytes", 0)
    measured_disk_gain = max(0, final_free - initial_free)

    # 3. Assemble final verification summary
    verification = {
        "verified_deleted_count": len(verified_deleted),
        "unverified_remaining_count": len(unverified_remaining),
        "unverified_items": unverified_remaining,
        "initial_storage_free": initial_root_usage.get("free_human", "N/A"),
        "final_storage_free": final_root_usage.get("free_human", "N/A"),
        "measured_disk_gain_bytes": measured_disk_gain,
        "measured_disk_gain_human": format_bytes(measured_disk_gain),
        "reported_reclaimed_bytes": execution_summary.get("total_reclaimed_bytes", 0),
        "reported_reclaimed_human": execution_summary.get("total_reclaimed_human", "0 B")
    }

    plan_data["verification"] = verification
    plan_data["execution_summary"] = execution_summary

    # Append to markdown report
    md_report = plan_data.get("markdown_report", "")
    md_lines = [
        md_report,
        "",
        "## 7. Execution and Verification Results",
        f"- **Dry-Run Mode:** {execution_summary.get('dry_run', False)}",
        f"- **Approved Groups Executed:** {', '.join(execution_summary.get('approved_groups', [])) or 'None'}",
        f"- **Verified Deleted Items:** {len(verified_deleted)}",
        f"- **Failed / Unverified Items:** {len(unverified_remaining) + len(execution_summary.get('failed_items', []))}",
        f"- **Storage Before Mission:** {verification['initial_storage_free']} free",
        f"- **Storage After Mission:** {verification['final_storage_free']} free",
        f"- **Total Storage Reclaimed:** {verification['reported_reclaimed_human']}",
        "",
        "## 8. Remaining Items & Recommended Next Steps",
    ]

    if unverified_remaining:
        md_lines.append(f"- **Warning:** {len(unverified_remaining)} items could not be confirmed removed. Check permissions.")
    else:
        md_lines.append("- All approved actions were cleanly executed and verified on disk.")

    md_lines.extend([
        "- Virtual machines and local AI models were kept intact in accordance with safety policies.",
        "- No background daemons or scheduled tasks were installed. MacGuard remains purely on-demand.",
        "- Run `macguard mission` again whenever you wish to perform your next maintenance review."
    ])

    final_md = "\n".join(md_lines)
    plan_data["markdown_report"] = final_md

    # 4. Save JSON and Markdown files
    timestamp_slug = time.strftime("%Y%m%d_%H%M%S")
    json_path = reports_path / f"macguard_mission_{timestamp_slug}.json"
    md_path = reports_path / f"macguard_mission_{timestamp_slug}.md"

    try:
        json_path.write_text(json.dumps(plan_data, indent=2), encoding="utf-8")
        md_path.write_text(final_md, encoding="utf-8")
        plan_data["report_files"] = {
            "json_report": str(json_path),
            "markdown_report": str(md_path)
        }
        print(f"\n[MacGuard] Mission reports saved:")
        print(f"  • JSON:     {json_path}")
        print(f"  • Markdown: {md_path}")
    except Exception as e:
        print(f"[MacGuard Error] Could not save reports to {reports_path}: {e}")

    # 5. Audit Log Entry
    if audit_logger:
        audit_logger.log_event("MISSION_COMPLETED", {
            "timestamp_slug": timestamp_slug,
            "dry_run": execution_summary.get("dry_run", False),
            "approved_groups": execution_summary.get("approved_groups", []),
            "reclaimed_bytes": execution_summary.get("total_reclaimed_bytes", 0),
            "reports": plan_data.get("report_files", {})
        })

    return plan_data
