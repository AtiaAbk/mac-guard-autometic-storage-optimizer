"""
Concurrency control: Prevents overlapping MacGuard missions via atomic lock file.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Optional
from macguard.config import get_lock_file

class LockError(Exception):
    """Raised when another MacGuard mission is already in progress."""
    pass

class MissionLock:
    """
    Ensures only a single MacGuard mission runs at any given time.
    Detects and clears stale locks from terminated processes.
    """

    def __init__(self, lock_path: Optional[Path] = None):
        self.lock_path = lock_path or get_lock_file()
        self.acquired = False

    def is_pid_running(self, pid: int) -> bool:
        """Check if process with PID is currently running."""
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # Running under another user, process exists
            return True

    def acquire(self) -> None:
        """Acquire the mission lock. Raises LockError if another active mission exists."""
        if self.lock_path.exists():
            try:
                content = self.lock_path.read_text().strip()
                if content:
                    parts = content.split(":")
                    old_pid = int(parts[0])
                    timestamp = parts[1] if len(parts) > 1 else "unknown"
                    if self.is_pid_running(old_pid):
                        raise LockError(
                            f"Another MacGuard mission (PID {old_pid}) is already running (started {timestamp}).\n"
                            "Concurrent missions are prevented to avoid conflicting modifications."
                        )
                    else:
                        # Stale lock from a dead process
                        self.lock_path.unlink(missing_ok=True)
            except (ValueError, IndexError):
                self.lock_path.unlink(missing_ok=True)

        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            self.lock_path.write_text(f"{os.getpid()}:{now}\n")
            self.acquired = True
        except Exception as e:
            raise LockError(f"Failed to create lock file at {self.lock_path}: {e}")

    def release(self) -> None:
        """Release the mission lock."""
        if self.acquired:
            try:
                if self.lock_path.exists():
                    # Only remove if it contains our PID
                    content = self.lock_path.read_text().strip()
                    if content.startswith(f"{os.getpid()}:"):
                        self.lock_path.unlink(missing_ok=True)
            except Exception:
                pass
            finally:
                self.acquired = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
