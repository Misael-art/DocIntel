"""Runtime helpers for the DocIntel desktop launcher."""

from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
import json
from dataclasses import dataclass
from pathlib import Path

from config.settings import REPORTS_DIR
from docintel.db.connection import init_database, resolve_db_path
from docintel.db.migrations import MIGRATIONS


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    repo_root: Path
    python_executable: str
    db_path: Path
    reports_dir: Path
    dashboard_path: Path
    readme_path: Path
    git_branch: str
    git_commit: str
    git_remote: str
    stage3_summary: str
    latest_plan_key: str
    latest_plan_status: str
    latest_plan_summary: str
    latest_validation_report: Path | None


def repo_root() -> Path:
    """Return the repository root from the package location."""
    return Path(__file__).resolve().parents[2]


def _git_output(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root(),
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""
    return (result.stdout or "").strip()


def database_is_current(db_path: Path) -> bool:
    """Return whether the configured database already contains all known migrations."""
    if not db_path.exists():
        return False

    try:
        conn = sqlite3.connect(db_path, timeout=5)
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            ).fetchone()
            if row is None:
                return False
            applied = {
                migration[0]
                for migration in conn.execute("SELECT version FROM schema_migrations")
            }
        finally:
            conn.close()
    except sqlite3.Error:
        return False

    expected = {migration.version for migration in MIGRATIONS}
    return expected.issubset(applied)


def ensure_runtime_ready() -> Path:
    """Initialize or migrate the SQLite database when needed."""
    db_path = resolve_db_path()
    if not database_is_current(db_path):
        init_database(db_path)
    return db_path


def build_script_command(script_name: str, *args: str) -> list[str]:
    """Build a command list for one of the root operational scripts."""
    return [sys.executable, str(repo_root() / script_name), *args]


def parse_stage3_summary(status_path: Path | None = None) -> str:
    """Read a short summary from status_execucao.md when available."""
    path = status_path or Path(REPORTS_DIR) / "status_execucao.md"
    if not path.exists():
        return "Status da Etapa 3 ainda nao gerado."

    raw = path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"\*\*Arquivos Processados\*\* \| ([0-9,]+) / ([0-9,]+)", raw)
    if match:
        done = int(match.group(1).replace(",", ""))
        total = int(match.group(2).replace(",", ""))
        pending = max(total - done, 0)
        return f"Etapa 3: {done:,}/{total:,} processados, {pending:,} pendentes."
    return "Status da Etapa 3 presente, mas sem resumo interpretavel."


def latest_plan_context(db_path: Path) -> tuple[str, str, str, Path | None]:
    """Read a short summary for the latest materialized execution plan."""
    if not db_path.exists():
        return ("nenhum", "SEM_PLANO", "Nenhum plano materializado ainda.", None)

    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """
                SELECT plan_key, status, summary
                FROM execution_plans
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return ("indisponivel", "ERRO", "Nao foi possivel ler o ultimo plano materializado.", None)

    if row is None:
        return ("nenhum", "SEM_PLANO", "Nenhum plano materializado ainda.", None)

    report_path: Path | None = None
    ready_steps = blocked_steps = skipped_steps = None
    raw_summary = row["summary"] or ""
    if raw_summary:
        try:
            payload = json.loads(raw_summary)
        except json.JSONDecodeError:
            payload = {}
        report_value = payload.get("report_path")
        if report_value:
            report_path = Path(report_value)
        ready_steps = payload.get("ready_steps")
        blocked_steps = payload.get("blocked_steps")
        skipped_steps = payload.get("skipped_steps")

    status = row["status"]
    key = row["plan_key"]
    if ready_steps is not None and blocked_steps is not None and skipped_steps is not None:
        summary = (
            f"Ultimo plano {key}: {status} "
            f"(prontas={ready_steps}, bloqueadas={blocked_steps}, puladas={skipped_steps})."
        )
    else:
        summary = f"Ultimo plano {key}: {status}."
    return (key, status, summary, report_path)


def collect_runtime_context() -> RuntimeContext:
    """Collect the current launcher context for GUI rendering."""
    root = repo_root()
    db_path = ensure_runtime_ready()
    latest_plan_key, latest_plan_status, latest_plan_summary, latest_validation_report = latest_plan_context(db_path)
    return RuntimeContext(
        repo_root=root,
        python_executable=sys.executable,
        db_path=db_path,
        reports_dir=Path(REPORTS_DIR),
        dashboard_path=root / "output" / "dashboard.html",
        readme_path=root / "README.md",
        git_branch=_git_output("branch", "--show-current") or "desconhecido",
        git_commit=_git_output("rev-parse", "--short", "HEAD") or "desconhecido",
        git_remote=_git_output("config", "--get", "remote.origin.url") or "desconhecido",
        stage3_summary=parse_stage3_summary(),
        latest_plan_key=latest_plan_key,
        latest_plan_status=latest_plan_status,
        latest_plan_summary=latest_plan_summary,
        latest_validation_report=latest_validation_report,
    )


def open_in_shell(target: Path) -> None:
    """Open a file or directory in the Windows shell."""
    os.startfile(str(target))
