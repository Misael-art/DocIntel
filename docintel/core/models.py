"""Lightweight dataclasses used by the production baseline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from docintel.core.enums import ExecutionMode, ValidationStatus


@dataclass(frozen=True, slots=True)
class GuardrailDecision:
    """Result of a backend safety evaluation."""

    allowed: bool
    status: ValidationStatus
    reason: str
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Structured audit payload stored in SQLite and emitted to logs."""

    etapa: str
    acao: str
    alvo: str | None = None
    resultado: str | None = None
    detalhes: str | None = None
    severity: str = "INFO"
    correlation_id: str | None = None
    details_json: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """Materialized request evaluated before any mutating execution."""

    mode: ExecutionMode
    manual_approval_present: bool
    manifest_path: str | None
    validation_completed: bool
