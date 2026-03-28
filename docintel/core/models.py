"""Lightweight dataclasses used by the production baseline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from docintel.core.enums import (
    ActionType,
    ExecutionMode,
    PlanStatus,
    StepStatus,
    ValidationSeverity,
    ValidationStatus,
)


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


@dataclass(frozen=True, slots=True)
class MaterializedExecutionStep:
    """Execution step derived from a validated manifest row."""

    step_order: int
    action_type: ActionType
    source_path: str | None
    destination_path: str | None
    manifest_key: str
    status: StepStatus
    message: str
    rollback_supported: bool
    journal_payload: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ValidationRecord:
    """Normalized validation entry persisted into validation_results."""

    scope_type: str
    scope_ref: str
    rule_code: str
    severity: ValidationSeverity
    status: ValidationStatus
    message: str
    evidence_json: Mapping[str, object] = field(default_factory=dict)
    step_order: int | None = None


@dataclass(frozen=True, slots=True)
class PlanMaterializationSummary:
    """Summary returned after plan materialization and validation."""

    plan_key: str
    plan_status: PlanStatus
    total_decisions: int
    materialized_steps: int
    ready_steps: int
    blocked_steps: int
    skipped_steps: int
    validation_records: int
    report_path: str
