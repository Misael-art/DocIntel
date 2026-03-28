"""Shared filesystem helpers used by validation and execution."""

from __future__ import annotations

import hashlib
import os


def safe_collision_segment(value: str) -> str:
    """Return a conservative filesystem-safe segment."""
    cleaned = (value or "").strip().replace(":", "_")
    for char in '<>:"/\\|?*':
        cleaned = cleaned.replace(char, "_")
    cleaned = cleaned.rstrip(". ")
    return cleaned or "item"


def file_sha256(path: str) -> str:
    """Calculate a SHA-256 digest for a file."""
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def choose_destination_candidate(dest_path: str, source_hash: str, source_path: str) -> tuple[str, str]:
    """Resolve a deterministic destination without overwriting existing files."""
    if not os.path.exists(dest_path):
        return dest_path, "NEW_DESTINATION"
    if source_hash:
        try:
            if file_sha256(dest_path) == source_hash:
                return dest_path, "ALREADY_PRESENT_SAME_HASH"
        except OSError:
            pass
    base, ext = os.path.splitext(dest_path)
    suffix = safe_collision_segment(source_hash[:8] if source_hash else os.path.basename(source_path))
    candidate = f"{base}__dup_{suffix}{ext}"
    counter = 1
    while os.path.exists(candidate):
        candidate = f"{base}__dup_{suffix}_{counter}{ext}"
        counter += 1
    return candidate, "COLLISION_RENAMED"
