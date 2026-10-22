"""
Unit tests for the Automatic Safe Cache Cleanup Engine:
- Predefined allowlist matching
- Process liveness checks (skipping cache if app process is running)
- Verification that only verified regenerable caches are targeted
- Measurement of reclaimed disk space
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from macguard.stages.stage_safe_autoclean import (
    SAFE_AUTOCLEAN_ALLOWLIST,
    execute_safe_autoclean,
    is_process_running
)

class TestSafeAutoclean(unittest.TestCase):

    def setUp(self):
        self.test_root = Path(tempfile.mkdtemp(prefix=".macguard_autoclean_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_root, ignore_errors=True)

    def test_process_liveness_check(self):
        running = {"google chrome", "google chrome helper", "zsh", "python3"}
        
        is_active, proc = is_process_running(["Google Chrome"], running)
        self.assertTrue(is_active)
        self.assertEqual(proc, "Google Chrome")

        is_active, proc = is_process_running(["Safari"], running)
        self.assertFalse(is_active)
        self.assertIsNone(proc)

    def test_autoclean_skips_when_app_is_running(self):
        # Create dummy Chrome cache in test_root
        chrome_cache = self.test_root / "Library/Caches/Google/Chrome/Default/Cache"
        chrome_cache.mkdir(parents=True, exist_ok=True)
        with open(chrome_cache / "data_0", "wb") as f:
            f.write(b"CHROME_CACHE_DATA" * 1000)

        # Mock that Google Chrome is currently running
        with patch("macguard.stages.stage_safe_autoclean.get_running_process_names", return_value={"google chrome"}):
            summary = execute_safe_autoclean(
                base_dir=self.test_root,
                dry_run=False,
                allow_synthetic=True
            )

        # Should be skipped because Chrome is running!
        self.assertTrue(chrome_cache.exists(), "Cache must NOT be deleted while application is running!")
        self.assertEqual(len(summary["skipped_items"]), 1)
        self.assertIn("actively running", summary["skipped_items"][0]["reason"])

    def test_autoclean_cleans_when_app_is_not_running(self):
        # Create dummy HelpViewer cache in test_root
        help_cache = self.test_root / "Library/Caches/com.apple.helpd"
        help_cache.mkdir(parents=True, exist_ok=True)
        with open(help_cache / "help_data.bin", "wb") as f:
            f.write(b"DISPOSABLE_HELP_CACHE" * 1000)

        # Mock that HelpViewer is NOT running
        with patch("macguard.stages.stage_safe_autoclean.get_running_process_names", return_value={"zsh", "python3"}):
            summary = execute_safe_autoclean(
                base_dir=self.test_root,
                dry_run=False,
                allow_synthetic=True
            )

        # Should be cleanly removed!
        self.assertFalse(help_cache.exists(), "Disposable allowlist cache should have been cleaned!")
        self.assertEqual(len(summary["cleaned_items"]), 1)
        self.assertGreater(summary["total_apparent_bytes_cleaned"], 0)

if __name__ == "__main__":
    unittest.main()
