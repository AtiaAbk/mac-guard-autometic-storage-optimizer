"""
Stage 5: Classification Engine.

Classifies all discovered findings by:
- Risk Level: LOW, MEDIUM, HIGH, PROTECTED
- Usefulness: DISPOSABLE, TRANSIENT, POTENTIAL_UTILITY, ESSENTIAL
- Confidence Score: 0.0 - 1.0
- Recommended Action: APPROVE, REVIEW_REQUIRED, REJECT, KEEP
Groups findings into logical action categories for consolidated review.
"""

from __future__ import annotations

from typing import Dict, Any, List
from macguard.utils.disk import format_bytes

def classify_findings(
    storage_scan: Dict[str, Any],
    vmware_scan: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Groups and classifies discovered items into clean, actionable proposal groups.
    """
    groups: List[Dict[str, Any]] = []

    # 1. Disposable Application Caches (LOW RISK)
    cache_items = storage_scan.get("caches", [])
    if cache_items:
        total_size = sum(item["size_bytes"] for item in cache_items)
        total_files = sum(item.get("file_count", 1) for item in cache_items)
        groups.append({
            "group_id": "disposable_caches",
            "category_name": "Verified Disposable Application Caches",
            "risk_level": "LOW",
            "usefulness": "DISPOSABLE",
            "confidence": 0.98,
            "recommended_action": "APPROVE",
            "description": "Transient app caches (browsers, temporary assets) that can be safely deleted; regenerated as needed.",
            "is_selectable": True,
            "default_approved": False,  # User must still approve, but this is recommended
            "total_bytes": total_size,
            "total_human": format_bytes(total_size),
            "file_count": total_files,
            "items": [
                {
                    "path": item["path"],
                    "name": item["name"],
                    "size_bytes": item["size_bytes"],
                    "size_human": format_bytes(item["size_bytes"]),
                    "file_count": item.get("file_count", 1),
                    "action": "DELETE_CACHE_DIR"
                }
                for item in cache_items
            ]
        })

    # 2. Developer Build Artifacts (LOW RISK)
    dev_items = storage_scan.get("developer_artifacts", [])
    if dev_items:
        total_size = sum(item["size_bytes"] for item in dev_items)
        total_files = sum(item.get("file_count", 1) for item in dev_items)
        groups.append({
            "group_id": "dev_artifacts",
            "category_name": "Developer Build Artifacts & Package Caches",
            "risk_level": "LOW",
            "usefulness": "DISPOSABLE",
            "confidence": 0.95,
            "recommended_action": "APPROVE",
            "description": "Rebuildable developer caches (Xcode DerivedData, pip cache, Homebrew downloads).",
            "is_selectable": True,
            "default_approved": False,
            "total_bytes": total_size,
            "total_human": format_bytes(total_size),
            "file_count": total_files,
            "items": [
                {
                    "path": item["path"],
                    "name": item["name"],
                    "size_bytes": item["size_bytes"],
                    "size_human": format_bytes(item["size_bytes"]),
                    "file_count": item.get("file_count", 1),
                    "action": "DELETE_CACHE_DIR"
                }
                for item in dev_items
            ]
        })

    # 3. Old Application & User Logs (MEDIUM RISK)
    log_items = storage_scan.get("logs", [])
    if log_items:
        total_size = sum(item["size_bytes"] for item in log_items)
        total_files = sum(item.get("file_count", 1) for item in log_items)
        groups.append({
            "group_id": "application_logs",
            "category_name": "Old Application and Diagnostic Logs",
            "risk_level": "MEDIUM",
            "usefulness": "TRANSIENT",
            "confidence": 0.85,
            "recommended_action": "REVIEW_REQUIRED",
            "description": "Historical diagnostic log files. Safe to clear unless actively debugging a recent crash.",
            "is_selectable": True,
            "default_approved": False,
            "total_bytes": total_size,
            "total_human": format_bytes(total_size),
            "file_count": total_files,
            "items": [
                {
                    "path": item["path"],
                    "name": item["name"],
                    "size_bytes": item["size_bytes"],
                    "size_human": format_bytes(item["size_bytes"]),
                    "file_count": item.get("file_count", 1),
                    "action": "DELETE_LOG_FILE"
                }
                for item in log_items
            ]
        })

    # 4. Old Installers (.dmg, .pkg, .iso) (MEDIUM RISK)
    installer_items = storage_scan.get("installers", [])
    if installer_items:
        total_size = sum(item["size_bytes"] for item in installer_items)
        groups.append({
            "group_id": "old_installers",
            "category_name": "Downloaded Disk Images & Installers (.dmg / .pkg)",
            "risk_level": "MEDIUM",
            "usefulness": "POTENTIAL_UTILITY",
            "confidence": 0.80,
            "recommended_action": "REVIEW_REQUIRED",
            "description": "Disk images and installers in Downloads/Desktop. Review before deleting in case original is needed.",
            "is_selectable": True,
            "default_approved": False,
            "total_bytes": total_size,
            "total_human": format_bytes(total_size),
            "file_count": len(installer_items),
            "items": [
                {
                    "path": item["path"],
                    "name": item["name"],
                    "size_bytes": item["size_bytes"],
                    "size_human": format_bytes(item["size_bytes"]),
                    "age_days": item.get("age_days", 0),
                    "action": "DELETE_INSTALLER"
                }
                for item in installer_items
            ]
        })

    # 5. Duplicate Candidates (HIGH RISK)
    dup_items = storage_scan.get("duplicates", [])
    if dup_items:
        # Sum of potential savings = (count - 1) * size
        total_savings = sum(item["potential_savings_bytes"] for item in dup_items)
        total_files = sum(item["count"] for item in dup_items)
        groups.append({
            "group_id": "duplicate_candidates",
            "category_name": "Identical Duplicate File Candidates",
            "risk_level": "HIGH",
            "usefulness": "POTENTIAL_UTILITY",
            "confidence": 0.70,
            "recommended_action": "REJECT",  # Default reject by policy
            "description": "Cryptographically matching files with identical sizes and SHA256 hashes. Review individually.",
            "is_selectable": True,
            "default_approved": False,
            "total_bytes": total_savings,
            "total_human": format_bytes(total_savings),
            "file_count": total_files,
            "items": [
                {
                    "path": str(item["paths"]),
                    "name": f"Set of {item['count']} duplicates ({format_bytes(item['size_bytes'])} each)",
                    "size_bytes": item["potential_savings_bytes"],
                    "size_human": format_bytes(item["potential_savings_bytes"]),
                    "duplicates": item["paths"],
                    "action": "REVIEW_DUPLICATES"
                }
                for item in dup_items
            ]
        })

    # 6. Local AI Models (HIGH RISK / INFORMATIONAL)
    ai_models = storage_scan.get("local_ai_models", [])
    if ai_models:
        total_size = sum(item["size_bytes"] for item in ai_models)
        total_files = sum(item.get("file_count", 1) for item in ai_models)
        groups.append({
            "group_id": "local_ai_models",
            "category_name": "Local AI Models & Weights (Ollama / HuggingFace / LM Studio)",
            "risk_level": "HIGH",
            "usefulness": "ESSENTIAL",
            "confidence": 0.90,
            "recommended_action": "KEEP",
            "description": "Downloaded LLM weights and local model storage. Kept intact to avoid re-downloading large models.",
            "is_selectable": False,
            "default_approved": False,
            "total_bytes": total_size,
            "total_human": format_bytes(total_size),
            "file_count": total_files,
            "items": [
                {
                    "path": item["path"],
                    "name": item["name"],
                    "size_bytes": item["size_bytes"],
                    "size_human": format_bytes(item["size_bytes"]),
                    "file_count": item.get("file_count", 1),
                    "action": "KEEP_PROTECTED"
                }
                for item in ai_models
            ]
        })

    # 7. VMware Virtual Machines (PROTECTED / INFORMATIONAL)
    vms = vmware_scan.get("discovered_vms", [])
    if vms:
        total_size = vmware_scan.get("total_vm_storage_bytes", 0)
        total_files = sum(item.get("file_count", 1) for item in vms)
        groups.append({
            "group_id": "vmware_vms",
            "category_name": "VMware Virtual Machines (Ubuntu / Windows / Guests)",
            "risk_level": "PROTECTED",
            "usefulness": "ESSENTIAL",
            "confidence": 1.0,
            "recommended_action": "KEEP",
            "description": "Host-side virtual machine bundles (.vmwarevm), virtual disks (.vmdk), and snapshots. Never modified.",
            "is_selectable": False,
            "default_approved": False,
            "total_bytes": total_size,
            "total_human": format_bytes(total_size),
            "file_count": total_files,
            "items": [
                {
                    "path": item["bundle_path"],
                    "name": f"{item['display_name']} ({item['guest_os']})",
                    "size_bytes": item["size_bytes"],
                    "size_human": item["size_human"],
                    "snapshots": item["snapshots_count"],
                    "action": "KEEP_PROTECTED"
                }
                for item in vms
            ]
        })

    return groups
