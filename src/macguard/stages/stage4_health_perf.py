"""
Stage 4: Battery Health, Performance, and System Pressure Assessment.

Evaluates:
- Battery status, cycle count, condition
- Memory pressure, swap usage, page faults
- CPU load averages and top active processes
- Login items and user LaunchAgents
- Generates actionable performance recommendations
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, Any, List
from macguard.utils.system import run_cmd

def assess_health_and_performance() -> Dict[str, Any]:
    """Inspects battery health, CPU/memory pressure, and login items."""
    results: Dict[str, Any] = {
        "battery": {
            "has_battery": False,
            "status": "Unknown",
            "percentage": 0,
            "power_source": "Unknown",
            "cycle_count": None,
            "condition": "Unknown"
        },
        "memory": {
            "page_size_bytes": 16384,
            "free_pages": 0,
            "active_pages": 0,
            "inactive_pages": 0,
            "wired_pages": 0,
            "compressed_pages": 0,
            "swap_usage": "Unknown",
            "pressure_level": "Normal"
        },
        "cpu": {
            "load_averages": [0.0, 0.0, 0.0],
            "top_processes": []
        },
        "login_items": [],
        "recommendations": []
    }

    # 1. Battery Assessment via pmset
    rc, stdout, _ = run_cmd(["pmset", "-g", "batt"])
    if rc == 0 and stdout:
        if "InternalBattery" in stdout:
            results["battery"]["has_battery"] = True
            if "AC Power" in stdout:
                results["battery"]["power_source"] = "AC Power"
            elif "Battery Power" in stdout:
                results["battery"]["power_source"] = "Battery Power"

            pct_match = re.search(r'(\d+)%', stdout)
            if pct_match:
                results["battery"]["percentage"] = int(pct_match.group(1))

            status_match = re.search(r';\s*([^;]+?);', stdout)
            if status_match:
                results["battery"]["status"] = status_match.group(1).strip()

    # Battery cycle count via system_profiler
    rc, stdout, _ = run_cmd(["system_profiler", "SPPowerDataType"], timeout=5)
    if rc == 0 and stdout:
        cycle_match = re.search(r'Cycle Count:\s*(\d+)', stdout)
        if cycle_match:
            results["battery"]["cycle_count"] = int(cycle_match.group(1))
        condition_match = re.search(r'Condition:\s*([^\n\r]+)', stdout)
        if condition_match:
            results["battery"]["condition"] = condition_match.group(1).strip()

    # 2. CPU Load Averages
    try:
        loads = os.getloadavg()
        results["cpu"]["load_averages"] = [round(x, 2) for x in loads]
    except Exception:
        pass

    # 3. Top Active Processes by CPU and Memory
    rc, stdout, _ = run_cmd(["ps", "-A", "-o", "pid,%cpu,%mem,comm", "-r"], timeout=5)
    if rc == 0 and stdout:
        lines = stdout.splitlines()
        top_procs: List[Dict[str, Any]] = []
        for line in lines[1:11]:  # Top 10
            parts = line.split(None, 3)
            if len(parts) == 4:
                try:
                    top_procs.append({
                        "pid": int(parts[0]),
                        "cpu_pct": float(parts[1]),
                        "mem_pct": float(parts[2]),
                        "command": parts[3].strip()
                    })
                except ValueError:
                    continue
        results["cpu"]["top_processes"] = top_procs

    # 4. Memory Pressure & vm_stat
    rc, stdout, _ = run_cmd(["vm_stat"], timeout=5)
    if rc == 0 and stdout:
        for line in stdout.splitlines():
            if "page size of" in line:
                m = re.search(r'page size of (\d+) bytes', line)
                if m:
                    results["memory"]["page_size_bytes"] = int(m.group(1))
            elif "Pages free:" in line:
                m = re.search(r'(\d+)', line)
                if m:
                    results["memory"]["free_pages"] = int(m.group(1))
            elif "Pages active:" in line:
                m = re.search(r'(\d+)', line)
                if m:
                    results["memory"]["active_pages"] = int(m.group(1))
            elif "Pages inactive:" in line:
                m = re.search(r'(\d+)', line)
                if m:
                    results["memory"]["inactive_pages"] = int(m.group(1))
            elif "Pages wired down:" in line:
                m = re.search(r'(\d+)', line)
                if m:
                    results["memory"]["wired_pages"] = int(m.group(1))
            elif "Pages occupied by compressor:" in line:
                m = re.search(r'(\d+)', line)
                if m:
                    results["memory"]["compressed_pages"] = int(m.group(1))

    # Swap usage
    rc, stdout, _ = run_cmd(["sysctl", "-n", "vm.swapusage"])
    if rc == 0 and stdout:
        results["memory"]["swap_usage"] = stdout

    # 5. Login Items / User LaunchAgents
    user_agents = Path.home() / "Library" / "LaunchAgents"
    if user_agents.exists() and user_agents.is_dir():
        try:
            for item in user_agents.glob("*.plist"):
                results["login_items"].append({
                    "name": item.stem,
                    "path": str(item)
                })
        except Exception:
            pass

    # 6. Performance Recommendations
    recs: List[str] = []
    if results["battery"]["has_battery"]:
        condition = results["battery"]["condition"].lower()
        if "normal" not in condition and condition != "unknown":
            recs.append(f"Battery condition is reported as '{results['battery']['condition']}'. Consider hardware check.")
        if results["battery"]["cycle_count"] and results["battery"]["cycle_count"] > 1000:
            recs.append(f"Battery cycle count is high ({results['battery']['cycle_count']} cycles). Battery health may be degraded.")

    # High load check
    cpu_cores = os.cpu_count() or 1
    if results["cpu"]["load_averages"][0] > (cpu_cores * 1.5):
        recs.append(f"High CPU load average ({results['cpu']['load_averages'][0]} on {cpu_cores} cores). Check top energy processes.")

    # Top energy hog warning
    for proc in results["cpu"]["top_processes"][:3]:
        if proc["cpu_pct"] > 80.0:
            recs.append(f"Process {Path(proc['command']).name} (PID {proc['pid']}) is utilizing {proc['cpu_pct']}% CPU.")

    # Memory pressure check
    free_mb = (results["memory"]["free_pages"] * results["memory"]["page_size_bytes"]) / (1024 * 1024)
    if free_mb < 250:
        results["memory"]["pressure_level"] = "Elevated"
        recs.append("Available free memory is low (< 250 MB). Inactive pages and caches are being paged.")

    if not recs:
        recs.append("System health and thermal metrics are within normal parameters.")

    results["recommendations"] = recs
    return results
