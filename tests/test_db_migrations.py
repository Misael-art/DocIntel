import os
import sqlite3
import tempfile
import unittest

from docintel.db.connection import get_connection, init_database


class DatabaseMigrationTests(unittest.TestCase):
    def test_init_database_creates_required_tables_and_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "docintel_test.db")
            init_database(db_path)

            conn = get_connection(db_path, query_only=True)
            try:
                tables = {
                    row["name"]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                expected_tables = {
                    "files",
                    "documents",
                    "projects",
                    "duplicates",
                    "entities",
                    "relations",
                    "classifications",
                    "actions_proposed",
                    "organization_decisions",
                    "execution_plans",
                    "execution_steps",
                    "validation_results",
                    "link_registry",
                    "naming_rules",
                    "policy_exceptions",
                    "manifests",
                    "config_rewrites",
                    "risk_assessments",
                    "audit_log",
                    "schema_migrations",
                }
                self.assertTrue(expected_tables.issubset(tables))

                project_columns = {
                    row["name"] for row in conn.execute("PRAGMA table_info(projects)")
                }
                self.assertIn("created_at", project_columns)
                self.assertIn("updated_at", project_columns)

                audit_columns = {
                    row["name"] for row in conn.execute("PRAGMA table_info(audit_log)")
                }
                self.assertIn("severity", audit_columns)
                self.assertIn("correlation_id", audit_columns)
                self.assertIn("details_json", audit_columns)

                versions = [
                    row["version"]
                    for row in conn.execute(
                        "SELECT version FROM schema_migrations ORDER BY version"
                    )
                ]
                self.assertEqual(
                    versions,
                    ["0001_baseline_schema", "0002_legacy_hardening"],
                )
            finally:
                conn.close()

    def test_init_database_hardens_legacy_projects_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "legacy.db")
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pasta_raiz TEXT NOT NULL UNIQUE,
                    nome_projeto TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT DEFAULT (datetime('now')),
                    etapa TEXT NOT NULL,
                    acao TEXT NOT NULL
                )
                """
            )
            conn.commit()
            conn.close()

            init_database(db_path)

            conn = sqlite3.connect(db_path)
            try:
                project_columns = {row[1] for row in conn.execute("PRAGMA table_info(projects)")}
                self.assertIn("updated_at", project_columns)

                audit_columns = {row[1] for row in conn.execute("PRAGMA table_info(audit_log)")}
                self.assertIn("severity", audit_columns)
                self.assertIn("details_json", audit_columns)
            finally:
                conn.close()
