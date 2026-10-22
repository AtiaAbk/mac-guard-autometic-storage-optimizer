"""
Stage 1: Environment Inspection and Configuration Validation.

Inspects current environment (macOS version, hardware, storage, SIP)
and verifies MacGuard has NO active launchd jobs, recurring daemons,
or automated schedules.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, Any, List
from macguard.utils.disk import get_disk_usage
from macguard.utils.system import run_cmd
from macguard.config import MACGUARD_HOME

def inspect_environment() -> Dict[str, Any]:
    """Inspects the macOS environment and validates on-demand configuration."""
    env_info: Dict[str, Any] = {
        "os": {},
        "hardware": {},
        "sip": "Unknown",
        "storage": {},
        "schedule_validation": {
            "is_purely_on_demand": True,
            "detected_schedulers": []
        },
        "config": {
            "macguard_home": str(MACGUARD_HOME),
            "python_version": sys.version.split()[0],
        }
    }

    # OS Info via sw_vers
    rc, stdout, _ = run_cmd(["sw_vers"])
    if rc == 0:
        for line in stdout.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                env_info["os"][k.strip()] = v.strip()

    # Hardware Info via sysctl
    rc, stdout, _ = run_cmd(["sysctl", "-n", "machdep.cpu.brand_string"])
    cpu_model = stdout if rc == 0 else "Apple Silicon / Unknown"
    rc, ncpu, _ = run_cmd(["sysctl", "-n", "hw.ncpu"])
    rc, memsize, _ = run_cmd(["sysctl", "-n", "hw.memsize"])
    mem_bytes = int(memsize) if memsize.isdigit() else 0

    env_info["hardware"] = {
        "cpu_model": cpu_model,
        "cpu_cores": int(ncpu) if ncpu.isdigit() else os.cpu_count() or 1,
        "ram_bytes": mem_bytes,
        "ram_gb": round(mem_bytes / (1024 ** 3), 1) if mem_bytes else 0
    }

    # SIP Status
    rc, stdout, _ = run_cmd(["csrutil", "status"])
    if rc == 0:
        env_info["sip"] = stdout
    else:
        env_info["sip"] = "Enabled (Restricted query)"

    # Initial Root Storage
    env_info["storage"]["root"] = get_disk_usage("/")
    user_home = Path.home()
    env_info["storage"]["user_home"] = get_disk_usage(user_home)

    # Validate that NO background schedules exist for MacGuard
    # Check LaunchAgents / LaunchDaemons
    launch_paths = [
        Path.home() / "Library" / "LaunchAgents",
        Path("/Library/LaunchAgents"),
        Path("/Library/LaunchDaemons"),
    ]
    detected_schedulers: List[str] = []
    for p in launch_paths:
        if p.exists() and p.is_dir():
            try:
                for item in p.glob("*macguard*"):
                    detected_schedulers.append(str(item))
            except (PermissionError, OSError):
                pass

    # Check crontab
    rc, stdout, _ = run_cmd(["crontab", "-l"])
    if rc == 0 and "macguard" in stdout.lower():
        detected_schedulers.append("User crontab contains macguard entry")

    if detected_schedulers:
        env_info["schedule_validation"]["is_purely_on_demand"] = False
        env_info["schedule_validation"]["detected_schedulers"] = detected_schedulers
    else:
        env_info["schedule_validation"]["is_purely_on_demand"] = True

    return env_info
