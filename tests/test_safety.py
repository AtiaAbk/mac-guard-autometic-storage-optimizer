"""
Unit tests for MacGuard SafetyPolicy.
"""

import unittest
from pathlib import Path
from macguard.safety import SafetyPolicy

class TestSafetyPolicy(unittest.TestCase):

    def test_protects_system_prefixes(self):
        system_paths = [
            Path("/System/Library/CoreServices"),
            Path("/usr/bin/python3"),
            Path("/bin/sh"),
            Path("/sbin/mount"),
            Path("/Library/Preferences/SystemConfiguration"),
        ]
        for p in system_paths:
            is_safe, reason = SafetyPolicy.validate_for_deletion(p)
            self.assertFalse(is_safe, f"Path {p} should be protected!")
            self.assertIn("protected macOS system location", reason)

    def test_protects_sensitive_config(self):
        hosts = Path("/etc/hosts")
        is_safe, reason = SafetyPolicy.validate_for_deletion(hosts)
        self.assertFalse(is_safe)
        self.assertIsNotNone(reason)

    def test_protects_vm_storage(self):
        vm_paths = [
            Path("/Users/user/Virtual Machines/Ubuntu.vmwarevm"),
            Path("/Users/user/VMs/Windows11.vmdk"),
            Path("/Users/user/VMs/snap-000001.vmdk"),
            Path("/Users/user/Virtual Machines.localized/Debian.vmx"),
            Path("/tmp/test.vmem"),
            Path("/tmp/state.vmss"),
        ]
        for p in vm_paths:
            self.assertTrue(SafetyPolicy.is_vm_storage(p), f"Should recognize {p} as VM storage")
            is_safe, reason = SafetyPolicy.validate_for_deletion(p)
            self.assertFalse(is_safe, f"Path {p} should NOT be safe for deletion")
            self.assertIn("Virtual Machine resource", reason)

    def test_protects_source_and_documents(self):
        protected_files = [
            Path("/Users/user/Documents/report.docx"),
            Path("/Users/user/Documents/taxes.pdf"),
            Path("/Users/user/Projects/app/main.py"),
            Path("/Users/user/Projects/app/server.go"),
            Path("/Users/user/Projects/app/Cargo.toml"),
            Path("/Users/user/.ssh/id_ed25519"),
            Path("/Users/user/.git/config"),
            Path("/Users/user/db.sqlite3"),
            Path("/Users/user/cert.pem"),
        ]
        for p in protected_files:
            self.assertTrue(SafetyPolicy.is_source_or_document(p), f"Should protect {p}")

    def test_blocks_root_and_user_home(self):
        self.assertFalse(SafetyPolicy.validate_for_deletion(Path("/"))[0])
        self.assertFalse(SafetyPolicy.validate_for_deletion(Path.home())[0])

if __name__ == "__main__":
    unittest.main()
