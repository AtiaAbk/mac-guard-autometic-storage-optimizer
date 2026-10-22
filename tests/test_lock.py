"""
Unit tests for Concurrency Lock and Stale Lock Recovery.
"""

import os
import tempfile
import unittest
from pathlib import Path
from macguard.utils.lock import MissionLock, LockError

class TestMissionLock(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.lock_file = Path(self.temp_dir) / "test.lock"

    def tearDown(self):
        if self.lock_file.exists():
            self.lock_file.unlink()
        os.rmdir(self.temp_dir)

    def test_acquire_and_release(self):
        lock = MissionLock(self.lock_file)
        lock.acquire()
        self.assertTrue(self.lock_file.exists())
        self.assertTrue(lock.acquired)
        lock.release()
        self.assertFalse(self.lock_file.exists())

    def test_blocks_concurrent_mission(self):
        lock1 = MissionLock(self.lock_file)
        lock1.acquire()

        lock2 = MissionLock(self.lock_file)
        with self.assertRaises(LockError):
            lock2.acquire()

        lock1.release()

    def test_clears_stale_lock_from_dead_pid(self):
        # Write lock with a guaranteed dead PID (e.g. 9999999)
        self.lock_file.write_text("9999999:2026-01-01 00:00:00\n")

        lock = MissionLock(self.lock_file)
        # Should detect dead PID, clear stale lock, and acquire cleanly
        lock.acquire()
        self.assertTrue(lock.acquired)
        lock.release()

if __name__ == "__main__":
    unittest.main()
