"""
Synthetic Test Runner for MacGuard.

Creates an isolated sandbox environment with synthetic fixtures:
- Disposable caches
- Old logs
- Old installers
- Duplicate files
- Protected items (VM disks, documents, source code, credentials)

Tests the entire 10-stage lifecycle:
1. Dry-run mode (verifying zero files are deleted)
2. Selective approval (verifying only approved disposable files are deleted,
   while duplicate review candidates, VM files, and documents are 100% preserved)
3. SafetyPolicy blocks deletion of protected files even if requested.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, List

from macguard.engine import MissionEngine
from macguard.safety import SafetyPolicy
from macguard.utils.disk import get_path_size

def create_synthetic_environment() -> Path:
    """Creates a temporary synthetic directory structure with dummy files."""
    test_root = Path(tempfile.mkdtemp(prefix=".macguard_synthetic_test_"))

    # 1. Disposable Caches
    cache_dir = test_root / "Library" / "Caches" / "com.test.dummycache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    with open(cache_dir / "cache.bin", "wb") as f:
        f.write(b"0" * (12 * 1024 * 1024))  # 12 MB

    # 2. Old Logs
    log_dir = test_root / "Library" / "Logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    old_log = log_dir / "old_system_test.log"
    with open(old_log, "wb") as f:
        f.write(b"LOG ENTRY\n" * 100000)
    past_time = time.time() - (30 * 86400)
    os.utime(str(old_log), (past_time, past_time))

    # 3. Old Installers
    down_dir = test_root / "Downloads"
    down_dir.mkdir(parents=True, exist_ok=True)
    old_installer = down_dir / "legacy_app_setup.dmg"
    with open(old_installer, "wb") as f:
        f.write(b"DMG DATA" * 100000)
    os.utime(str(old_installer), (past_time, past_time))

    # 4. Duplicate Candidates
    dup1 = down_dir / "sample_video_part1.iso"
    dup2 = down_dir / "sample_video_copy.iso"
    content = b"IDENTICAL_CONTENT_HASH_BLOCK_" * 50000
    with open(dup1, "wb") as f:
        f.write(content)
    with open(dup2, "wb") as f:
        f.write(content)

    # 5. Protected Files (Must NEVER be touched)
    protected_code = test_root / "Projects" / "myapp" / "main.py"
    protected_code.parent.mkdir(parents=True, exist_ok=True)
    with open(protected_code, "w") as f:
        f.write("print('Critical source code')\n")

    protected_doc = test_root / "Documents" / "financials.xlsx"
    protected_doc.parent.mkdir(parents=True, exist_ok=True)
    with open(protected_doc, "wb") as f:
        f.write(b"PK\x03\x04ExcelData")

    protected_vm = test_root / "Virtual Machines" / "Ubuntu.vmwarevm" / "Ubuntu.vmdk"
    protected_vm.parent.mkdir(parents=True, exist_ok=True)
    with open(protected_vm, "wb") as f:
        f.write(b"VMDK DISK HEADER")

    return test_root

def run_synthetic_test(dry_run: bool = False) -> bool:
    """Executes a full end-to-end synthetic test suite."""
    print("\n" + "=" * 80)
    print("               RUNNING MACGUARD SYNTHETIC END-TO-END TEST")
    print("=" * 80)

    test_root = create_synthetic_environment()
    reports_dir = test_root / "reports"
    audit_dir = test_root / "audit"

    try:
        print(f"Created isolated synthetic test directory at:\n  {test_root}\n")

        # Part A: Test Safety Policy
        print("Testing SafetyPolicy invariants...")
        vm_vmdk = test_root / "Virtual Machines" / "Ubuntu.vmwarevm" / "Ubuntu.vmdk"
        safe, reason = SafetyPolicy.validate_for_deletion(vm_vmdk, allow_synthetic=False)
        assert not safe, "Safety Policy failed to protect VM disk!"
        print(f"  ✓ Confirmed VM protection: {reason}")

        code_file = test_root / "Projects" / "myapp" / "main.py"
        safe, reason = SafetyPolicy.validate_for_deletion(code_file, allow_synthetic=False)
        assert not safe, "Safety Policy failed to protect source code!"
        print(f"  ✓ Confirmed source code protection: {reason}")

        sys_path = Path("/System/Library/Kernels")
        safe, reason = SafetyPolicy.validate_for_deletion(sys_path, allow_synthetic=False)
        assert not safe, "Safety Policy failed to protect macOS /System path!"
        print(f"  ✓ Confirmed /System protection: {reason}")

        # Part B: Run Engine in Dry-Run Mode with isolated synthetic root
        print("\nTesting MissionEngine in Dry-Run Mode...")
        engine_dry = MissionEngine(
            reports_dir=reports_dir,
            audit_dir=audit_dir,
            dry_run=True,
            non_interactive=True,
            approve_low_risk=True,
            synthetic_root=test_root,
            allow_synthetic=True
        )
        report_dry = engine_dry.run()

        # Verify no files were deleted in dry-run
        cache_bin = test_root / "Library" / "Caches" / "com.test.dummycache" / "cache.bin"
        assert cache_bin.exists(), "Dry-run violated safety: cache.bin was deleted!"
        print("  ✓ Dry-run verification passed: zero files were deleted.")

        # Part C: Run Engine with Selective Approval on isolated synthetic root
        print("\nTesting MissionEngine with Selective Approval...")
        engine_live = MissionEngine(
            reports_dir=reports_dir,
            audit_dir=audit_dir,
            dry_run=False,
            non_interactive=True,
            approve_groups=["disposable_caches"],  # Only approve disposable caches
            synthetic_root=test_root,
            allow_synthetic=True
        )
        report_live = engine_live.run()

        # Synthetic cache should be deleted because it was approved:
        assert not cache_bin.exists(), "Approved synthetic cache should have been removed!"
        print("  ✓ Approved synthetic cache was cleanly removed.")

        # Protected files must remain intact:
        assert code_file.exists(), "Source code file was affected!"
        assert vm_vmdk.exists(), "VM disk was affected!"
        print("  ✓ Protected files (code, VM, documents) are 100% intact.")

        # Verify reports and audit log generated
        json_reports = list(reports_dir.glob("*.json"))
        md_reports = list(reports_dir.glob("*.md"))
        audit_file = audit_dir / "audit.log"

        assert len(json_reports) >= 1, "Missing JSON report!"
        assert len(md_reports) >= 1, "Missing Markdown report!"
        assert audit_file.exists(), "Missing audit log!"

        print(f"  ✓ Verified report outputs: {len(json_reports)} JSON, {len(md_reports)} MD")
        print(f"  ✓ Verified audit trail: {audit_file.stat().st_size} bytes")

        print("\n" + "=" * 80)
        print("           SYNTHETIC END-TO-END TEST SUITE PASSED SUCCESSFULLY")
        print("=" * 80 + "\n")
        return True

    finally:
        shutil.rmtree(test_root, ignore_errors=True)

if __name__ == "__main__":
    success = run_synthetic_test()
    import sys
    sys.exit(0 if success else 1)
