"""
MacGuard CLI: Command-Line Interface.

Usage:
    macguard deep-clean [options]
    macguard mission [options]  (alias)
    macguard status
    macguard reports [list | latest]
"""

from __future__ import annotations

import argparse
import sys
import json
from pathlib import Path

from macguard.config import get_reports_dir, get_audit_dir, MACGUARD_HOME
from macguard.engine import MissionEngine

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="macguard",
        description="MacGuard: On-Demand Deep Cleaning & Storage Intelligence for macOS on Apple Silicon."
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available commands")

    # Primary command: `macguard deep-clean` (with `mission` as fully supported alias)
    for cmd_name, cmd_help in [
        ("deep-clean", "Initiate complete on-demand storage analysis and safe deep-cleaning mission."),
        ("mission", "Alias for deep-clean: complete on-demand storage analysis & cleanup.")
    ]:
        p = subparsers.add_parser(cmd_name, help=cmd_help)
        p.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate execution without modifying or deleting any files."
        )
        p.add_argument(
            "--auto-only",
            action="store_true",
            help="Execute only the predefined safe automatic cache cleanup and skip optional review."
        )
        p.add_argument(
            "--non-interactive",
            action="store_true",
            help="Run without interactive prompts (approves specified flags or defaults to reject all optional deletions)."
        )
        p.add_argument(
            "--approve-groups",
            type=str,
            default="",
            help="Comma-separated group IDs to approve for optional deletion (e.g. 'disposable_caches,dev_artifacts')."
        )
        p.add_argument(
            "--approve-low-risk",
            action="store_true",
            help="Approve all verified LOW-risk disposable cache groups."
        )
        p.add_argument(
            "--reject-all",
            action="store_true",
            help="Reject all optional proposed modifications, save reports, and leave all files unchanged."
        )
        p.add_argument(
            "--report-dir",
            type=Path,
            default=None,
            help="Custom directory to store mission JSON and Markdown reports."
        )
        p.add_argument(
            "--audit-dir",
            type=Path,
            default=None,
            help="Custom directory to store audit log."
        )
        p.add_argument(
            "--synthetic-test",
            action="store_true",
            help="Execute isolated end-to-end self-test on temporary synthetic files."
        )

    # Status command: `macguard status`
    subparsers.add_parser(
        "status",
        help="Display MacGuard configuration, on-demand status, and recent mission history."
    )

    # Reports command: `macguard reports`
    report_parser = subparsers.add_parser(
        "reports",
        help="List or display saved MacGuard reports."
    )
    report_parser.add_argument(
        "action",
        nargs="?",
        choices=["list", "latest"],
        default="list",
        help="List all reports or show latest report."
    )

    return parser

def cmd_status() -> None:
    print("\n" + "=" * 60)
    print("                 MACGUARD ENGINE STATUS")
    print("=" * 60)
    print(f"MacGuard Home:  {MACGUARD_HOME}")
    print(f"Reports Dir:    {get_reports_dir()}")
    print(f"Audit Dir:      {get_audit_dir()}")
    print("Operating Mode: STRICTLY ON-DEMAND (No background daemons)")

    reports = sorted(get_reports_dir().glob("macguard_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    print(f"Total Missions Recorded: {len(reports)}")
    if reports:
        print(f"Latest Mission: {reports[0].name}")
    print("=" * 60 + "\n")

def cmd_reports(action: str) -> None:
    reports = sorted(get_reports_dir().glob("macguard_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        print(f"No reports found in {get_reports_dir()}. Run 'macguard deep-clean' to perform a mission.")
        return

    if action == "latest":
        latest = reports[0]
        print(f"\n--- Displaying Latest Report: {latest.name} ---\n")
        print(latest.read_text(encoding="utf-8"))
    else:
        print(f"\nFound {len(reports)} mission report(s) in {get_reports_dir()}:")
        for idx, rep in enumerate(reports[:15], start=1):
            print(f"  [{idx}] {rep.name} ({rep.stat().st_size} bytes)")
        print()

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        sys.exit(0)

    if args.subcommand == "status":
        cmd_status()
        sys.exit(0)

    if args.subcommand == "reports":
        cmd_reports(args.action)
        sys.exit(0)

    if args.subcommand in {"deep-clean", "mission"}:
        approve_list = [g.strip() for g in args.approve_groups.split(",") if g.strip()] if args.approve_groups else None

        if args.synthetic_test:
            from tests.synthetic_runner import run_synthetic_test
            success = run_synthetic_test(dry_run=args.dry_run)
            sys.exit(0 if success else 1)

        engine = MissionEngine(
            reports_dir=args.report_dir,
            audit_dir=args.audit_dir,
            dry_run=args.dry_run,
            auto_only=getattr(args, "auto_only", False),
            non_interactive=args.non_interactive,
            approve_groups=approve_list,
            approve_low_risk=args.approve_low_risk,
            reject_all=args.reject_all
        )
        engine.run()

if __name__ == "__main__":
    main()
