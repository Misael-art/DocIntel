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


class ValidationSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    BLOCKER = "BLOCKER"


class ExecutionMode(StrEnum):
    DRY_RUN = "DRY_RUN"
    APPLY = "APPLY"
    RESUME = "RESUME"
    RETRY = "RETRY"


class PlanStatus(StrEnum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    VALIDATED_WITH_BLOCKERS = "VALIDATED_WITH_BLOCKERS"
    BLOCKED = "BLOCKED"
    EXECUTED = "EXECUTED"


class StepStatus(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
    COMPLETED = "COMPLETED"


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
