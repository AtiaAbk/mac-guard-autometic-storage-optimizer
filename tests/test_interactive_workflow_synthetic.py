"""
End-to-end interactive simulation on synthetic disposable test files.
Simulates a live human terminal session using input feeds to test:
- Interactive main menu navigation
- File-by-file installer review and selection
- File-by-file duplicate review
- Explicit per-group execution confirmation
- Verification of before-and-after storage metrics
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from macguard.engine import MissionEngine
from tests.synthetic_runner import create_synthetic_environment

class TestEndToEndInteractiveSimulation(unittest.TestCase):

    def setUp(self):
        self.test_root = create_synthetic_environment()
        self.reports_dir = self.test_root / "reports"
        self.audit_dir = self.test_root / "audit"

    def tearDown(self):
        shutil.rmtree(self.test_root, ignore_errors=True)

    def test_full_interactive_workflow_with_file_review_and_confirmations(self):
        # Scripted user responses:
        # 1. Main menu: "approve 1" (approve disposable caches)
        # 2. Main menu: "review installers"
        #    Installer menu: "select 1", then "done"
        # 3. Main menu: "review duplicates"
        #    Duplicate menu: "default", then "done"
        # 4. Main menu: "proceed"
        # 5. Confirmation 1 (disposable caches): "yes"
        # 6. Confirmation 2 (old installers): "yes"
        # 7. Confirmation 3 (duplicates): "yes"
        user_inputs = [
            "approve 1",
            "review installers",
            "select 1",
            "done",
            "review duplicates",
            "default",
            "done",
            "proceed",
            "yes",
            "yes",
            "yes"
        ]

        engine = MissionEngine(
            reports_dir=self.reports_dir,
            audit_dir=self.audit_dir,
            dry_run=False,
            non_interactive=False,  # Genuinely interactive!
            synthetic_root=self.test_root,
            allow_synthetic=True
        )

        with patch("builtins.input", side_effect=user_inputs):
            report = engine.run()

        # Verify results
        # 1. Synthetic cache should be deleted
        cache_bin = self.test_root / "Library" / "Caches" / "com.test.dummycache" / "cache.bin"
        self.assertFalse(cache_bin.exists(), "Approved synthetic cache should have been removed!")

        # 2. Synthetic installer #1 should be deleted
        installer_dmg = self.test_root / "Downloads" / "legacy_app_setup.dmg"
        self.assertFalse(installer_dmg.exists(), "Approved installer should have been removed!")

        # 3. In duplicate set, copy 2 should be deleted, copy 1 must be kept
        dup1 = self.test_root / "Downloads" / "sample_video_part1.iso"
        dup2 = self.test_root / "Downloads" / "sample_video_copy.iso"
        self.assertTrue(dup1.exists(), "Original copy in duplicate cluster must be kept!")
        self.assertFalse(dup2.exists(), "Secondary duplicate copy should have been removed!")

        # 4. Protected files must remain 100% intact
        code_file = self.test_root / "Projects" / "myapp" / "main.py"
        doc_file = self.test_root / "Documents" / "financials.xlsx"
        vm_vmdk = self.test_root / "Virtual Machines" / "Ubuntu.vmwarevm" / "Ubuntu.vmdk"
        self.assertTrue(code_file.exists(), "Source code was modified!")
        self.assertTrue(doc_file.exists(), "Document was modified!")
        self.assertTrue(vm_vmdk.exists(), "VM disk was modified!")

        # 5. Verification checks
        ver = report.get("verification", {})
        self.assertGreater(ver.get("reported_reclaimed_bytes", 0), 0)
        self.assertEqual(ver.get("unverified_remaining_count", 0), 0)

        # 6. Reports exist
        json_reports = list(self.reports_dir.glob("*.json"))
        md_reports = list(self.reports_dir.glob("*.md"))
        self.assertGreaterEqual(len(json_reports), 1)
        self.assertGreaterEqual(len(md_reports), 1)

if __name__ == "__main__":
    unittest.main()
