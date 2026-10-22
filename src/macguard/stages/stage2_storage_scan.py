"""
Stage 2: Accessible Storage and Artifacts Analysis.

Scans:
- Application caches & logs
- Old installers (.dmg, .pkg, .iso)
- Duplicate candidates
- Developer artifacts (Xcode DerivedData, node_modules, pycache, pip cache, Homebrew)
- Docker storage
- Local AI models (Ollama, HuggingFace, LM Studio)
- Large files (> 250 MB)
- Inaccessible/protected locations
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
from macguard.utils.disk import get_path_size, format_bytes
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
    Performs a thorough read-only storage scan across accessible locations.
    If synthetic_root is passed, restricts scanning strictly to that isolated subtree.
    """
    results: Dict[str, Any] = {
        "caches": [],
        "logs": [],
        "installers": [],
        "duplicates": [],
        "developer_artifacts": [],
        "docker_storage": {},
        "local_ai_models": [],
        "large_files": [],
        "inaccessible_locations": [],
        "summary": {}
    }

    user_home = synthetic_root if synthetic_root else Path.home()
    now = time.time()

    # 1. Caches Scan
    caches_dir = user_home / "Library" / "Caches"
    if caches_dir.exists() and caches_dir.is_dir():
        try:
            for entry in os.scandir(str(caches_dir)):
                try:
                    p = Path(entry.path)
                    if entry.is_dir(follow_symlinks=False):
                        size, count = get_path_size(p)
                        # In synthetic root, count any cache > 1KB; in real system, > 10MB
                        min_sz = 1024 if synthetic_root else (10 * 1024 * 1024)
                        if size > min_sz:
                            results["caches"].append({
                                "path": str(p),
                                "name": p.name,
                                "size_bytes": size,
                                "file_count": count,
                                "type": "application_cache"
                            })
                except (PermissionError, OSError):
                    results["inaccessible_locations"].append(entry.path)
        except (PermissionError, OSError):
            results["inaccessible_locations"].append(str(caches_dir))

    # Homebrew cache
    if not synthetic_root:
        brew_cache = user_home / "Library" / "Caches" / "Homebrew"
        if brew_cache.exists():
            size, count = get_path_size(brew_cache)
            if size > 1024 * 1024:
                results["developer_artifacts"].append({
                    "path": str(brew_cache),
                    "name": "Homebrew Cache",
                    "size_bytes": size,
                    "file_count": count,
                    "type": "homebrew_cache"
                })

    # 2. Logs Scan
    logs_dir = user_home / "Library" / "Logs"
    if logs_dir.exists() and logs_dir.is_dir():
        try:
            for entry in os.scandir(str(logs_dir)):
                try:
                    p = Path(entry.path)
                    size, count = get_path_size(p)
                    stat = p.stat()
                    age_days = (now - stat.st_mtime) / 86400.0
                    min_log_sz = 1024 if synthetic_root else (1024 * 1024)
                    if size > min_log_sz or age_days > OLD_LOG_AGE_DAYS:
                        results["logs"].append({
                            "path": str(p),
                            "name": p.name,
                            "size_bytes": size,
                            "file_count": count,
                            "age_days": round(age_days, 1),
                            "type": "user_log"
                        })
                except (PermissionError, OSError):
                    pass
        except (PermissionError, OSError):
            results["inaccessible_locations"].append(str(logs_dir))

    # 3. Old Installers (.dmg, .pkg, .iso) in Downloads / Desktop
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
                            if ext in {".dmg", ".pkg", ".iso"}:
                                stat = p.stat()
                                age_days = (now - stat.st_mtime) / 86400.0
                                size = stat.st_size
                                results["installers"].append({
                                    "path": str(p),
                                    "name": p.name,
                                    "size_bytes": size,
                                    "age_days": round(age_days, 1),
                                    "is_old": age_days > OLD_INSTALLER_AGE_DAYS
                                })
                    except (PermissionError, OSError):
                        pass
            except (PermissionError, OSError):
                results["inaccessible_locations"].append(str(d))

    if not synthetic_root:
        # 4. Developer Artifacts
        derived_data = user_home / "Library" / "Developer" / "Xcode" / "DerivedData"
        if derived_data.exists():
            size, count = get_path_size(derived_data)
            if size > 1024 * 1024:
                results["developer_artifacts"].append({
                    "path": str(derived_data),
                    "name": "Xcode DerivedData",
                    "size_bytes": size,
                    "file_count": count,
                    "type": "xcode_derived_data"
                })

        pip_cache = user_home / ".cache" / "pip"
        if pip_cache.exists():
            size, count = get_path_size(pip_cache)
            if size > 1024 * 1024:
                results["developer_artifacts"].append({
                    "path": str(pip_cache),
                    "name": "Pip Cache",
                    "size_bytes": size,
                    "file_count": count,
                    "type": "pip_cache"
                })

        # 5. Local AI Models
        ollama_models = user_home / ".ollama" / "models"
        if ollama_models.exists():
            size, count = get_path_size(ollama_models)
            if size > 0:
                results["local_ai_models"].append({
                    "path": str(ollama_models),
                    "name": "Ollama Models",
                    "engine": "Ollama",
                    "size_bytes": size,
                    "file_count": count
                })

        hf_cache = user_home / ".cache" / "huggingface" / "hub"
        if hf_cache.exists():
            size, count = get_path_size(hf_cache)
            if size > 0:
                results["local_ai_models"].append({
                    "path": str(hf_cache),
                    "name": "HuggingFace Model Hub",
                    "engine": "HuggingFace",
                    "size_bytes": size,
                    "file_count": count
                })

        lmstudio_models = user_home / ".cache" / "lm-studio" / "models"
        if lmstudio_models.exists():
            size, count = get_path_size(lmstudio_models)
            if size > 0:
                results["local_ai_models"].append({
                    "path": str(lmstudio_models),
                    "name": "LM Studio Models",
                    "engine": "LM Studio",
                    "size_bytes": size,
                    "file_count": count
                })

        # 6. Docker Storage
        rc, stdout, _ = run_cmd(["docker", "system", "df", "--format", "{{json .}}"], timeout=5)
        if rc == 0 and stdout:
            results["docker_storage"]["status"] = "Running"
            results["docker_storage"]["details"] = stdout
        else:
            docker_data = user_home / "Library" / "Containers" / "com.docker.docker" / "Data"
            if docker_data.exists():
                size, count = get_path_size(docker_data)
                results["docker_storage"]["status"] = "Host Data Directory"
                results["docker_storage"]["size_bytes"] = size
            else:
                results["docker_storage"]["status"] = "Not active or not installed"

    # 7. Duplicate Candidates Scan (size-bucketed)
    size_map: Dict[int, List[Path]] = {}
    scan_dirs = search_roots if search_roots else [user_home / "Downloads"]

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
                    results["duplicates"].append({
                        "size_bytes": sz,
                        "sha256": sha,
                        "count": len(matched),
                        "paths": [str(x) for x in matched],
                        "potential_savings_bytes": (len(matched) - 1) * sz
                    })

    # 8. Large Files (> 250 MB)
    for d in scan_dirs:
        if d.exists() and d.is_dir():
            try:
                for entry in os.scandir(str(d)):
                    try:
                        p = Path(entry.path)
                        if entry.is_file(follow_symlinks=False):
                            sz = entry.stat().st_size
                            if sz >= LARGE_FILE_THRESHOLD_BYTES:
                                results["large_files"].append({
                                    "path": str(p),
                                    "name": p.name,
                                    "size_bytes": sz,
                                    "size_human": format_bytes(sz)
                                })
                    except (PermissionError, OSError):
                        pass
            except (PermissionError, OSError):
                pass

    return results
