"""
MacGuard Mission Engine Orchestrator.

Orchestrates the complete 10-stage on-demand maintenance workflow:
Stage 1: Environment inspection and configuration validation
Stage 2: Accessible storage and artifacts scan
Stage 3: VMware VM discovery and inspection (protected)
Stage 4: Battery health and performance assessment
Stage 5: Classification and grouping
Stage 6: Non-double-counted savings calculation
Stage 7: Consolidated report and plan generation
Stage 8: Interactive review, granular file review & approval
Stage 9: Safe execution with per-group confirmation
Stage 10: Post-execution verification and final reporting
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Set, Optional

from macguard.utils.lock import MissionLock, LockError
from macguard.utils.audit import AuditLogger
from macguard.utils.disk import format_bytes, get_disk_usage
from macguard.utils.ui import Colors, style, print_header, print_divider, storage_bar, live_progress_step
from macguard.config import get_reports_dir, get_audit_dir

from macguard.stages.stage1_environment import inspect_environment
from macguard.stages.stage2_storage_scan import scan_storage
from macguard.stages.stage3_vmware_scan import inspect_vmware
from macguard.stages.stage4_health_perf import assess_health_and_performance
from macguard.stages.stage5_classify import classify_findings
from macguard.stages.stage6_savings_calc import calculate_savings
from macguard.stages.stage7_plan_gen import generate_plan_and_report
from macguard.stages.stage8_approval import review_and_approve
from macguard.stages.stage9_execute import execute_approved_actions
from macguard.stages.stage10_verify import verify_and_report

class MissionEngine:
    """
    Executes a complete MacGuard mission from start to finish.
    """

    def __init__(
        self,
        reports_dir: Optional[Path] = None,
        audit_dir: Optional[Path] = None,
        dry_run: bool = False,
        non_interactive: bool = False,
        approve_groups: Optional[List[str]] = None,
        approve_low_risk: bool = False,
        reject_all: bool = False,
        search_roots: Optional[List[Path]] = None,
        synthetic_root: Optional[Path] = None,
        allow_synthetic: bool = False
    ):
        self.reports_dir = reports_dir or get_reports_dir()
        self.audit_dir = audit_dir or get_audit_dir()
        self.dry_run = dry_run
        self.non_interactive = non_interactive
        self.approve_groups = approve_groups
        self.approve_low_risk = approve_low_risk
        self.reject_all = reject_all
        self.search_roots = search_roots
        self.synthetic_root = synthetic_root
        self.allow_synthetic = allow_synthetic
        self.audit_logger = AuditLogger(self.audit_dir)

    def run(self) -> Dict[str, Any]:
        """
        Runs the full 10-stage mission under concurrency lock with live progress presentation.
        """
        lock = MissionLock()
        try:
            lock.acquire()
        except LockError as e:
            print(style(f"\n[MacGuard Error] {e}", Colors.RED, Colors.BOLD))
            sys.exit(1)

        start_time = time.time()
        print_header("MACGUARD ON-DEMAND MAINTENANCE ENGINE", "Exclusively User-Triggered | Zero Background Services")

        if self.dry_run:
            print(style("  * Mode: DRY-RUN SIMULATION (No files will be modified or deleted)", Colors.YELLOW, Colors.BOLD))

        self.audit_logger.log_event("MISSION_STARTED", {
            "dry_run": self.dry_run,
            "non_interactive": self.non_interactive,
            "reports_dir": str(self.reports_dir)
        })

        try:
            # -------------------------------------------------------------
            # Stage 1: Environment Inspection
            # -------------------------------------------------------------
            live_progress_step(1, 10, "Inspecting Environment & Verifying On-Demand Configuration")
            env_info = inspect_environment()
            root_storage = env_info.get("storage", {}).get("root", {})
            used_pct = root_storage.get("pct_used", 0.0)

            print(f"  • Host:     {style(env_info.get('os', {}).get('ProductName', 'macOS'), Colors.BOLD)} {env_info.get('os', {}).get('ProductVersion', '')} ({env_info.get('hardware', {}).get('cpu_model', '')})")
            print(f"  • Storage:  {storage_bar(used_pct)} | Free: {style(root_storage.get('free_human', 'N/A'), Colors.GREEN)} of {root_storage.get('total_human', 'N/A')}")
            print(f"  • Security: SIP {env_info.get('sip', 'Enabled')}")

            if env_info["schedule_validation"]["is_purely_on_demand"]:
                print(style("  ✓ Verification: Purely on-demand. Zero background daemons, launchd jobs, or schedulers found.", Colors.GREEN))
            else:
                print(style("  ! Notice: Background scheduler files detected. MacGuard strictly operates on-demand.", Colors.YELLOW))

            # -------------------------------------------------------------
            # Stage 2: Storage & Artifacts Deep Scan
            # -------------------------------------------------------------
            live_progress_step(2, 10, "Analyzing Storage: Caches, Logs, Installers, Duplicates & Developer Artifacts")
            storage_scan = scan_storage(
                search_roots=self.search_roots,
                synthetic_root=self.synthetic_root
            )
            cache_bytes = sum(c["size_bytes"] for c in storage_scan.get("caches", []))
            log_bytes = sum(l["size_bytes"] for l in storage_scan.get("logs", []))
            inst_bytes = sum(i["size_bytes"] for i in storage_scan.get("installers", []))
            dup_bytes = sum(d["potential_savings_bytes"] for d in storage_scan.get("duplicates", []))

            print(f"  • Application Caches:     {len(storage_scan['caches'])} targets ({format_bytes(cache_bytes)})")
            print(f"  • Diagnostic Logs:        {len(storage_scan['logs'])} items ({format_bytes(log_bytes)})")
            print(f"  • Downloaded Installers:  {len(storage_scan['installers'])} files ({format_bytes(inst_bytes)})")
            print(f"  • Duplicate Candidates:   {len(storage_scan['duplicates'])} clusters ({format_bytes(dup_bytes)})")
            print(f"  • Developer Artifacts:    {len(storage_scan['developer_artifacts'])} targets")
            if storage_scan.get("local_ai_models"):
                print(f"  • Local AI Models:        {len(storage_scan['local_ai_models'])} repositories")

            # -------------------------------------------------------------
            # Stage 3: VMware VM Discovery & Inspection
            # -------------------------------------------------------------
            live_progress_step(3, 10, "Discovering VMware Virtual Machines & Inspecting Host Storage")
            vmware_scan = inspect_vmware()
            if vmware_scan["discovered_vms"]:
                print(style(f"  • Discovered {len(vmware_scan['discovered_vms'])} VM bundle(s) ({vmware_scan['total_vm_storage_human']}):", Colors.CYAN))
                for vm in vmware_scan["discovered_vms"]:
                    print(style(f"    - {vm['display_name']} ({vm['guest_os']}): {vm['size_human']}, {vm['snapshots_count']} snapshot(s) [STRICTLY PROTECTED - NO CHANGES]", Colors.GRAY))
            else:
                print("  • No VMware virtual machine bundles found in standard paths.")

            # -------------------------------------------------------------
            # Stage 4: Health, Battery & System Pressure Assessment
            # -------------------------------------------------------------
            live_progress_step(4, 10, "Assessing Battery Health, Thermal State & System Pressure")
            health_perf = assess_health_and_performance()
            batt = health_perf.get("battery", {})
            if batt.get("has_battery"):
                print(f"  • Battery:   {batt.get('percentage')}% ({batt.get('status')}) on {batt.get('power_source')} | Condition: {batt.get('condition')}")
            else:
                print("  • Battery:   Desktop Mac (AC connected)")
            print(f"  • CPU Load:  {health_perf.get('cpu', {}).get('load_averages', [])}")
            print(f"  • Memory:    {health_perf.get('memory', {}).get('pressure_level', 'Normal')} pressure")

            for rec in health_perf.get("recommendations", []):
                print(style(f"  • Assessment: {rec}", Colors.GRAY))

            # -------------------------------------------------------------
            # Stage 5: Classification Engine
            # -------------------------------------------------------------
            live_progress_step(5, 10, "Classifying Findings by Risk, Usefulness, Confidence & Action")
            groups = classify_findings(storage_scan, vmware_scan)
            print(f"  ✓ Structured discovered items into {len(groups)} distinct action proposal categories.")

            # -------------------------------------------------------------
            # Stage 6: Savings Calculation (No Double Counting)
            # -------------------------------------------------------------
            live_progress_step(6, 10, "Calculating Realistic Non-Double-Counted Potential Storage Savings")
            savings = calculate_savings(groups)
            print(f"  • Net Realistic Potential:  {style(savings['net_potential_human'], Colors.BOLD, Colors.CYAN)}")
            print(f"  • Recommended Safe Savings: {style(savings['recommended_savings_human'], Colors.BOLD, Colors.GREEN)} (Low-Risk disposable caches only)")

            # -------------------------------------------------------------
            # Stage 7: Consolidated Action Plan & Mission Report Generation
            # -------------------------------------------------------------
            live_progress_step(7, 10, "Generating Consolidated Action Proposal & Machine-Readable Audit Data")
            plan_data = generate_plan_and_report(env_info, storage_scan, vmware_scan, health_perf, groups, savings)
            print("  ✓ Consolidated action plan and audit structures prepared.")

            # -------------------------------------------------------------
            # Stage 8: Interactive Consolidated Approval Stage
            # -------------------------------------------------------------
            live_progress_step(8, 10, "Consolidated Review & User Approval Interface")
            approved_ids, custom_files = review_and_approve(
                groups=groups,
                non_interactive=self.non_interactive,
                auto_approve_groups=self.approve_groups,
                approve_low_risk=self.approve_low_risk,
                reject_all=self.reject_all
            )

            self.audit_logger.log_event("APPROVAL_DECISION", {
                "approved_groups": list(approved_ids),
                "custom_files": {k: list(v) for k, v in custom_files.items()},
                "total_approved": len(approved_ids)
            })

            # -------------------------------------------------------------
            # Stage 9: Safe Execution Engine (Per-Group Explicit Confirmation)
            # -------------------------------------------------------------
            live_progress_step(9, 10, "Executing Approved Operations")
            if not approved_ids:
                print(style("  [MacGuard Notice] Zero action groups authorized. All files remain unmodified.", Colors.YELLOW))
                exec_summary = {
                    "dry_run": self.dry_run,
                    "approved_groups": [],
                    "executed_items": [],
                    "skipped_items": [],
                    "failed_items": [],
                    "total_attempted_bytes": 0,
                    "total_reclaimed_bytes": 0,
                    "total_reclaimed_human": "0 B"
                }
            else:
                exec_summary = execute_approved_actions(
                    groups=groups,
                    approved_group_ids=approved_ids,
                    custom_approved_files=custom_files,
                    dry_run=self.dry_run,
                    non_interactive=self.non_interactive,
                    allow_synthetic=self.allow_synthetic,
                    audit_logger=self.audit_logger
                )

            # -------------------------------------------------------------
            # Stage 10: Post-Execution Verification and Final Report
            # -------------------------------------------------------------
            live_progress_step(10, 10, "Post-Execution Verification & Writing Final Mission Reports")
            final_report = verify_and_report(
                plan_data=plan_data,
                execution_summary=exec_summary,
                reports_dir=self.reports_dir,
                audit_logger=self.audit_logger
            )

            elapsed = round(time.time() - start_time, 2)
            print_header("MACGUARD MISSION COMPLETE", f"Duration: {elapsed}s | Mode: On-Demand")

            ver = final_report.get("verification", {})
            print(f"  • Initial Available Storage:  {style(ver.get('initial_storage_free', 'N/A'), Colors.BOLD)}")
            print(f"  • Final Available Storage:    {style(ver.get('final_storage_free', 'N/A'), Colors.BOLD)}")
            print(f"  • Verified Reclaimed Storage: {style(ver.get('reported_reclaimed_human', '0 B'), Colors.BOLD, Colors.GREEN)}")
            print(f"  • Verified Deleted Items:     {ver.get('verified_deleted_count', 0)}")
            print(f"  • Failed / Skipped Items:     {ver.get('unverified_remaining_count', 0) + len(exec_summary.get('skipped_items', []))}")

            rep_files = final_report.get("report_files", {})
            if rep_files:
                print(f"\n  • Human Report:    {rep_files.get('markdown_report', 'Saved')}")
                print(f"  • Machine Report:  {rep_files.get('json_report', 'Saved')}")

            print_divider()
            return final_report

        finally:
            lock.release()
