"""
Configuration and constants for MacGuard On-Demand Maintenance Engine.
"""

from __future__ import annotations

import os
from pathlib import Path

# Base MacGuard directory configuration
DEFAULT_MACGUARD_DIR = Path(os.path.expanduser("~/.macguard"))

def get_macguard_home() -> Path:
    """
    Returns the MacGuard home directory.
    Respects MACGUARD_HOME env var if set.
    Gracefully falls back to workspace or /tmp if home dir is not writable.
    """
    custom = os.getenv("MACGUARD_HOME")
    if custom:
        path = Path(custom)
    else:
        path = DEFAULT_MACGUARD_DIR

    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".write_test"
        test_file.touch()
        test_file.unlink()
        return path
    except (PermissionError, OSError):
        fallback = Path.cwd() / ".macguard"
        try:
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback
        except (PermissionError, OSError):
            tmp_fallback = Path("/tmp/.macguard")
            tmp_fallback.mkdir(parents=True, exist_ok=True)
            return tmp_fallback

MACGUARD_HOME = get_macguard_home()

def get_reports_dir() -> Path:
    reports = MACGUARD_HOME / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    return reports

def get_audit_dir() -> Path:
    audit = MACGUARD_HOME / "audit"
    audit.mkdir(parents=True, exist_ok=True)
    return audit

def get_lock_file() -> Path:
    return MACGUARD_HOME / "macguard.lock"

# Storage Scanning Defaults
LARGE_FILE_THRESHOLD_BYTES = 250 * 1024 * 1024  # 250 MB
OLD_INSTALLER_AGE_DAYS = 14
OLD_LOG_AGE_DAYS = 7
DUPLICATE_MIN_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB

# Blocked extensions and filenames that must NEVER be deleted automatically
ESSENTIAL_EXTENSIONS = {
    ".keychain", ".keychain-db", ".pem", ".crt", ".key",
    ".sqlite", ".sqlite3", ".db",
    ".git", ".svn", ".hg",
    ".docx", ".xlsx", ".pptx", ".pdf", ".pages", ".numbers",
    ".swift", ".py", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".m", ".ts", ".js",
    ".toml", ".yaml", ".yml", ".ini", ".env", ".conf", ".json"
}

# High-risk / Protected Root Paths (Case-insensitive prefix matches)
PROTECTED_PREFIXES = [
    "/System",
    "/usr",
    "/bin",
    "/sbin",
    "/etc",
    "/private/etc",
    "/private/var",
    "/var/db",
    "/Library/Apple",
    "/Library/Frameworks",
    "/Library/KernelExtensions",
    "/Library/Preferences/SystemConfiguration",
]
