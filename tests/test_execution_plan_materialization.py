import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import organization_planner
from docintel.db.connection import get_connection, init_database
from docintel.validator.service import resolve_manifest_validation_status


class ExecutionPlanMaterializationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "docintel.db"
        self.source_dir = self.root / "source"
        self.dest_i = self.root / "I_Drive"
        self.dest_f = self.root / "F_Drive"
        self.gdrive = self.root / "GoogleDrive"
        self.manifest_dir = self.root / "reports"
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.dest_i.mkdir(parents=True, exist_ok=True)
        self.dest_f.mkdir(parents=True, exist_ok=True)
        self.gdrive.mkdir(parents=True, exist_ok=True)
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

        self.project_file = self.source_dir / "README.md"
        self.project_file.write_text("# projeto\n", encoding="utf-8")
        self.ambiguous_file = self.source_dir / "blob.dat"
        self.ambiguous_file.write_bytes(b"dado ambiguo")

        with patch.dict(os.environ, {"DOCINTEL_DB_PATH": str(self.db_path)}, clear=False):
            init_database()

        conn = get_connection(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO files (
                    caminho_completo, nome_arquivo, extensao, tamanho_bytes,
                    disco_origem, pasta_raiz, profundidade, fase_correspondente,
                    status_indexacao, hash_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(self.project_file),
                    self.project_file.name,
                    ".md",
                    self.project_file.stat().st_size,
                    "F:\\",
                    "Projects",
                    1,
                    "FASE_2",
                    "HASH_CALCULADO",
                    "abc123",
                ),
            )
            conn.execute(
                """
                INSERT INTO files (
                    caminho_completo, nome_arquivo, extensao, tamanho_bytes,
                    disco_origem, pasta_raiz, profundidade, fase_correspondente,
                    status_indexacao, hash_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(self.ambiguous_file),
                    self.ambiguous_file.name,
                    ".dat",
                    self.ambiguous_file.stat().st_size,
                    "F:\\",
                    "Misc",
                    1,
                    "INDEFINIDO",
                    "HASH_CALCULADO",
                    "def456",
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _patched_destinations(self):
        return {
            "GOOGLE_DRIVE": {
                "label": "Google Drive",
                "root": str(self.gdrive),
                "logical_root": "GOOGLE_DRIVE://",
                "min_free_bytes": None,
                "allow_execute": True,
            },
            "I_DRIVE": {
                "label": "I:\\",
                "root": str(self.dest_i),
                "logical_root": str(self.dest_i),
                "min_free_bytes": 0,
                "allow_execute": True,
            },
            "F_DRIVE": {
                "label": "F:\\",
                "root": str(self.dest_f),
                "logical_root": str(self.dest_f),
                "min_free_bytes": 0,
                "allow_execute": True,
            },
            "REVIEW_QUEUE": {
                "label": "Review Queue",
                "root": None,
                "logical_root": "REVIEW_QUEUE://",
                "min_free_bytes": None,
                "allow_execute": False,
            },
            "KEEP_ON_SOURCE": {
                "label": "Manter na origem",
                "root": None,
                "logical_root": "KEEP_ON_SOURCE://",
                "min_free_bytes": None,
                "allow_execute": False,
            },
        }

    def _patch_runtime(self):
        manifest_paths = {
            "GOOGLE_DRIVE": str(self.manifest_dir / "google_drive_manifest.csv"),
            "C_DRAIN": str(self.manifest_dir / "drain_c_manifest.csv"),
            "I_DRIVE": str(self.manifest_dir / "i_drive_curated_manifest.csv"),
            "F_DRIVE": str(self.manifest_dir / "f_drive_cold_storage_manifest.csv"),
            "REVIEW": str(self.manifest_dir / "review_queue_manifest.csv"),
        }
        return patch.multiple(
            organization_planner,
            DB_PATH=str(self.db_path),
            MANIFEST_DIR=str(self.manifest_dir),
            COMBINED_MANIFEST_PATH=str(self.manifest_dir / "organization_manifest.csv"),
            SUMMARY_PATH=str(self.manifest_dir / "organization_summary.md"),
            TOP_RISKS_PATH=str(self.manifest_dir / "top_riscos_operacionais.md"),
            EXECUTION_LOG_PATH=str(self.manifest_dir / "execution_log.csv"),
            MANIFEST_PATHS=manifest_paths,
            DESTINATIONS=self._patched_destinations(),
            SOURCE_DRIVES=["F:\\"],
        )

    def test_build_plan_materializes_execution_plan_and_validation_results(self):
        with patch.dict(os.environ, {"DOCINTEL_DB_PATH": str(self.db_path)}, clear=False):
            with self._patch_runtime():
                with patch("organization_planner.iter_c_user_files", return_value=[]):
                    with patch("organization_planner.summarize_c_user_targets", return_value={}):
                        result = organization_planner.build_plan(limit=0, include_c_audit=False)

        self.assertEqual(result["plan_status"], "VALIDATED_WITH_BLOCKERS")
        self.assertTrue(Path(result["validation_report"]).exists())

        conn = get_connection(self.db_path, query_only=True)
        try:
            plan = conn.execute(
                "SELECT plan_key, status FROM execution_plans ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.assertIsNotNone(plan)
            self.assertEqual(plan["status"], "VALIDATED_WITH_BLOCKERS")

            manifest_statuses = {
                row["manifest_kind"]: row["status"]
                for row in conn.execute("SELECT manifest_kind, status FROM manifests ORDER BY id")
            }
            self.assertEqual(manifest_statuses["I_DRIVE"], "VALIDATED")
            self.assertEqual(manifest_statuses["REVIEW"], "REVIEW_REQUIRED")

            step_statuses = [row["status"] for row in conn.execute("SELECT status FROM execution_steps ORDER BY step_order")]
            self.assertEqual(step_statuses, ["READY", "BLOCKED"])

            validation_count = conn.execute("SELECT COUNT(*) FROM validation_results").fetchone()[0]
            self.assertGreaterEqual(validation_count, 4)
        finally:
            conn.close()

    def test_execute_manifest_runs_only_for_validated_manifest(self):
        with patch.dict(os.environ, {"DOCINTEL_DB_PATH": str(self.db_path)}, clear=False):
            with self._patch_runtime():
                with patch("organization_planner.iter_c_user_files", return_value=[]):
                    with patch("organization_planner.summarize_c_user_targets", return_value={}):
                        result = organization_planner.build_plan(limit=0, include_c_audit=False)

                i_manifest = organization_planner.MANIFEST_PATHS["I_DRIVE"]
                review_manifest = organization_planner.MANIFEST_PATHS["REVIEW"]

                self.assertEqual(
                    resolve_manifest_validation_status(str(self.db_path), os.path.abspath(i_manifest)),
                    "VALIDATED",
                )
                self.assertEqual(
                    resolve_manifest_validation_status(str(self.db_path), os.path.abspath(review_manifest)),
                    "REVIEW_REQUIRED",
                )

                execution_log = self.manifest_dir / "i_drive_execution.csv"
                organization_planner.execute_manifest(i_manifest, str(execution_log))
                copied_file = next(self.dest_i.rglob("README.md"))
                self.assertTrue(copied_file.exists())
                self.assertEqual(copied_file.read_text(encoding="utf-8"), "# projeto\n")

                with self.assertRaises(SystemExit):
                    organization_planner.execute_manifest(review_manifest, str(self.manifest_dir / "review_execution.csv"))

                with execution_log.open(newline="", encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual(rows[0]["result"], "COPIED")

    def test_capacity_validation_blocks_manifest_and_execution(self):
        volume_root = f"{self.dest_i.drive}\\"
        low_capacity = {
            "label": volume_root,
            "free": 0,
            "total": 1024,
            "used": 1024,
            "exists": True,
        }

        with patch.dict(os.environ, {"DOCINTEL_DB_PATH": str(self.db_path)}, clear=False):
            with self._patch_runtime():
                with patch("organization_planner.iter_c_user_files", return_value=[]):
                    with patch("organization_planner.summarize_c_user_targets", return_value={}):
                        with patch(
                            "docintel.validator.service.get_volume_info",
                            side_effect=lambda path: low_capacity if path == volume_root else {
                                "label": path,
                                "free": 1024 * 1024 * 1024,
                                "total": 2 * 1024 * 1024 * 1024,
                                "used": 1024 * 1024 * 1024,
                                "exists": True,
                            },
                        ):
                            result = organization_planner.build_plan(limit=0, include_c_audit=False)

                self.assertEqual(result["plan_status"], "VALIDATED_WITH_BLOCKERS")
                i_manifest = organization_planner.MANIFEST_PATHS["I_DRIVE"]
                self.assertEqual(
                    resolve_manifest_validation_status(str(self.db_path), os.path.abspath(i_manifest)),
                    "BLOCKED",
                )

                with self.assertRaises(SystemExit):
                    organization_planner.execute_manifest(i_manifest, str(self.manifest_dir / "blocked.csv"))

        conn = get_connection(self.db_path, query_only=True)
        try:
            capacity_row = conn.execute(
                """
                SELECT status, message
                FROM validation_results
                WHERE scope_type = 'MANIFEST' AND scope_ref = 'I_DRIVE' AND rule_code = 'DESTINATION_CAPACITY_CHECK'
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
            self.assertIsNotNone(capacity_row)
            self.assertEqual(capacity_row["status"], "BLOCKED")
            self.assertIn("nao possui folga suficiente", capacity_row["message"])
        finally:
            conn.close()
