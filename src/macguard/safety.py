"""
Safety Policy and Path Verification for MacGuard.

Strictly protects system paths, personal files, source code, databases,
credentials, VM disks, and snapshots.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple, List, Optional
from macguard.config import PROTECTED_PREFIXES, ESSENTIAL_EXTENSIONS

class SafetyViolationError(Exception):
    """Raised when an operation attempts to violate MacGuard safety policies."""
    pass

class SafetyPolicy:
    """
    Validates all candidate paths and operations against strict safety policies.
    """

    @staticmethod
    def is_system_path(path: Path) -> bool:
        """Check if path falls under protected macOS system paths."""
        resolved = str(path.resolve())
        for prefix in PROTECTED_PREFIXES:
            if resolved == prefix or resolved.startswith(prefix + "/"):
                return True
        return False

    @staticmethod
    def is_source_or_document(path: Path) -> bool:
        """Check if path is personal document, database, or project source code."""
        if path.suffix.lower() in ESSENTIAL_EXTENSIONS:
            return True
        # Check if inside a .git directory or hidden credential dir
        parts = path.parts
        if ".git" in parts or ".ssh" in parts or ".gnupg" in parts:
            return True
        return False

    @staticmethod
    def is_vm_storage(path: Path) -> bool:
        """Check if path is a virtual machine disk, snapshot, or bundle."""
        ext = path.suffix.lower()
        if ext in {".vmwarevm", ".vmdk", ".vmem", ".vmss", ".vmsd", ".nvram", ".iso", ".qcow2", ".vdi"}:
            return True
        # If part of Virtual Machines directory
        for p in path.parts:
            if "virtual machine" in p.lower():
                return True
        return False

    @staticmethod
    def check_permissions(path: Path) -> Tuple[bool, Optional[str]]:
        """
        Checks if current user has write permissions without needing elevated privileges.
        Never requests or prompts for passwords.
        """
        if not path.exists():
            return True, None

        if not os.access(str(path), os.W_OK):
            return False, (
                f"Path '{path}' requires elevated administrator privileges. "
                "MacGuard does not request or store passwords. "
                f"To remove manually if desired, run in a separate terminal: sudo rm -rf '{path}'"
            )

        parent = path.parent
        if parent.exists() and not os.access(str(parent), os.W_OK):
            return False, (
                f"Parent directory '{parent}' is write-protected. "
                f"To remove manually, run: sudo rm -rf '{path}'"
            )

        return True, None

    @staticmethod
    def validate_for_deletion(path: Path, allow_synthetic: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Validates whether a path is strictly safe to delete if approved.
        Returns (is_safe, refusal_reason).
        """
        try:
            resolved = path.resolve()
        except Exception as e:
            return False, f"Could not resolve path safely: {e}"

        # Synthetic test directories are allowed if explicitly flagged
        if allow_synthetic and (
            ".macguard_synthetic_test" in str(resolved) or
            ".macguard_autoclean_test" in str(resolved)
        ):
            return True, None

        # Check system paths first
        if SafetyPolicy.is_system_path(resolved):
            return False, f"Path '{resolved}' is a protected macOS system location."

        # Prohibit deleting active keychain / sensitive system config
        if any(sens in str(resolved) for sens in ["/Library/Keychains", "/etc/hosts", "/etc/resolv.conf"]):
            return False, f"Path '{resolved}' is sensitive system configuration."

        # Check VM storage
        if SafetyPolicy.is_vm_storage(resolved):
            return False, f"Path '{resolved}' is a Virtual Machine resource (strictly protected)."

        # Check source code / documents
        if SafetyPolicy.is_source_or_document(resolved):
            return False, f"Path '{resolved}' contains protected document or code extension ({resolved.suffix})."

        # Check root or user root
        user_home = Path.home().resolve()
        if resolved == user_home or resolved == Path("/"):
            return False, f"Path '{resolved}' is the user home or filesystem root."

        # Check permissions and privilege requirement
        perm_ok, perm_err = SafetyPolicy.check_permissions(resolved)
        if not perm_ok:
            return False, perm_err

        return True, None
