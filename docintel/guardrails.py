"""Centralized safety checks shared by supervisors and future executors."""

from __future__ import annotations

from docintel.core.enums import ExecutionMode, ValidationStatus
from docintel.core.models import ExecutionRequest, GuardrailDecision


def evaluate_execution_request(request: ExecutionRequest) -> GuardrailDecision:
    """Block unsafe execution attempts before any filesystem mutation."""
    if request.mode is ExecutionMode.DRY_RUN:
        return GuardrailDecision(
            allowed=True,
            status=ValidationStatus.PASSED,
            reason="Dry-run is always allowed because it does not mutate the filesystem.",
        )

    blockers: list[str] = []
    if not request.manual_approval_present:
        blockers.append("MANUAL_APPROVAL_REQUIRED")
    if not request.validation_completed:
        blockers.append("VALIDATION_NOT_COMPLETED")
    if not request.manifest_path:
        blockers.append("EXECUTABLE_MANIFEST_REQUIRED")

    if blockers:
        return GuardrailDecision(
            allowed=False,
            status=ValidationStatus.BLOCKED,
            reason="Apply/resume/retry execution is blocked until all hard prerequisites are present.",
            blockers=tuple(blockers),
        )

    return GuardrailDecision(
        allowed=True,
        status=ValidationStatus.PASSED,
        reason="Execution prerequisites satisfied.",
    )
