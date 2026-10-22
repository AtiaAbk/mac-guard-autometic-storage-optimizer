"""
MacGuard Deep Cleaning & Storage Intelligence Engine Orchestrator.

Full Workflow:
1. Inspect environment & verify on-demand configuration (no schedulers)
2. Automatic Safe Cache Cleanup (Predefined Allowlist with Process Liveness checks)
3. Deep Storage Analysis (Volumes, User Directories, Caches, Logs, Installers, Duplicates)
4. Deep VMware Fusion Analysis (Virtual disks, snapshots, ISOs, host vs guest)
5. Battery, Thermals & Mach Virtual Memory Pressure Assessment
6. Risk Tier & Usefulness Classification
7. Non-Double-Counted Storage Savings Calculation
8. Consolidated Action Proposal & Machine-Readable Audit Data Generation
9. Interactive Review Menu (Installers, Duplicates, Large Files, VMware, Whole Groups)
10. Safe Execution of Explicitly Approved Items (Per-Group Affirmative Confirmation)
11. Post-Execution Verification & Persistent Reporting
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
from macguard.stages.stage_safe_autoclean import execute_safe_autoclean
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
    Executes a complete MacGuard deep-cleaning mission from start to finish.
    """

    def __init__(
        self,
        reports_dir: Optional[Path] = None,
        audit_dir: Optional[Path] = None,
        dry_run: bool = False,
        non_interactive: bool = False,
        auto_only: bool = False,
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
        self.auto_only = auto_only
        self.approve_groups = approve_groups
        self.approve_low_risk = approve_low_risk
        self.reject_all = reject_all
        self.search_roots = search_roots
        self.synthetic_root = synthetic_root
        self.allow_synthetic = allow_synthetic
        self.audit_logger = AuditLogger(self.audit_dir)

    def run(self) -> Dict[str, Any]:
        """
        Runs the full on-demand deep-cleaning mission under atomic concurrency lock.
        """
        lock = MissionLock()
        try:
            lock.acquire()
        except LockError as e:
            print(style(f"\n[MacGuard Concurrency Lock] {e}", Colors.RED, Colors.BOLD))
            sys.exit(1)

        start_time = time.time()
        print_header("MACGUARD — DEEP CLEANING & STORAGE INTELLIGENCE", "Exclusively User-Triggered | Apple Silicon & macOS Optimized")

        if self.dry_run:
            print(style("  * Mode: DRY-RUN SIMULATION (Read-only analysis; no files will be deleted)", Colors.YELLOW, Colors.BOLD))

        self.audit_logger.log_event("MISSION_STARTED", {
            "command": "deep-clean",
            "dry_run": self.dry_run,
            "non_interactive": self.non_interactive,
            "reports_dir": str(self.reports_dir)
        })

        try:
            # -------------------------------------------------------------
            # Stage 1: Environment Inspection & Configuration Validation
            # -------------------------------------------------------------
            live_progress_step(1, 10, "Inspecting Environment & Verifying No Background Daemons")
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
            # Stage 2: Automatic Safe Cache Cleanup (Predefined Allowlist)
            # -------------------------------------------------------------
            live_progress_step(2, 10, "Automatic Safe Cache Cleanup (Predefined Allowlist & Process Verification)")
            autoclean_summary = execute_safe_autoclean(
                base_dir=self.synthetic_root,
                dry_run=self.dry_run,
                allow_synthetic=self.allow_synthetic,
                audit_logger=self.audit_logger
            )

            # -------------------------------------------------------------
            # Stage 3: Deep Storage & Artifacts Analysis
            # -------------------------------------------------------------
            live_progress_step(3, 10, "Deep Storage Analysis: User Directories, Logs, Installers, Duplicates & AI Models")
            storage_scan = scan_storage(
                search_roots=self.search_roots,
                synthetic_root=self.synthetic_root
            )
            cache_bytes = sum(c.get("apparent_bytes", 0) for c in storage_scan.get("caches", []))
            log_bytes = sum(l.get("apparent_bytes", 0) for l in storage_scan.get("logs", []))
            inst_bytes = sum(i.get("apparent_bytes", 0) for i in storage_scan.get("installers", []))
            dup_bytes = sum(d.get("potential_savings_bytes", 0) for d in storage_scan.get("duplicates", []))

            print(f"  • Application Caches:     {len(storage_scan['caches'])} targets ({format_bytes(cache_bytes)})")
            print(f"  • Diagnostic Logs:        {len(storage_scan['logs'])} items ({format_bytes(log_bytes)})")
            print(f"  • Downloaded Installers:  {len(storage_scan['installers'])} files ({format_bytes(inst_bytes)})")
            print(f"  • Duplicate Candidates:   {len(storage_scan['duplicates'])} clusters ({format_bytes(dup_bytes)})")
            print(f"  • Developer Artifacts:    {len(storage_scan['developer_artifacts'])} targets")
            if storage_scan.get("local_ai_models"):
                print(f"  • Local AI Models:        {len(storage_scan['local_ai_models'])} repositories")

            # -------------------------------------------------------------
            # Stage 4: VMware Fusion Deep Inspection (Strictly Protected)
            # -------------------------------------------------------------
            live_progress_step(4, 10, "Deep VMware Fusion Inspection (Virtual Disks, Snapshots, Host vs Guest)")
            vmware_scan = inspect_vmware()
            if vmware_scan["discovered_vms"]:
                print(style(f"  • Discovered {len(vmware_scan['discovered_vms'])} VM bundle(s) ({vmware_scan['total_host_storage_human']}):", Colors.CYAN))
                for vm in vmware_scan["discovered_vms"]:
                    snaps = vm['snapshot_chains']['snapshot_count']
                    delta_sz = vm['snapshot_chains']['delta_storage_human']
                    print(style(f"    - {vm['display_name']} ({vm['guest_os']}): Apparent {vm['apparent_human']} | Allocated {vm['allocated_human']}, {snaps} snapshot(s) ({delta_sz}) [STRICTLY PROTECTED]", Colors.GRAY))
            else:
                print("  • No VMware virtual machine bundles found in standard paths.")

            # -------------------------------------------------------------
            # Stage 5: Battery Health, Thermal State & System Pressure
            # -------------------------------------------------------------
            live_progress_step(5, 10, "Assessing Battery Health, Thermal State & Mach Memory Pressure")
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
            # Stage 6: Risk Tier Classification
            # -------------------------------------------------------------
            live_progress_step(6, 10, "Classifying Findings by Risk, Usefulness, Confidence & Action")
            groups = classify_findings(storage_scan, vmware_scan)
            print(f"  ✓ Structured discovered items into {len(groups)} distinct action proposal categories.")

            # -------------------------------------------------------------
            # Stage 7: Realistic Savings Calculation (No Double-Counting)
            # -------------------------------------------------------------
            live_progress_step(7, 10, "Calculating Non-Double-Counted Realistic Storage Savings")
            savings = calculate_savings(groups)
            print(f"  • Net Realistic Potential:  {style(savings['net_potential_human'], Colors.BOLD, Colors.CYAN)}")
            print(f"  • Recommended Safe Savings: {style(savings['recommended_savings_human'], Colors.BOLD, Colors.GREEN)} (Low-Risk disposable caches only)")

            # -------------------------------------------------------------
            # Stage 8: Consolidated Action Plan & Audit Data Generation
            # -------------------------------------------------------------
            live_progress_step(8, 10, "Generating Consolidated Plan & Machine-Readable Audit Data")
            plan_data = generate_plan_and_report(
                env_info=env_info,
                storage_scan=storage_scan,
                vmware_scan=vmware_scan,
                health_perf=health_perf,
                groups=groups,
                savings=savings,
                autoclean_summary=autoclean_summary
            )
            print("  ✓ Consolidated action plan and audit structures prepared.")

            # -------------------------------------------------------------
            # Stage 9: Interactive Consolidated Approval Stage
            # -------------------------------------------------------------
            if self.auto_only:
                print(style("\n  [MacGuard Notice] Running with --auto-only. Optional deletions skipped.", Colors.CYAN))
                approved_ids, custom_files = set(), {}
            else:
                live_progress_step(9, 10, "Interactive Review & Approval Menu (Installers, Duplicates, Optional Deletions)")
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
            # Stage 10: Safe Execution (Per-Group Affirmative Confirmation)
            # -------------------------------------------------------------
            live_progress_step(10, 10, "Executing Approved Operations & Verifying Disk Storage")
            if not approved_ids:
                print(style("  [MacGuard Notice] Zero optional action groups authorized. Optional files remain unmodified.", Colors.YELLOW))
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

            # Combined Verification & Reporting
            final_report = verify_and_report(
                plan_data=plan_data,
                execution_summary=exec_summary,
                reports_dir=self.reports_dir,
                audit_logger=self.audit_logger
            )

            # Final Summary Screen
            elapsed = round(time.time() - start_time, 2)
            print_header("MACGUARD DEEP-CLEAN COMPLETE", f"Duration: {elapsed}s | Mode: On-Demand")

            ver = final_report.get("verification", {})
            auto_rec = autoclean_summary.get("total_apparent_bytes_cleaned", 0)
            opt_rec = exec_summary.get("total_reclaimed_bytes", 0)
            total_rec = auto_rec + opt_rec

            print(f"  • Initial Available Storage:      {style(ver.get('initial_storage_free', 'N/A'), Colors.BOLD)}")
            print(f"  • Final Available Storage:        {style(ver.get('final_storage_free', 'N/A'), Colors.BOLD)}")
            print(f"  • Space from Auto Safe Cleanup:   {style(format_bytes(auto_rec), Colors.GREEN)}")
            print(f"  • Space from Approved Deletions:  {style(format_bytes(opt_rec), Colors.GREEN)}")
            print(f"  • Total Verified Reclaimed Space: {style(format_bytes(total_rec), Colors.BOLD, Colors.GREEN)}")

            rep_files = final_report.get("report_files", {})
            if rep_files:
                print(f"\n  • Human Report (Markdown):  {rep_files.get('markdown_report', 'Saved')}")
                print(f"  • Machine Report (JSON):    {rep_files.get('json_report', 'Saved')}")

            print_divider()
            return final_report

        finally:
            lock.release()
