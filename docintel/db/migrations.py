"""Explicit SQLite migrations for DocIntel."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Migration:
    version: str
    description: str
    apply: Callable[[sqlite3.Connection], None]


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row[1] == column_name for row in rows)


def _add_column_if_missing(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_sql: str,
) -> None:
    if not _column_exists(conn, table_name, column_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")


def _baseline_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caminho_completo TEXT NOT NULL UNIQUE,
            nome_arquivo TEXT NOT NULL,
            extensao TEXT,
            tamanho_bytes INTEGER,
            hash_sha256 TEXT,
            hash_md5 TEXT,
            data_criacao TEXT,
            data_modificacao TEXT,
            data_ultimo_acesso TEXT,
            disco_origem TEXT NOT NULL,
            pasta_raiz TEXT,
            profundidade INTEGER,
            mime_type TEXT,
            idioma_detectado TEXT,
            encoding TEXT,
            texto_extraido TEXT,
            status_indexacao TEXT DEFAULT 'PENDENTE',
            status_triagem TEXT DEFAULT 'NAO_TRIADO',
            nivel_criticidade TEXT DEFAULT 'INDEFINIDO',
            nivel_confianca_classificacao REAL DEFAULT 0.0,
            requer_revisao_humana INTEGER DEFAULT 0,
            observacoes TEXT,
            fase_correspondente TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL UNIQUE,
            tipo_documento TEXT,
            subtipo_documento TEXT,
            assunto_principal TEXT,
            resumo_semantico TEXT,
            entidades_detectadas TEXT,
            pessoa_principal_relacionada TEXT,
            pessoas_secundarias TEXT,
            organizacoes_detectadas TEXT,
            datas_relevantes TEXT,
            numeros_relevantes TEXT,
            contexto_juridico TEXT,
            contexto_financeiro TEXT,
            contexto_profissional TEXT,
            contexto_familiar TEXT,
            contexto_migratorio TEXT,
            contexto_tecnico TEXT,
            contexto_medico TEXT,
            sensibilidade TEXT DEFAULT 'NORMAL',
            tags_semanticas TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (file_id) REFERENCES files(id)
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pasta_raiz TEXT NOT NULL UNIQUE,
            nome_projeto TEXT,
            categoria_projeto TEXT,
            status_projeto TEXT DEFAULT 'INDEFINIDO',
            ativo_ou_legado TEXT DEFAULT 'INDEFINIDO',
            ultimo_sinal_atividade TEXT,
            stack_detectada TEXT,
            linguagem_predominante TEXT,
            tem_git INTEGER DEFAULT 0,
            tem_node_modules INTEGER DEFAULT 0,
            tem_build INTEGER DEFAULT 0,
            repositorios_relacionados TEXT,
            documentacao_relacionada TEXT,
            ambiente_relacionado TEXT,
            backup_ou_workspace_real TEXT DEFAULT 'INDEFINIDO',
            risco_de_duplicidade TEXT,
            tamanho_total_bytes INTEGER,
            total_arquivos INTEGER,
            observacoes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS duplicates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id_origem INTEGER NOT NULL,
            file_id_relacionado INTEGER NOT NULL,
            tipo_duplicidade TEXT,
            similaridade REAL,
            criterio TEXT,
            recomendacao TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (file_id_origem) REFERENCES files(id),
            FOREIGN KEY (file_id_relacionado) REFERENCES files(id),
            UNIQUE(file_id_origem, file_id_relacionado)
        );

        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_entidade TEXT NOT NULL,
            tipo_entidade TEXT,
            variantes TEXT,
            observacoes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(nome_entidade, tipo_entidade)
        );

        CREATE TABLE IF NOT EXISTS relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_entity_type TEXT NOT NULL,
            source_entity_id INTEGER NOT NULL,
            relation_type TEXT NOT NULL,
            target_entity_type TEXT NOT NULL,
            target_entity_id INTEGER NOT NULL,
            metadata_json TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS classifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            classe_principal TEXT NOT NULL,
            classes_secundarias TEXT,
            justificativa_textual TEXT NOT NULL,
            metodo_classificacao TEXT,
            score REAL DEFAULT 0.0,
            revisado_por_humano INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (file_id) REFERENCES files(id)
        );

        CREATE TABLE IF NOT EXISTS actions_proposed (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER,
            project_id INTEGER,
            acao_sugerida TEXT NOT NULL,
            destino_sugerido TEXT,
            justificativa TEXT NOT NULL,
            risco TEXT DEFAULT 'BAIXO',
            depende_de_aprovacao INTEGER DEFAULT 1,
            status_aprovacao TEXT DEFAULT 'PENDENTE',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (file_id) REFERENCES files(id),
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );

        CREATE TABLE IF NOT EXISTS organization_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER,
            source_path TEXT NOT NULL UNIQUE,
            source_drive TEXT,
            fase_correspondente TEXT,
            categoria_operacional TEXT,
            temperatura_acesso TEXT,
            destino_recomendado TEXT,
            colecao_canonica TEXT,
            acao_recomendada TEXT,
            nome_normalizado TEXT,
            destino_logico TEXT,
            destino_fisico TEXT,
            justificativa_curta TEXT,
            risco_operacional TEXT DEFAULT 'MEDIO',
            confidence_label TEXT DEFAULT 'MEDIA',
            duplicate_hint TEXT,
            execution_blockers TEXT,
            requer_revisao_humana INTEGER DEFAULT 0,
            policy_version TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (file_id) REFERENCES files(id)
        );

        CREATE TABLE IF NOT EXISTS execution_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_key TEXT NOT NULL UNIQUE,
            plan_kind TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'DRAFT',
            mode TEXT NOT NULL DEFAULT 'DRY_RUN',
            source_snapshot_at TEXT,
            validated_at TEXT,
            approved_at TEXT,
            approved_by TEXT,
            summary TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS execution_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            step_order INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            source_path TEXT,
            destination_path TEXT,
            link_type TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            rollback_supported INTEGER NOT NULL DEFAULT 0,
            rollback_state TEXT,
            journal_payload TEXT,
            error_message TEXT,
            started_at TEXT,
            finished_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (plan_id) REFERENCES execution_plans(id),
            UNIQUE(plan_id, step_order)
        );

        CREATE TABLE IF NOT EXISTS validation_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER,
            step_id INTEGER,
            scope_type TEXT NOT NULL,
            scope_ref TEXT NOT NULL,
            rule_code TEXT NOT NULL,
            severity TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT NOT NULL,
            evidence_json TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (plan_id) REFERENCES execution_plans(id),
            FOREIGN KEY (step_id) REFERENCES execution_steps(id)
        );

        CREATE TABLE IF NOT EXISTS link_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_path TEXT NOT NULL,
            link_path TEXT NOT NULL UNIQUE,
            target_path TEXT NOT NULL,
            link_type TEXT NOT NULL,
            validation_status TEXT NOT NULL DEFAULT 'PENDING',
            last_validated_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS naming_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_name TEXT NOT NULL UNIQUE,
            unicode_normalization TEXT NOT NULL,
            invalid_char_policy TEXT NOT NULL,
            whitespace_policy TEXT NOT NULL,
            collision_strategy TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS policy_exceptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope_type TEXT NOT NULL,
            scope_ref TEXT NOT NULL,
            policy_code TEXT NOT NULL,
            rationale TEXT NOT NULL,
            approved_by TEXT,
            expires_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS manifests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manifest_key TEXT NOT NULL UNIQUE,
            manifest_kind TEXT NOT NULL,
            plan_id INTEGER,
            file_path TEXT NOT NULL,
            checksum_sha256 TEXT,
            row_count INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'GENERATED',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (plan_id) REFERENCES execution_plans(id)
        );

        CREATE TABLE IF NOT EXISTS config_rewrites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER,
            target_path TEXT NOT NULL,
            backup_manifest_ref TEXT,
            proposed_diff TEXT NOT NULL,
            validation_status TEXT NOT NULL DEFAULT 'PENDING',
            applied_at TEXT,
            reverted_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (plan_id) REFERENCES execution_plans(id)
        );

        CREATE TABLE IF NOT EXISTS risk_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER,
            scope_type TEXT NOT NULL,
            scope_ref TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            risk_code TEXT NOT NULL,
            confidence REAL DEFAULT 0.0,
            summary TEXT NOT NULL,
            blockers TEXT,
            mitigation TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (plan_id) REFERENCES execution_plans(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT (datetime('now')),
            etapa TEXT NOT NULL,
            acao TEXT NOT NULL,
            alvo TEXT,
            resultado TEXT,
            detalhes TEXT,
            severity TEXT DEFAULT 'INFO',
            correlation_id TEXT,
            details_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_files_hash ON files(hash_sha256);
        CREATE INDEX IF NOT EXISTS idx_files_ext ON files(extensao);
        CREATE INDEX IF NOT EXISTS idx_files_disco ON files(disco_origem);
        CREATE INDEX IF NOT EXISTS idx_files_fase ON files(fase_correspondente);
        CREATE INDEX IF NOT EXISTS idx_files_criticidade ON files(nivel_criticidade);
        CREATE INDEX IF NOT EXISTS idx_files_pasta_raiz ON files(pasta_raiz);
        CREATE INDEX IF NOT EXISTS idx_files_status ON files(status_indexacao);
        CREATE INDEX IF NOT EXISTS idx_classifications_classe ON classifications(classe_principal);
        CREATE INDEX IF NOT EXISTS idx_org_decisions_dest ON organization_decisions(destino_recomendado);
        CREATE INDEX IF NOT EXISTS idx_org_decisions_collection ON organization_decisions(colecao_canonica);
        CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_entity_type, source_entity_id);
        CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_entity_type, target_entity_id);
        CREATE INDEX IF NOT EXISTS idx_execution_steps_plan ON execution_steps(plan_id, status);
        CREATE INDEX IF NOT EXISTS idx_validation_results_scope ON validation_results(scope_type, scope_ref, status);
        CREATE INDEX IF NOT EXISTS idx_link_registry_target ON link_registry(target_path, validation_status);
        CREATE INDEX IF NOT EXISTS idx_manifests_plan ON manifests(plan_id, status);
        CREATE INDEX IF NOT EXISTS idx_risk_assessments_scope ON risk_assessments(scope_type, scope_ref, risk_level);
        CREATE INDEX IF NOT EXISTS idx_audit_log_etapa ON audit_log(etapa, timestamp);
        """
    )


def _legacy_hardening(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "projects"):
        return

    _add_column_if_missing(conn, "projects", "repositorios_relacionados", "repositorios_relacionados TEXT")
    _add_column_if_missing(conn, "projects", "documentacao_relacionada", "documentacao_relacionada TEXT")
    _add_column_if_missing(conn, "projects", "ambiente_relacionado", "ambiente_relacionado TEXT")
    _add_column_if_missing(conn, "projects", "risco_de_duplicidade", "risco_de_duplicidade TEXT")
    _add_column_if_missing(
        conn,
        "projects",
        "created_at",
        "created_at TEXT DEFAULT (datetime('now'))",
    )
    _add_column_if_missing(
        conn,
        "projects",
        "updated_at",
        "updated_at TEXT DEFAULT (datetime('now'))",
    )
    _add_column_if_missing(
        conn,
        "audit_log",
        "severity",
        "severity TEXT DEFAULT 'INFO'",
    )
    _add_column_if_missing(
        conn,
        "audit_log",
        "correlation_id",
        "correlation_id TEXT",
    )
    _add_column_if_missing(
        conn,
        "audit_log",
        "details_json",
        "details_json TEXT",
    )


MIGRATIONS: tuple[Migration, ...] = (
    Migration("0001_baseline_schema", "Create baseline production schema.", _baseline_schema),
    Migration("0002_legacy_hardening", "Backfill legacy columns and audit fields.", _legacy_hardening),
)


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply pending migrations in order."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    applied = {
        row[0]
        for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")
    }

    for migration in MIGRATIONS:
        if migration.version in applied:
            continue
        migration.apply(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
            (migration.version, migration.description),
        )
        conn.commit()
