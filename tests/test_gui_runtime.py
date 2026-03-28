import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from docintel.gui.runtime import (
    build_script_command,
    database_is_current,
    parse_stage3_summary,
)


class GuiRuntimeTests(unittest.TestCase):
    def test_build_script_command_uses_root_python(self):
        command = build_script_command("monitor_extraction.py", "--limit", "1")
        self.assertTrue(command[0].endswith("python.exe") or command[0].endswith("python"))
        self.assertTrue(command[1].endswith("monitor_extraction.py"))
        self.assertEqual(command[2:], ["--limit", "1"])

    def test_parse_stage3_summary_reads_markdown_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_path = Path(temp_dir) / "status_execucao.md"
            status_path.write_text(
                "# Status\n| Campo | Valor |\n|-------|-------|\n| **Arquivos Processados** | 1,234 / 2,000 |\n",
                encoding="utf-8",
            )
            summary = parse_stage3_summary(status_path)
            self.assertIn("1,234/2,000".replace("/", ""), summary.replace("/", ""))
            self.assertIn("766", summary)

    def test_database_is_current_detects_missing_migrations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "plain.db"
            db_path.touch()
            self.assertFalse(database_is_current(db_path))

    def test_database_is_current_accepts_initialized_db(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "docintel.db")
            with patch.dict(os.environ, {"DOCINTEL_DB_PATH": db_path}, clear=False):
                from docintel.db.connection import init_database

                init_database()
                self.assertTrue(database_is_current(Path(db_path)))
