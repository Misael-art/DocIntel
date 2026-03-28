import json
import os
import tempfile
import unittest
from unittest.mock import patch

from db.operations import log_audit
from docintel.db.connection import get_connection, init_database


class AuditLogTests(unittest.TestCase):
    def test_log_audit_persists_structured_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "audit.db")
            with patch.dict(os.environ, {"DOCINTEL_DB_PATH": db_path}, clear=False):
                init_database()
                log_audit(
                    "VALIDATOR",
                    "PRECHECK",
                    "manifest.csv",
                    "BLOCKED",
                    "Validation did not pass.",
                    severity="ERROR",
                    correlation_id="corr-123",
                    details_json={"rule": "NO_DESTINATION_COLLISION", "passed": False},
                )

                conn = get_connection(query_only=True)
                try:
                    row = conn.execute(
                        """
                        SELECT etapa, acao, alvo, resultado, detalhes, severity, correlation_id, details_json
                        FROM audit_log
                        ORDER BY id DESC
                        LIMIT 1
                        """
                    ).fetchone()
                finally:
                    conn.close()

                self.assertEqual(row["etapa"], "VALIDATOR")
                self.assertEqual(row["acao"], "PRECHECK")
                self.assertEqual(row["severity"], "ERROR")
                self.assertEqual(row["correlation_id"], "corr-123")
                self.assertEqual(
                    json.loads(row["details_json"]),
                    {"rule": "NO_DESTINATION_COLLISION", "passed": False},
                )
