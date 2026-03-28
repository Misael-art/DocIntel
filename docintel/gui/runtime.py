"""Runtime helpers for the DocIntel desktop launcher."""

from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
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


def collect_runtime_context() -> RuntimeContext:
    """Collect the current launcher context for GUI rendering."""
    root = repo_root()
    db_path = ensure_runtime_ready()
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
    )


def open_in_shell(target: Path) -> None:
    """Open a file or directory in the Windows shell."""
    os.startfile(str(target))
