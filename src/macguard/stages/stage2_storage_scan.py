"""
Stage 2: Full Deep Storage & Artifacts Analysis.

Analyzes:
- Storage volumes & user directories (Downloads, Desktop, Documents, Trash)
- Application caches & temporary files (with browser breakdowns)
- Application logs & crash reports (DiagnosticReports)
- Old installers (.dmg, .pkg, .iso, installer .zip)
- Duplicate file candidates with reliable SHA256 hashes (identifying Original vs Copies)
- Development & build caches (Xcode DerivedData, CocoaPods, SwiftPM, pip, npm, gradle, cargo)
- Docker storage (images, containers, volumes)
- Local AI models (Ollama, HuggingFace, LM Studio, MLX)
- Top largest files and directories ranked by storage consumption
- Apparent size vs allocated disk space on blocks
- Inaccessible locations with permission explanations
"""

from __future__ import annotations

import os
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple

from macguard.config import (
    LARGE_FILE_THRESHOLD_BYTES,
    OLD_INSTALLER_AGE_DAYS,
    OLD_LOG_AGE_DAYS,
    DUPLICATE_MIN_SIZE_BYTES
)
from macguard.utils.disk import get_path_detailed_size, format_bytes
from macguard.utils.system import run_cmd
from macguard.safety import SafetyPolicy

def calculate_sha256(path: Path, max_bytes: int = 10 * 1024 * 1024) -> str:
    """Calculate SHA256 of the first max_bytes for fast comparison."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            chunk = f.read(max_bytes)
            h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""

def scan_storage(
    search_roots: List[Path] | None = None,
    synthetic_root: Path | None = None
) -> Dict[str, Any]:
    """
    Performs full deep storage analysis across accessible locations.
    """
    results: Dict[str, Any] = {
        "user_directories": {},
        "caches": [],
        "browser_caches": [],
        "logs": [],
        "crash_reports": [],
        "installers": [],
        "duplicates": [],
        "developer_artifacts": [],
        "docker_storage": {},
        "local_ai_models": [],
        "application_support_summary": [],
        "large_files": [],
        "largest_directories": [],
        "inaccessible_locations": [],
        "summary": {}
    }

    user_home = synthetic_root if synthetic_root else Path.home()
    now = time.time()

    # 1. Primary User Directories Overview (Downloads, Desktop, Documents, Trash)
    user_dirs = {
        "Downloads": user_home / "Downloads",
        "Desktop": user_home / "Desktop",
        "Documents": user_home / "Documents",
        "Trash": user_home / ".Trash"
    }

    for name, p in user_dirs.items():
        if p.exists():
            app_b, alloc_b, cnt = get_path_detailed_size(p)
            results["user_directories"][name] = {
                "path": str(p),
                "apparent_bytes": app_b,
                "apparent_human": format_bytes(app_b),
                "allocated_bytes": alloc_b,
                "allocated_human": format_bytes(alloc_b),
                "file_count": cnt
            }

    # 2. Application Caches & Browser Caches
    caches_dir = user_home / "Library" / "Caches"
    if caches_dir.exists() and caches_dir.is_dir():
        try:
            for entry in os.scandir(str(caches_dir)):
                try:
                    p = Path(entry.path)
                    if entry.is_dir(follow_symlinks=False):
                        app_b, alloc_b, cnt = get_path_detailed_size(p)
                        min_sz = 1024 if synthetic_root else (10 * 1024 * 1024)
                        if app_b > min_sz:
                            item_info = {
                                "path": str(p),
                                "name": p.name,
                                "apparent_bytes": app_b,
                                "apparent_human": format_bytes(app_b),
                                "allocated_bytes": alloc_b,
                                "allocated_human": format_bytes(alloc_b),
                                "file_count": cnt,
                                "type": "application_cache",
                                "safety_classification": "DISPOSABLE_CACHE"
                            }
                            # Check if browser cache
                            name_lower = p.name.lower()
                            if any(b in name_lower for b in ["google", "chrome", "safari", "firefox", "brave", "edge"]):
                                item_info["type"] = "browser_cache"
                                results["browser_caches"].append(item_info)
                            else:
                                results["caches"].append(item_info)
                except (PermissionError, OSError) as e:
                    results["inaccessible_locations"].append({
                        "path": entry.path,
                        "reason": f"Permission denied accessing cache directory: {e}"
                    })
        except (PermissionError, OSError) as e:
            results["inaccessible_locations"].append({
                "path": str(caches_dir),
                "reason": f"Cannot scan Caches root: {e}"
            })

    # 3. Application Logs & Diagnostic Crash Reports
    logs_dir = user_home / "Library" / "Logs"
    if logs_dir.exists() and logs_dir.is_dir():
        try:
            for entry in os.scandir(str(logs_dir)):
                try:
                    p = Path(entry.path)
                    app_b, alloc_b, cnt = get_path_detailed_size(p)
                    stat = p.stat()
                    age_days = (now - stat.st_mtime) / 86400.0
                    min_log_sz = 1024 if synthetic_root else (1024 * 1024)

                    if p.name == "DiagnosticReports":
                        # Crash reports folder
                        results["crash_reports"].append({
                            "path": str(p),
                            "name": "macOS Crash & Diagnostic Reports",
                            "apparent_bytes": app_b,
                            "apparent_human": format_bytes(app_b),
                            "allocated_bytes": alloc_b,
                            "allocated_human": format_bytes(alloc_b),
                            "file_count": cnt,
                            "safety_classification": "DIAGNOSTIC_REPORTS"
                        })
                    elif app_b > min_log_sz or age_days > OLD_LOG_AGE_DAYS:
                        results["logs"].append({
                            "path": str(p),
                            "name": p.name,
                            "apparent_bytes": app_b,
                            "apparent_human": format_bytes(app_b),
                            "allocated_bytes": alloc_b,
                            "allocated_human": format_bytes(alloc_b),
                            "file_count": cnt,
                            "age_days": round(age_days, 1),
                            "safety_classification": "APPLICATION_LOGS"
                        })
                except (PermissionError, OSError):
                    pass
        except (PermissionError, OSError) as e:
            results["inaccessible_locations"].append({
                "path": str(logs_dir),
                "reason": str(e)
            })

    # 4. Old Installers (.dmg, .pkg, .iso, installer .zip)
    candidate_installer_dirs = [user_home / "Downloads", user_home / "Desktop"]
    if search_roots:
        candidate_installer_dirs = search_roots

    for d in candidate_installer_dirs:
        if d.exists() and d.is_dir():
            try:
                for entry in os.scandir(str(d)):
                    try:
                        p = Path(entry.path)
                        if entry.is_file(follow_symlinks=False):
                            ext = p.suffix.lower()
                            is_installer = ext in {".dmg", ".pkg", ".iso"}
                            # Check installer zip
                            if ext == ".zip":
                                fn_lower = p.stem.lower()
                                if any(kw in fn_lower for kw in ["install", "setup", "update", "patch"]):
                                    is_installer = True

                            if is_installer:
                                st = p.stat()
                                age_days = (now - st.st_mtime) / 86400.0
                                alloc_b = getattr(st, "st_blocks", 0) * 512
                                results["installers"].append({
                                    "path": str(p),
                                    "name": p.name,
                                    "apparent_bytes": st.st_size,
                                    "apparent_human": format_bytes(st.st_size),
                                    "allocated_bytes": max(alloc_b, 0),
                                    "allocated_human": format_bytes(alloc_b),
                                    "age_days": round(age_days, 1),
                                    "is_old": age_days > OLD_INSTALLER_AGE_DAYS,
                                    "safety_classification": "OPTIONAL_INSTALLER_REVIEW"
                                })
                    except (PermissionError, OSError):
                        pass
            except (PermissionError, OSError) as e:
                results["inaccessible_locations"].append({
                    "path": str(d),
                    "reason": str(e)
                })

    # 5. Development & Build Artifacts
    if not synthetic_root:
        dev_locations = [
            ("Xcode DerivedData", user_home / "Library/Developer/Xcode/DerivedData", "xcode_derived_data"),
            ("Xcode Archives", user_home / "Library/Developer/Xcode/Archives", "xcode_archives"),
            ("CocoaPods Release Pods", user_home / "Library/Caches/CocoaPods", "cocoapods_cache"),
            ("Swift Package Manager", user_home / "Library/Caches/org.swift.swiftpm", "swiftpm_cache"),
            ("Homebrew Package Downloads", user_home / "Library/Caches/Homebrew", "homebrew_cache"),
            ("Python Pip Cache", user_home / ".cache/pip", "pip_cache"),
            ("NPM / Yarn Content Cache", user_home / ".npm/_cacache", "npm_cacache"),
            ("Gradle Build Caches", user_home / ".gradle/caches", "gradle_cache"),
            ("Cargo Registry Caches", user_home / ".cargo/registry/cache", "cargo_cache")
        ]

        for name, dev_p, dev_type in dev_locations:
            if dev_p.exists():
                app_b, alloc_b, cnt = get_path_detailed_size(dev_p)
                if app_b > 1024 * 1024:
                    results["developer_artifacts"].append({
                        "path": str(dev_p),
                        "name": name,
                        "type": dev_type,
                        "apparent_bytes": app_b,
                        "apparent_human": format_bytes(app_b),
                        "allocated_bytes": alloc_b,
                        "allocated_human": format_bytes(alloc_b),
                        "file_count": cnt,
                        "safety_classification": "DEVELOPER_BUILD_CACHE"
                    })

    # 6. Local AI Models & Repositories (Ollama, HuggingFace, LM Studio, MLX)
    if not synthetic_root:
        ai_dirs = [
            ("Ollama Model Blobs", user_home / ".ollama/models", "Ollama"),
            ("HuggingFace Model Hub", user_home / ".cache/huggingface/hub", "HuggingFace"),
            ("LM Studio Cached Models", user_home / ".cache/lm-studio/models", "LM Studio"),
            ("LM Studio Local Models", user_home / ".lmstudio/models", "LM Studio"),
            ("Apple MLX Model Cache", user_home / ".cache/mlx", "Apple MLX")
        ]

        for name, ai_p, engine in ai_dirs:
            if ai_p.exists():
                app_b, alloc_b, cnt = get_path_detailed_size(ai_p)
                if app_b > 0:
                    results["local_ai_models"].append({
                        "path": str(ai_p),
                        "name": name,
                        "engine": engine,
                        "apparent_bytes": app_b,
                        "apparent_human": format_bytes(app_b),
                        "allocated_bytes": alloc_b,
                        "allocated_human": format_bytes(alloc_b),
                        "file_count": cnt,
                        "safety_classification": "LOCAL_AI_MODEL_PROTECTED"
                    })

    # 7. Docker Storage
    if not synthetic_root:
        rc, stdout, _ = run_cmd(["docker", "system", "df", "--format", "{{json .}}"], timeout=5)
        if rc == 0 and stdout:
            results["docker_storage"]["status"] = "Active"
            results["docker_storage"]["details"] = stdout
        else:
            docker_data = user_home / "Library/Containers/com.docker.docker/Data"
            if docker_data.exists():
                app_b, alloc_b, cnt = get_path_detailed_size(docker_data)
                results["docker_storage"]["status"] = "Docker VM Data Directory"
                results["docker_storage"]["apparent_bytes"] = app_b
                results["docker_storage"]["apparent_human"] = format_bytes(app_b)
                results["docker_storage"]["allocated_bytes"] = alloc_b
                results["docker_storage"]["allocated_human"] = format_bytes(alloc_b)
            else:
                results["docker_storage"]["status"] = "Not active"

    # 8. Duplicate Candidates Detection (Size Bucketing -> SHA256 -> Original vs Copy)
    size_map: Dict[int, List[Path]] = {}
    scan_dirs = search_roots if search_roots else [user_home / "Downloads", user_home / "Desktop"]
    min_dup_sz = 1024 if synthetic_root else DUPLICATE_MIN_SIZE_BYTES

    for d in scan_dirs:
        if d.exists() and d.is_dir():
            try:
                for entry in os.scandir(str(d)):
                    try:
                        p = Path(entry.path)
                        if entry.is_file(follow_symlinks=False):
                            sz = entry.stat().st_size
                            if sz >= min_dup_sz:
                                size_map.setdefault(sz, []).append(p)
                    except (PermissionError, OSError):
                        pass
            except (PermissionError, OSError):
                pass

    for sz, file_list in size_map.items():
        if len(file_list) > 1:
            hash_map: Dict[str, List[Path]] = {}
            for f in file_list:
                sha = calculate_sha256(f)
                if sha:
                    hash_map.setdefault(sha, []).append(f)
            for sha, matched in hash_map.items():
                if len(matched) > 1:
                    # Sort by modification time (earliest = Original copy)
                    sorted_by_mtime = sorted(matched, key=lambda p: p.stat().st_mtime)
                    original_file = sorted_by_mtime[0]
                    duplicate_copies = sorted_by_mtime[1:]

                    results["duplicates"].append({
                        "size_bytes": sz,
                        "size_human": format_bytes(sz),
                        "sha256": sha,
                        "total_copies": len(matched),
                        "original_path": str(original_file),
                        "duplicate_paths": [str(x) for x in duplicate_copies],
                        "all_paths": [str(x) for x in sorted_by_mtime],
                        "potential_savings_bytes": len(duplicate_copies) * sz,
                        "potential_savings_human": format_bytes(len(duplicate_copies) * sz),
                        "safety_classification": "OPTIONAL_DUPLICATE_REVIEW"
                    })

    # 9. Top Large Files & Ranked Directories
    found_files: List[Dict[str, Any]] = []
    for d in scan_dirs:
        if d.exists() and d.is_dir():
            try:
                for entry in os.scandir(str(d)):
                    try:
                        p = Path(entry.path)
                        if entry.is_file(follow_symlinks=False):
                            st = entry.stat()
                            sz = st.st_size
                            alloc = getattr(st, "st_blocks", 0) * 512
                            if sz >= (1024 if synthetic_root else LARGE_FILE_THRESHOLD_BYTES):
                                found_files.append({
                                    "path": str(p),
                                    "name": p.name,
                                    "apparent_bytes": sz,
                                    "apparent_human": format_bytes(sz),
                                    "allocated_bytes": max(alloc, 0),
                                    "allocated_human": format_bytes(alloc),
                                    "extension": p.suffix.lower()
                                })
                    except (PermissionError, OSError):
                        pass
            except (PermissionError, OSError):
                pass

    found_files.sort(key=lambda x: x["apparent_bytes"], reverse=True)
    results["large_files"] = found_files[:25]

    return results
