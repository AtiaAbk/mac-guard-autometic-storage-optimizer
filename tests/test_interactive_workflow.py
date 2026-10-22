"""
Unit and integration tests for the Interactive Terminal Interface:
- Per-group explicit confirmation ('yes' vs empty enter / 'no')
- Individual file review for installers (.dmg/.pkg)
- Individual file review for duplicate clusters
- Verification that Enter, empty responses, or invalid inputs never approve actions
"""

import unittest
from unittest.mock import patch
from pathlib import Path

from macguard.stages.stage8_approval import (
    review_installer_files,
    review_duplicate_files,
    review_and_approve
)
from macguard.stages.stage9_execute import execute_approved_actions

class TestInteractiveInterface(unittest.TestCase):

    def test_installer_file_review_selection(self):
        group = {
            "group_id": "old_installers",
            "category_name": "Downloaded Disk Images & Installers",
            "items": [
                {"path": "/tmp/app1.dmg", "name": "app1.dmg", "size_bytes": 1000},
                {"path": "/tmp/app2.pkg", "name": "app2.pkg", "size_bytes": 2000},
            ]
        }
        # Simulate user typing: "select 1", then "done"
        with patch("builtins.input", side_effect=["select 1", "done"]):
            selected = review_installer_files(group, set())
            self.assertEqual(selected, {"/tmp/app1.dmg"})

    def test_duplicate_file_review_keep_at_least_one(self):
        group = {
            "group_id": "duplicate_candidates",
            "category_name": "Identical Duplicate File Candidates",
            "items": [
                {
                    "path": "cluster_1",
                    "duplicates": ["/tmp/copy1.iso", "/tmp/copy2.iso"],
                    "size_bytes": 5000
                }
            ]
        }
        # Simulate user selecting "delete 1.2", then "done"
        with patch("builtins.input", side_effect=["delete 1.2", "done"]):
            selected = review_duplicate_files(group, set())
            self.assertEqual(selected, {"/tmp/copy2.iso"})

    def test_empty_response_never_approves_in_main_menu(self):
        groups = [
            {
                "group_id": "disposable_caches",
                "category_name": "Disposable Caches",
                "risk_level": "LOW",
                "is_selectable": True,
                "items": [{"path": "/tmp/test", "size_bytes": 100}]
            }
        ]
        # User presses Enter (empty string), then types "quit"
        with patch("builtins.input", side_effect=["", "quit"]):
            approved, custom = review_and_approve(groups, non_interactive=False)
            self.assertEqual(approved, set())
            self.assertEqual(custom, {})

    def test_explicit_confirmation_in_execution_skips_on_empty(self):
        groups = [
            {
                "group_id": "disposable_caches",
                "category_name": "Disposable Caches",
                "risk_level": "LOW",
                "is_selectable": True,
                "items": [{"path": "/tmp/nonexistent_test", "size_bytes": 100}]
            }
        ]
        # Simulate user pressing Enter (empty input "") at confirmation prompt
        with patch("builtins.input", side_effect=[""]):
            summary = execute_approved_actions(
                groups=groups,
                approved_group_ids={"disposable_caches"},
                non_interactive=False,
                dry_run=True
            )
            # Group should be skipped because confirmation was not explicitly "yes" or "y"
            self.assertEqual(summary["total_reclaimed_bytes"], 0)
            self.assertEqual(len(summary["skipped_items"]), 1)
            self.assertIn("declined or skipped", summary["skipped_items"][0]["reason"])

    def test_explicit_confirmation_in_execution_executes_on_yes(self):
        groups = [
            {
                "group_id": "disposable_caches",
                "category_name": "Disposable Caches",
                "risk_level": "LOW",
                "is_selectable": True,
                "items": [{"path": "/tmp/nonexistent_test", "size_bytes": 100}]
            }
        ]
        # Simulate user typing "yes"
        with patch("builtins.input", side_effect=["yes"]):
            summary = execute_approved_actions(
                groups=groups,
                approved_group_ids={"disposable_caches"},
                non_interactive=False,
                dry_run=True
            )
            # Execution proceeded to process the item (which was nonexistent on disk in this mock)
            self.assertEqual(len(summary["skipped_items"]), 0)

if __name__ == "__main__":
    unittest.main()
