"""
Stage 5: Risk & Usefulness Classification Engine.

Classifies all discovered findings into strict risk tiers:
- LOW: Disposable caches, temporary files, build caches (safe to clean)
- MEDIUM: Old logs, old installers (.dmg, .pkg, .iso, .zip) (review required)
- HIGH: Duplicate candidates, Docker storage (review required, keep original)
- PROTECTED: VMware virtual machines, local AI models, source code, documents (shielded)
"""

from __future__ import annotations

from typing import Dict, Any, List
from macguard.utils.disk import format_bytes

def classify_findings(
    storage_scan: Dict[str, Any],
    vmware_scan: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Groups and classifies discovered items into clean, actionable proposal categories.
    """
    groups: List[Dict[str, Any]] = []

    # 1. Remaining Disposable Application Caches (LOW RISK)
    cache_items = storage_scan.get("caches", []) + storage_scan.get("browser_caches", [])
    if cache_items:
        total_size = sum(item.get("apparent_bytes", item.get("size_bytes", 0)) for item in cache_items)
        total_files = sum(item.get("file_count", 1) for item in cache_items)
        groups.append({
            "group_id": "disposable_caches",
            "category_name": "Application & Web Browser Caches",
            "risk_level": "LOW",
            "usefulness": "DISPOSABLE",
            "confidence": 0.98,
            "recommended_action": "APPROVE",
            "description": "Transient application and web caches. Automatically regenerates as needed.",
            "is_selectable": True,
            "default_approved": False,
            "total_bytes": total_size,
            "total_human": format_bytes(total_size),
            "file_count": total_files,
            "items": [
                {
                    "path": item["path"],
                    "name": item["name"],
                    "size_bytes": item.get("apparent_bytes", item.get("size_bytes", 0)),
                    "size_human": format_bytes(item.get("apparent_bytes", item.get("size_bytes", 0))),
                    "allocated_human": format_bytes(item.get("allocated_bytes", 0)),
                    "file_count": item.get("file_count", 1),
                    "action": "DELETE_CACHE_DIR"
                }
                for item in cache_items
            ]
        })

    # 2. Developer Build Artifacts (LOW RISK)
    dev_items = storage_scan.get("developer_artifacts", [])
    if dev_items:
        total_size = sum(item.get("apparent_bytes", item.get("size_bytes", 0)) for item in dev_items)
        total_files = sum(item.get("file_count", 1) for item in dev_items)
        groups.append({
            "group_id": "dev_artifacts",
            "category_name": "Developer Build Artifacts & Package Caches",
            "risk_level": "LOW",
            "usefulness": "DISPOSABLE",
            "confidence": 0.95,
            "recommended_action": "APPROVE",
            "description": "Xcode DerivedData, CocoaPods, SwiftPM, and pip/npm build caches.",
            "is_selectable": True,
            "default_approved": False,
            "total_bytes": total_size,
            "total_human": format_bytes(total_size),
            "file_count": total_files,
            "items": [
                {
                    "path": item["path"],
                    "name": item["name"],
                    "size_bytes": item.get("apparent_bytes", item.get("size_bytes", 0)),
                    "size_human": format_bytes(item.get("apparent_bytes", item.get("size_bytes", 0))),
                    "allocated_human": format_bytes(item.get("allocated_bytes", 0)),
                    "file_count": item.get("file_count", 1),
                    "action": "DELETE_CACHE_DIR"
                }
                for item in dev_items
            ]
        })

    # 3. Old Application & Diagnostic Logs (MEDIUM RISK)
    log_items = storage_scan.get("logs", []) + storage_scan.get("crash_reports", [])
    if log_items:
        total_size = sum(item.get("apparent_bytes", item.get("size_bytes", 0)) for item in log_items)
        total_files = sum(item.get("file_count", 1) for item in log_items)
        groups.append({
            "group_id": "application_logs",
            "category_name": "Diagnostic Logs & Crash Reports",
            "risk_level": "MEDIUM",
            "usefulness": "TRANSIENT",
            "confidence": 0.85,
            "recommended_action": "REVIEW_REQUIRED",
            "description": "Historical crash reports (DiagnosticReports) and diagnostic logs.",
            "is_selectable": True,
            "default_approved": False,
            "total_bytes": total_size,
            "total_human": format_bytes(total_size),
            "file_count": total_files,
            "items": [
                {
                    "path": item["path"],
                    "name": item["name"],
                    "size_bytes": item.get("apparent_bytes", item.get("size_bytes", 0)),
                    "size_human": format_bytes(item.get("apparent_bytes", item.get("size_bytes", 0))),
                    "allocated_human": format_bytes(item.get("allocated_bytes", 0)),
                    "file_count": item.get("file_count", 1),
                    "action": "DELETE_LOG_FILE"
                }
                for item in log_items
            ]
        })

    # 4. Old Installers (.dmg, .pkg, .iso, installer .zip) (MEDIUM RISK)
    installer_items = storage_scan.get("installers", [])
    if installer_items:
        total_size = sum(item.get("apparent_bytes", item.get("size_bytes", 0)) for item in installer_items)
        groups.append({
            "group_id": "old_installers",
            "category_name": "Downloaded Installers & Disk Images (.dmg, .pkg, .iso, .zip)",
            "risk_level": "MEDIUM",
            "usefulness": "POTENTIAL_UTILITY",
            "confidence": 0.80,
            "recommended_action": "REVIEW_REQUIRED",
            "description": "Disk images and installers in Downloads/Desktop. Review individual files.",
            "is_selectable": True,
            "default_approved": False,
            "total_bytes": total_size,
            "total_human": format_bytes(total_size),
            "file_count": len(installer_items),
            "items": [
                {
                    "path": item["path"],
                    "name": item["name"],
                    "size_bytes": item.get("apparent_bytes", item.get("size_bytes", 0)),
                    "size_human": format_bytes(item.get("apparent_bytes", item.get("size_bytes", 0))),
                    "allocated_human": format_bytes(item.get("allocated_bytes", 0)),
                    "age_days": item.get("age_days", 0),
                    "action": "DELETE_INSTALLER"
                }
                for item in installer_items
            ]
        })

    # 5. Duplicate Candidates (HIGH RISK - Requires Review, Keeps Original)
    dup_items = storage_scan.get("duplicates", [])
    if dup_items:
        total_savings = sum(item.get("potential_savings_bytes", 0) for item in dup_items)
        total_files = sum(item.get("total_copies", len(item.get("all_paths", item.get("paths", [])))) for item in dup_items)
        groups.append({
            "group_id": "duplicate_candidates",
            "category_name": "Identical Duplicate File Candidates (SHA256 Match)",
            "risk_level": "HIGH",
            "usefulness": "POTENTIAL_UTILITY",
            "confidence": 0.75,
            "recommended_action": "REVIEW_REQUIRED",
            "description": "Cryptographically matching files. Original copy is kept; only candidate duplicates targeted.",
            "is_selectable": True,
            "default_approved": False,
            "total_bytes": total_savings,
            "total_human": format_bytes(total_savings),
            "file_count": total_files,
            "items": [
                {
                    "path": item.get("original_path", str(item.get("all_paths", item.get("paths", [""])))[0]),
                    "name": f"Set of {item.get('total_copies', 2)} duplicate files ({item.get('size_human', '')} each)",
                    "size_bytes": item.get("potential_savings_bytes", 0),
                    "size_human": item.get("potential_savings_human", format_bytes(item.get("potential_savings_bytes", 0))),
                    "duplicates": item.get("all_paths", item.get("duplicate_paths", item.get("paths", []))),
                    "original": item.get("original_path", ""),
                    "action": "REVIEW_DUPLICATES"
                }
                for item in dup_items
            ]
        })

    # 6. Local AI Models (PROTECTED / DO NOT DELETE)
    ai_models = storage_scan.get("local_ai_models", [])
    if ai_models:
        total_size = sum(item.get("apparent_bytes", 0) for item in ai_models)
        total_files = sum(item.get("file_count", 1) for item in ai_models)
        groups.append({
            "group_id": "local_ai_models",
            "category_name": "Local AI Models & Weights (Ollama, HuggingFace, LM Studio, MLX)",
            "risk_level": "PROTECTED",
            "usefulness": "ESSENTIAL",
            "confidence": 1.0,
            "recommended_action": "KEEP",
            "description": "Downloaded LLM weights and neural network models. Kept intact to avoid re-downloading.",
            "is_selectable": False,
            "default_approved": False,
            "total_bytes": total_size,
            "total_human": format_bytes(total_size),
            "file_count": total_files,
            "items": [
                {
                    "path": item["path"],
                    "name": f"{item['name']} ({item['engine']})",
                    "size_bytes": item.get("apparent_bytes", 0),
                    "size_human": item.get("apparent_human", format_bytes(item.get("apparent_bytes", 0))),
                    "allocated_human": item.get("allocated_human", "0 B"),
                    "action": "KEEP_PROTECTED"
                }
                for item in ai_models
            ]
        })

    # 7. VMware Virtual Machines (STRICTLY PROTECTED)
    vms = vmware_scan.get("discovered_vms", [])
    if vms:
        total_size = vmware_scan.get("total_host_apparent_bytes", 0)
        total_files = sum(item.get("file_count", 1) for item in vms)
        groups.append({
            "group_id": "vmware_vms",
            "category_name": "VMware Fusion Virtual Machines (Ubuntu / Windows / Guests)",
            "risk_level": "PROTECTED",
            "usefulness": "ESSENTIAL",
            "confidence": 1.0,
            "recommended_action": "KEEP",
            "description": "Host-side VM bundles (.vmwarevm), virtual disks (.vmdk), and snapshots. Never modified.",
            "is_selectable": False,
            "default_approved": False,
            "total_bytes": total_size,
            "total_human": format_bytes(total_size),
            "file_count": total_files,
            "items": [
                {
                    "path": item["bundle_path"],
                    "name": f"{item['display_name']} (Guest: {item['guest_os']})",
                    "size_bytes": item["apparent_bytes"],
                    "size_human": item["apparent_human"],
                    "allocated_human": item["allocated_human"],
                    "snapshots": item["snapshot_chains"]["snapshot_count"],
                    "action": "KEEP_PROTECTED"
                }
                for item in vms
            ]
        })

    return groups
