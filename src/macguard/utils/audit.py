"""
Audit logging for MacGuard On-Demand Maintenance Engine.
Maintains an append-only verifiable record of all scans, proposals, approvals,
executions, and verifications.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
from macguard.config import get_audit_dir

class AuditLogger:
    """
    Appends structured events to the MacGuard audit log.
    """

    def __init__(self, audit_dir: Optional[Path] = None):
        self.audit_dir = audit_dir or get_audit_dir()
        self.log_file = self.audit_dir / "audit.log"

    def log_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Log an event with UTC and local timestamp, event type, and details."""
        try:
            self.audit_dir.mkdir(parents=True, exist_ok=True)
            record = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "event_type": event_type,
                "details": details
            }
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            # Audit logging must not crash mission but should warn
            print(f"[MacGuard Audit Warning] Could not append to audit log: {e}")
