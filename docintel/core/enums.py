"""Shared enums for safe planning and execution."""

from __future__ import annotations

from enum import StrEnum


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKED = "BLOCKED"


class ValidationStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class ExecutionMode(StrEnum):
    DRY_RUN = "DRY_RUN"
    APPLY = "APPLY"
    RESUME = "RESUME"
    RETRY = "RETRY"


class ActionType(StrEnum):
    COPY = "COPY"
    KEEP = "KEEP"
    REVIEW = "REVIEW"
    QUARANTINE = "QUARANTINE"
    LINK = "LINK"
    REWRITE_CONFIG = "REWRITE_CONFIG"


class LinkType(StrEnum):
    SYMLINK = "SYMLINK"
    JUNCTION = "JUNCTION"
    HARDLINK = "HARDLINK"
