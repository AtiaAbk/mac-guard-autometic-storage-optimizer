"""
Stage 3: VMware Virtual Machine Discovery and Inspection.

Discovers VMware VMs, parses .vmx configs (read-only), measures host-side
storage (bundles, .vmdk disks, .vmsd snapshots, .vmem memory files), identifies
guest OS (e.g. Ubuntu, Windows), and strictly marks all VM resources as PROTECTED.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, Any, List
from macguard.utils.disk import get_path_size, format_bytes
from macguard.utils.system import run_cmd

def parse_vmx(vmx_path: Path) -> Dict[str, str]:
    """Parse a .vmx file safely (read-only) into key-value pairs."""
    config: Dict[str, str] = {}
    try:
        with open(vmx_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                match = re.match(r'^([^=]+?)\s*=\s*"(.*)"\s*$', line)
                if match:
                    k, v = match.group(1).strip(), match.group(2).strip()
                    config[k.lower()] = v
    except Exception:
        pass
    return config

def inspect_vmware() -> Dict[str, Any]:
    """
    Discovers and inspects VMware Fusion VMs. Read-only.
    """
    results: Dict[str, Any] = {
        "fusion_installed": False,
        "running_vms": [],
        "discovered_vms": [],
        "total_vm_storage_bytes": 0,
        "total_vm_storage_human": "0 B"
    }

    # Check if VMware Fusion is installed
    fusion_app = Path("/Applications/VMware Fusion.app")
    if fusion_app.exists():
        results["fusion_installed"] = True

    # Check running VMs via vmrun
    vmrun_path = Path("/Applications/VMware Fusion.app/Contents/Public/vmrun")
    if vmrun_path.exists():
        rc, stdout, _ = run_cmd([str(vmrun_path), "-T", "fusion", "list"], timeout=5)
        if rc == 0:
            lines = stdout.splitlines()
            for line in lines[1:]:  # skip 'Total running VMs: X'
                if line.strip():
                    results["running_vms"].append(line.strip())

    user_home = Path.home()
    candidate_vm_dirs = [
        user_home / "Virtual Machines",
        user_home / "Virtual Machines.localized",
        user_home / "Documents" / "Virtual Machines",
        user_home / "Documents" / "Virtual Machines.localized",
    ]

    total_storage = 0
    found_bundles: List[Path] = []

    for base_dir in candidate_vm_dirs:
        if base_dir.exists() and base_dir.is_dir():
            try:
                for entry in os.scandir(str(base_dir)):
                    try:
                        p = Path(entry.path)
                        if entry.is_dir() and p.suffix.lower() == ".vmwarevm":
                            found_bundles.append(p)
                    except (PermissionError, OSError):
                        pass
            except (PermissionError, OSError):
                pass

    for bundle in found_bundles:
        bundle_size, file_count = get_path_size(bundle)
        total_storage += bundle_size

        vm_details: Dict[str, Any] = {
            "name": bundle.stem,
            "bundle_path": str(bundle),
            "size_bytes": bundle_size,
            "size_human": format_bytes(bundle_size),
            "file_count": file_count,
            "guest_os": "Unknown",
            "display_name": bundle.stem,
            "memsize_mb": 0,
            "numvcpus": 1,
            "snapshots_count": 0,
            "vmdk_count": 0,
            "is_running": False,
            "safety_classification": "PROTECTED_INFORMATIONAL"
        }

        # Check if running
        for r_vm in results["running_vms"]:
            if str(bundle) in r_vm:
                vm_details["is_running"] = True
                break

        # Find .vmx file
        vmx_files = list(bundle.glob("*.vmx"))
        if vmx_files:
            cfg = parse_vmx(vmx_files[0])
            vm_details["display_name"] = cfg.get("displayname", bundle.stem)
            vm_details["guest_os"] = cfg.get("guestos", "Unknown")
            vm_details["memsize_mb"] = int(cfg.get("memsize", "0"))
            vm_details["numvcpus"] = int(cfg.get("numvcpus", "1"))

        # Inspect snapshots (.vmsd file or -00000X.vmdk files)
        vmdks = list(bundle.glob("*.vmdk"))
        vm_details["vmdk_count"] = len(vmdks)
        snapshot_vmdks = [v for v in vmdks if re.search(r'-\d{5,6}\.vmdk$', v.name)]
        vm_details["snapshots_count"] = len(snapshot_vmdks)

        results["discovered_vms"].append(vm_details)

    results["total_vm_storage_bytes"] = total_storage
    results["total_vm_storage_human"] = format_bytes(total_storage)
    return results
