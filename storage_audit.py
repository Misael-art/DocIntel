"""
DocIntel - Auditoria utilitaria de armazenamento e C:.
"""
from __future__ import annotations

import os
import shutil
from typing import Iterator

from config.organization_policy import C_USER_TARGETS


def iter_c_user_files() -> Iterator[dict]:
    """Yield file metadata from audited user folders on C:."""
    for bucket, paths in C_USER_TARGETS.items():
        for target in paths:
            if not os.path.exists(target):
                continue
            for root, _, files in os.walk(target):
                for name in files:
                    full_path = os.path.join(root, name)
                    try:
                        stat = os.stat(full_path)
                    except OSError:
                        continue
                    _, ext = os.path.splitext(name)
                    yield {
                        "file_id": None,
                        "source_path": full_path,
                        "source_drive": "C:\\",
                        "size_bytes": stat.st_size,
                        "extensao": ext.lower() if ext else "",
                        "nome_arquivo": name,
                        "pasta_raiz": bucket,
                        "fase_correspondente": "C_USER",
                        "status_indexacao": "C_AUDIT",
                        "data_modificacao": None,
                        "is_c_audit": True,
                    }


def iter_bucket_files(paths: list[str]) -> Iterator[dict]:
    for target in paths:
        if not os.path.exists(target):
            continue
        for root, _, files in os.walk(target):
            for name in files:
                full_path = os.path.join(root, name)
                try:
                    stat = os.stat(full_path)
                except OSError:
                    continue
                yield {"path": full_path, "size_bytes": stat.st_size}


def summarize_c_user_targets() -> dict:
    """Small summary for report rendering."""
    stats = {}
    for bucket, paths in C_USER_TARGETS.items():
        total_files = 0
        total_bytes = 0
        for entry in iter_bucket_files(paths):
            total_files += 1
            total_bytes += entry["size_bytes"]
        stats[bucket] = {"files": total_files, "bytes": total_bytes}
    return stats


def get_volume_info(path: str) -> dict:
    """Return total/free/used bytes if path exists."""
    if not path:
        return {"exists": False, "total": 0, "free": 0, "used": 0}
    probe = path
    if not os.path.exists(probe):
        drive, _ = os.path.splitdrive(path)
        probe = f"{drive}\\" if drive else path
    if not os.path.exists(probe):
        return {"exists": False, "total": 0, "free": 0, "used": 0}
    total, used, free = shutil.disk_usage(probe)
    return {"exists": True, "total": total, "free": free, "used": used}
