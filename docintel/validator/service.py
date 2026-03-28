"""Validation and execution-plan materialization for DocIntel manifests."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import os

from config.organization_policy import ACTION_COPY, ACTION_DRAIN_C, ACTION_KEEP, ACTION_REVIEW, DESTINATIONS
from docintel.core.enums import (
    ActionType,
    PlanStatus,
    RiskLevel,
    StepStatus,
    ValidationSeverity,
    ValidationStatus,
)
from docintel.core.models import MaterializedExecutionStep, PlanMaterializationSummary, ValidationRecord
from docintel.db.connection import get_connection
from docintel.filesystem import choose_destination_candidate
from storage_audit import get_volume_info


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "sim"}


def _manifest_status(ready: int, blocked: int, review: int, executable: int, policy_blocked: bool) -> str:
    if policy_blocked:
        return "BLOCKED"
    if review and not executable:
        return "REVIEW_REQUIRED"
    if blocked > 0:
        return "BLOCKED"
    if ready > 0:
        return "VALIDATED"
    return "NO_EXECUTION_REQUIRED"


def _plan_status(manifest_statuses: list[str]) -> PlanStatus:
    if not manifest_statuses:
        return PlanStatus.BLOCKED
    if any(status == "BLOCKED" for status in manifest_statuses):
        return PlanStatus.VALIDATED_WITH_BLOCKERS
    if any(status == "REVIEW_REQUIRED" for status in manifest_statuses):
        return PlanStatus.VALIDATED_WITH_BLOCKERS
    if any(status == "VALIDATED" for status in manifest_statuses):
        return PlanStatus.VALIDATED
    return PlanStatus.BLOCKED


def _row_count(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def _checksum(path: Path) -> str:
    import hashlib

    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _reserve_for_destination_root(destination_path: str) -> int:
    for config in DESTINATIONS.values():
        root = config.get("root")
        if root and destination_path.startswith(root):
            return int(config.get("min_free_bytes") or 0)
    return 0


def _drive_or_root(destination_path: str) -> str:
    drive, _ = os.path.splitdrive(destination_path)
    return f"{drive}\\" if drive else destination_path


def _normalize_risk_level(value: str | RiskLevel | None) -> RiskLevel:
    if isinstance(value, RiskLevel):
        return value
    normalized = (value or "").strip().upper()
    aliases = {
        "BAIXO": RiskLevel.LOW,
        "LOW": RiskLevel.LOW,
        "MEDIO": RiskLevel.MEDIUM,
        "MÉDIO": RiskLevel.MEDIUM,
        "MEDIUM": RiskLevel.MEDIUM,
        "ALTO": RiskLevel.HIGH,
        "HIGH": RiskLevel.HIGH,
        "BLOQUEADO": RiskLevel.BLOCKED,
        "BLOCKED": RiskLevel.BLOCKED,
    }
    return aliases.get(normalized, RiskLevel.MEDIUM)


def _build_plan_records(
    plan_key: str,
    manifest_label: str,
    row: dict[str, str],
    step_order: int,
) -> tuple[MaterializedExecutionStep | None, list[ValidationRecord], RiskLevel]:
    action = row["recommended_action"]
    source_path = row["source_path"]
    destination_path = row.get("destination_path") or ""
    source_hash = row.get("hash_sha256") or ""
    blockers = [item for item in (row.get("execution_blockers") or "").split(";") if item]
    needs_review = _truthy(row.get("requires_human_review"))
    risk_level = _normalize_risk_level(row.get("risk_level"))
    validations: list[ValidationRecord] = []
    manifest_key = f"{plan_key}:{manifest_label}"

    if action == ACTION_KEEP:
        return None, validations, risk_level

    if action == ACTION_REVIEW:
        step = MaterializedExecutionStep(
            step_order=step_order,
            action_type=ActionType.REVIEW,
            source_path=source_path,
            destination_path=None,
            manifest_key=manifest_key,
            status=StepStatus.BLOCKED,
            message="Item requer revisao humana antes de qualquer execucao.",
            rollback_supported=False,
            journal_payload={"manifest_label": manifest_label, "source_path": source_path},
        )
        validations.append(
            ValidationRecord(
                scope_type="STEP",
                scope_ref=source_path,
                rule_code="HUMAN_REVIEW_REQUIRED",
                severity=ValidationSeverity.BLOCKER,
                status=ValidationStatus.BLOCKED,
                message="A acao recomendada e revisao humana; nenhuma execucao automatica e permitida.",
                evidence_json={"manifest_label": manifest_label},
                step_order=step_order,
            )
        )
        return step, validations, RiskLevel.BLOCKED

    action_type = ActionType.COPY
    resolved_destination = destination_path
    step_status = StepStatus.READY
    message = "Etapa pronta para execucao copy-first."

    if blockers:
        step_status = StepStatus.BLOCKED
        message = "Existem bloqueios de politica materializados no planejamento."
        validations.append(
            ValidationRecord(
                scope_type="STEP",
                scope_ref=source_path,
                rule_code="PLANNER_BLOCKERS_PRESENT",
                severity=ValidationSeverity.BLOCKER,
                status=ValidationStatus.BLOCKED,
                message="O planner marcou bloqueios explicitos para esta etapa.",
                evidence_json={"blockers": blockers},
                step_order=step_order,
            )
        )

    if needs_review:
        step_status = StepStatus.BLOCKED
        message = "Execucao bloqueada ate revisao humana."
        validations.append(
            ValidationRecord(
                scope_type="STEP",
                scope_ref=source_path,
                rule_code="REVIEW_REQUIRED",
                severity=ValidationSeverity.BLOCKER,
                status=ValidationStatus.BLOCKED,
                message="A decisao exige revisao humana antes de qualquer copia.",
                evidence_json={"risk_level": row.get("risk_level")},
                step_order=step_order,
            )
        )

    if not Path(source_path).exists():
        step_status = StepStatus.BLOCKED
        message = "Arquivo de origem nao encontrado no filesystem."
        validations.append(
            ValidationRecord(
                scope_type="STEP",
                scope_ref=source_path,
                rule_code="SOURCE_EXISTS",
                severity=ValidationSeverity.BLOCKER,
                status=ValidationStatus.BLOCKED,
                message="A origem nao existe mais no momento da validacao.",
                evidence_json={},
                step_order=step_order,
            )
        )

    if not destination_path:
        step_status = StepStatus.BLOCKED
        message = "Destino fisico ausente para etapa executavel."
        validations.append(
            ValidationRecord(
                scope_type="STEP",
                scope_ref=source_path,
                rule_code="DESTINATION_PRESENT",
                severity=ValidationSeverity.BLOCKER,
                status=ValidationStatus.BLOCKED,
                message="A etapa copy-first ficou sem destino fisico materializado.",
                evidence_json={"manifest_label": manifest_label},
                step_order=step_order,
            )
        )
    elif step_status is StepStatus.READY:
        resolved_destination, resolution = choose_destination_candidate(
            destination_path,
            source_hash,
            source_path,
        )
        if resolution == "ALREADY_PRESENT_SAME_HASH":
            step_status = StepStatus.SKIPPED
            message = "Destino ja contem o mesmo conteudo; nenhuma copia sera necessaria."
            validations.append(
                ValidationRecord(
                    scope_type="STEP",
                    scope_ref=source_path,
                    rule_code="DESTINATION_ALREADY_CURRENT",
                    severity=ValidationSeverity.INFO,
                    status=ValidationStatus.SKIPPED,
                    message="O destino ja possui o mesmo hash da origem.",
                    evidence_json={"destination_path": resolved_destination},
                    step_order=step_order,
                )
            )
        elif resolution == "COLLISION_RENAMED":
            message = "Colisao detectada; a etapa foi materializada com nome alternativo deterministico."
            validations.append(
                ValidationRecord(
                    scope_type="STEP",
                    scope_ref=source_path,
                    rule_code="DESTINATION_COLLISION_RENAMED",
                    severity=ValidationSeverity.WARNING,
                    status=ValidationStatus.PASSED,
                    message="O destino original ja existia e recebeu variante segura sem sobrescrita.",
                    evidence_json={"resolved_destination": resolved_destination},
                    step_order=step_order,
                )
            )

    step = MaterializedExecutionStep(
        step_order=step_order,
        action_type=action_type,
        source_path=source_path,
        destination_path=resolved_destination or None,
        manifest_key=manifest_key,
        status=step_status,
        message=message,
        rollback_supported=False,
        journal_payload={
            "manifest_label": manifest_label,
            "source_path": source_path,
            "original_destination_path": destination_path,
            "resolved_destination_path": resolved_destination,
            "risk_level": row.get("risk_level"),
            "duplicate_hint": row.get("duplicate_hint"),
        },
    )
    if step_status is StepStatus.READY:
        validations.append(
            ValidationRecord(
                scope_type="STEP",
                scope_ref=source_path,
                rule_code="STEP_READY_FOR_EXECUTION",
                severity=ValidationSeverity.INFO,
                status=ValidationStatus.PASSED,
                message="A etapa passou nas validacoes executaveis desta rodada.",
                evidence_json={"destination_path": resolved_destination},
                step_order=step_order,
            )
        )

    return step, validations, risk_level


def materialize_execution_plan(
    *,
    db_path: str,
    manifest_paths: dict[str, str],
    summary_path: str,
    top_risks_path: str,
    stats: dict[str, Any],
    policy_version: str,
) -> PlanMaterializationSummary:
    """Create execution_plans, execution_steps, manifests, validation_results and report artifacts."""
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    plan_key = f"org-{timestamp}"
    report_path = str(Path(summary_path).with_name(f"organization_validation_{plan_key}.md"))

    conn = get_connection(db_path)
    try:
        total_decisions = 0
        materialized_steps = 0
        ready_steps = 0
        blocked_steps = 0
        skipped_steps = 0
        validation_count = 0
        manifest_statuses: list[str] = []

        conn.execute(
            """
            INSERT INTO execution_plans (
                plan_key, plan_kind, status, mode, source_snapshot_at, summary
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                plan_key,
                "ORGANIZATION_CURATION",
                PlanStatus.DRAFT,
                "DRY_RUN",
                _utc_now(),
                json.dumps({"policy_version": policy_version, "stats": stats}, ensure_ascii=True),
            ),
        )
        plan_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()

        step_order = 1
        report_lines = [
            "# Validacao de Plano de Execucao",
            "",
            f"> Plan key: `{plan_key}`",
            f"> Politica: `{policy_version}`",
            f"> Gerado em UTC: {_utc_now()}",
            "",
            "## Manifests",
            "",
            "| Manifesto | Linhas | Status |",
            "|-----------|--------|--------|",
        ]

        for manifest_label, manifest_path in manifest_paths.items():
            path = Path(manifest_path)
            row_count = _row_count(path)
            checksum = _checksum(path)
            total_decisions += row_count

            conn.execute(
                """
                INSERT INTO manifests (manifest_key, manifest_kind, plan_id, file_path, checksum_sha256, row_count, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{plan_key}:{manifest_label}",
                    manifest_label,
                    plan_id,
                    str(path),
                    checksum,
                    row_count,
                    "GENERATED",
                ),
            )

            manifest_ready = 0
            manifest_blocked = 0
            manifest_review = 0
            manifest_executable = 0
            copy_bytes_by_root: Counter[str] = Counter()
            policy_blocked = False

            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    step, validations, _risk_level = _build_plan_records(plan_key, manifest_label, row, step_order)
                    if step is None:
                        continue

                    materialized_steps += 1
                    if step.status is StepStatus.READY:
                        ready_steps += 1
                        manifest_ready += 1
                        manifest_executable += 1
                    elif step.status is StepStatus.BLOCKED:
                        blocked_steps += 1
                        manifest_blocked += 1
                        if step.action_type is ActionType.REVIEW:
                            manifest_review += 1
                        else:
                            manifest_executable += 1
                    elif step.status is StepStatus.SKIPPED:
                        skipped_steps += 1

                    if step.action_type is ActionType.COPY and step.destination_path:
                        copy_bytes_by_root[_drive_or_root(step.destination_path)] += int(row.get("size_bytes") or 0)

                    conn.execute(
                        """
                        INSERT INTO execution_steps (
                            plan_id, step_order, action_type, source_path, destination_path,
                            status, rollback_supported, journal_payload
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            plan_id,
                            step.step_order,
                            step.action_type,
                            step.source_path,
                            step.destination_path,
                            step.status,
                            int(step.rollback_supported),
                            json.dumps(step.journal_payload, ensure_ascii=True),
                        ),
                    )
                    step_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                    for record in validations:
                        conn.execute(
                            """
                            INSERT INTO validation_results (
                                plan_id, step_id, scope_type, scope_ref, rule_code,
                                severity, status, message, evidence_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                plan_id,
                                step_id,
                                record.scope_type,
                                record.scope_ref,
                                record.rule_code,
                                record.severity,
                                record.status,
                                record.message,
                                json.dumps(record.evidence_json, ensure_ascii=True),
                            ),
                        )
                        validation_count += 1

                    step_order += 1

            for destination_root, planned_bytes in copy_bytes_by_root.items():
                info = get_volume_info(destination_root)
                reserve_bytes = _reserve_for_destination_root(destination_root)
                available_bytes = max(int(info["free"]) - reserve_bytes, 0) if info["exists"] else 0
                if not info["exists"]:
                    policy_blocked = True
                    status = ValidationStatus.BLOCKED
                    severity = ValidationSeverity.BLOCKER
                    message = f"O destino {destination_root} nao esta acessivel no momento da validacao."
                elif planned_bytes > available_bytes:
                    policy_blocked = True
                    status = ValidationStatus.BLOCKED
                    severity = ValidationSeverity.BLOCKER
                    message = (
                        f"O destino {destination_root} nao possui folga suficiente para o manifesto "
                        f"{manifest_label}."
                    )
                else:
                    status = ValidationStatus.PASSED
                    severity = ValidationSeverity.INFO
                    message = f"O destino {destination_root} passou na validacao de capacidade."

                conn.execute(
                    """
                    INSERT INTO validation_results (
                        plan_id, scope_type, scope_ref, rule_code, severity, status, message, evidence_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        plan_id,
                        "MANIFEST",
                        manifest_label,
                        "DESTINATION_CAPACITY_CHECK",
                        severity,
                        status,
                        message,
                        json.dumps(
                            {
                                "destination_root": destination_root,
                                "planned_bytes": planned_bytes,
                                "available_bytes_after_reserve": available_bytes,
                                "reserve_bytes": reserve_bytes,
                            },
                            ensure_ascii=True,
                        ),
                    ),
                )
                validation_count += 1

            manifest_status = _manifest_status(
                manifest_ready,
                manifest_blocked,
                manifest_review,
                manifest_executable,
                policy_blocked,
            )
            manifest_statuses.append(manifest_status)
            conn.execute(
                "UPDATE manifests SET status = ?, updated_at = datetime('now') WHERE manifest_key = ?",
                (manifest_status, f"{plan_key}:{manifest_label}"),
            )
            conn.execute(
                """
                INSERT INTO validation_results (
                    plan_id, scope_type, scope_ref, rule_code, severity, status, message, evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    "MANIFEST",
                    manifest_label,
                    "MANIFEST_VALIDATION_SUMMARY",
                    ValidationSeverity.INFO if manifest_status == "VALIDATED" else ValidationSeverity.WARNING,
                    ValidationStatus.PASSED if manifest_status == "VALIDATED" else ValidationStatus.BLOCKED if manifest_status in {"BLOCKED", "REVIEW_REQUIRED"} else ValidationStatus.SKIPPED,
                    f"Manifesto {manifest_label} finalizado com status {manifest_status}.",
                    json.dumps(
                        {
                            "row_count": row_count,
                            "ready_steps": manifest_ready,
                            "blocked_steps": manifest_blocked,
                            "review_steps": manifest_review,
                            "checksum": checksum,
                        },
                        ensure_ascii=True,
                    ),
                ),
            )
            validation_count += 1
            conn.execute(
                """
                INSERT INTO risk_assessments (
                    plan_id, scope_type, scope_ref, risk_level, risk_code, confidence, summary, blockers, mitigation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    "MANIFEST",
                    manifest_label,
                    RiskLevel.BLOCKED if manifest_blocked else RiskLevel.HIGH if manifest_review else RiskLevel.LOW,
                    "MANIFEST_RISK_SUMMARY",
                    1.0,
                    f"Manifesto {manifest_label}: {manifest_ready} pronto(s), {manifest_blocked} bloqueado(s), {manifest_review} em revisao.",
                    "REVIEW_REQUIRED" if manifest_review else "VALIDATION_BLOCKERS" if manifest_blocked else "",
                    "Resolver bloqueios e revisar itens humanos antes de aplicar.",
                ),
            )
            report_lines.append(f"| {manifest_label} | {row_count:,} | {manifest_status} |")
            conn.commit()

        final_plan_status = _plan_status(manifest_statuses)
        conn.execute(
            """
            INSERT INTO validation_results (
                plan_id, scope_type, scope_ref, rule_code, severity, status, message, evidence_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                "PLAN",
                plan_key,
                "PLAN_MATERIALIZATION_COMPLETE",
                ValidationSeverity.INFO,
                ValidationStatus.PASSED if final_plan_status is PlanStatus.VALIDATED else ValidationStatus.BLOCKED,
                f"Plano materializado com status {final_plan_status}.",
                json.dumps(
                    {
                        "materialized_steps": materialized_steps,
                        "ready_steps": ready_steps,
                        "blocked_steps": blocked_steps,
                        "skipped_steps": skipped_steps,
                    },
                    ensure_ascii=True,
                ),
            ),
        )
        validation_count += 1
        conn.execute(
            """
            UPDATE execution_plans
            SET status = ?, validated_at = datetime('now'), updated_at = datetime('now'), summary = ?
            WHERE id = ?
            """,
            (
                final_plan_status,
                json.dumps(
                    {
                        "policy_version": policy_version,
                        "stats": stats,
                        "plan_status": final_plan_status,
                        "report_path": report_path,
                        "ready_steps": ready_steps,
                        "blocked_steps": blocked_steps,
                        "skipped_steps": skipped_steps,
                    },
                    ensure_ascii=True,
                ),
                plan_id,
            ),
        )
        conn.commit()

        report_lines.extend(
            [
                "",
                "## Resumo",
                "",
                f"- Status do plano: `{final_plan_status}`",
                f"- Decisoes avaliadas: {total_decisions:,}",
                f"- Etapas materializadas: {materialized_steps:,}",
                f"- Etapas prontas: {ready_steps:,}",
                f"- Etapas bloqueadas: {blocked_steps:,}",
                f"- Etapas puladas: {skipped_steps:,}",
                f"- Registros de validacao: {validation_count:,}",
                f"- Summary report: `{summary_path}`",
                f"- Top risks: `{top_risks_path}`",
            ]
        )
        Path(report_path).write_text("\n".join(report_lines), encoding="utf-8")

        return PlanMaterializationSummary(
            plan_key=plan_key,
            plan_status=final_plan_status,
            total_decisions=total_decisions,
            materialized_steps=materialized_steps,
            ready_steps=ready_steps,
            blocked_steps=blocked_steps,
            skipped_steps=skipped_steps,
            validation_records=validation_count,
            report_path=report_path,
        )
    finally:
        conn.close()


def resolve_manifest_validation_status(db_path: str, manifest_path: str) -> str | None:
    """Return the latest known validation status for a manifest path."""
    conn = get_connection(db_path, query_only=True)
    try:
        row = conn.execute(
            """
            SELECT status
            FROM manifests
            WHERE file_path = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (str(Path(manifest_path)),),
        ).fetchone()
        return row["status"] if row else None
    finally:
        conn.close()
