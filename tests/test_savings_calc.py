"""
Unit tests for non-double-counted savings calculation.
"""

import unittest
from pathlib import Path
from macguard.stages.stage6_savings_calc import calculate_savings

class TestSavingsCalculator(unittest.TestCase):

    def test_duplicate_candidates_savings_formula(self):
        groups = [
            {
                "group_id": "duplicate_candidates",
                "risk_level": "HIGH",
                "is_selectable": True,
                "recommended_action": "REJECT",
                "total_bytes": 200 * 1024 * 1024,
                "items": [
                    {
                        "path": "dup_set",
                        "size_bytes": 200 * 1024 * 1024,
                        "duplicates": ["/tmp/f1.iso", "/tmp/f2.iso", "/tmp/f3.iso"]
                    }
                ]
            }
        ]
        savings = calculate_savings(groups)
        self.assertEqual(savings["net_potential_bytes"], 200 * 1024 * 1024)

    def test_nested_directory_no_double_counting(self):
        parent = Path("/tmp/test_cache_parent").resolve()
        child = Path("/tmp/test_cache_parent/subdir/nested.dat").resolve()

        groups = [
            {
                "group_id": "disposable_caches",
                "risk_level": "LOW",
                "is_selectable": True,
                "recommended_action": "APPROVE",
                "total_bytes": 500,
                "items": [
                    {"path": str(parent), "size_bytes": 500, "action": "DELETE_CACHE_DIR"},
                    {"path": str(child), "size_bytes": 200, "action": "DELETE_FILE"}
                ]
            }
        ]
        savings = calculate_savings(groups)
        self.assertEqual(savings["net_potential_bytes"], 500)
        self.assertEqual(savings["recommended_savings_bytes"], 500)

    def test_protected_groups_excluded_from_potential_savings(self):
        groups = [
            {
                "group_id": "vmware_vms",
                "risk_level": "PROTECTED",
                "is_selectable": False,
                "recommended_action": "KEEP",
                "total_bytes": 50 * 1024 * 1024 * 1024,
                "items": [{"path": "/Users/user/VMs/Ubuntu.vmwarevm", "size_bytes": 50 * 1024 * 1024 * 1024}]
            }
        ]
        savings = calculate_savings(groups)
        self.assertEqual(savings["net_potential_bytes"], 0)
        self.assertEqual(savings["recommended_savings_bytes"], 0)

if __name__ == "__main__":
    unittest.main()
