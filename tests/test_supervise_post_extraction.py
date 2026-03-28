import types
import unittest
from unittest.mock import call, patch

import supervise_post_extraction


class SupervisePostExtractionTests(unittest.TestCase):
    @patch("supervise_post_extraction.write_supervision_report")
    @patch("supervise_post_extraction.run_python_script")
    @patch("supervise_post_extraction.stage3_status")
    @patch("supervise_post_extraction.parse_args")
    def test_main_generates_safe_plan_without_execute_copy(
        self,
        parse_args_mock,
        stage3_status_mock,
        run_python_script_mock,
        write_report_mock,
    ):
        parse_args_mock.return_value = types.SimpleNamespace(
            execute_copy=False,
            manifest=None,
            limit=7,
        )
        stage3_status_mock.return_value = {
            "pending_f1_f2": 0,
            "done_f1_f2": 10,
            "target_total_f1_f2": 10,
            "stage3_complete": True,
        }

        supervise_post_extraction.main()

        self.assertEqual(
            run_python_script_mock.call_args_list,
            [
                call(supervise_post_extraction.GATE_SCRIPT),
                call(supervise_post_extraction.ORG_SCRIPT, ["--limit", "7"]),
            ],
        )
        write_report_mock.assert_called_once()

    @patch("supervise_post_extraction.stage3_status")
    @patch("supervise_post_extraction.parse_args")
    def test_main_blocks_execute_copy_without_manifest(
        self,
        parse_args_mock,
        stage3_status_mock,
    ):
        parse_args_mock.return_value = types.SimpleNamespace(
            execute_copy=True,
            manifest=None,
            limit=0,
        )
        stage3_status_mock.return_value = {
            "pending_f1_f2": 0,
            "done_f1_f2": 10,
            "target_total_f1_f2": 10,
            "stage3_complete": True,
        }

        with patch("supervise_post_extraction.run_python_script"):
            with patch("supervise_post_extraction.os.path.exists", return_value=False):
                with self.assertRaises(SystemExit) as ctx:
                    supervise_post_extraction.main()

        self.assertIn("EXECUTABLE_MANIFEST_REQUIRED", str(ctx.exception))

    @patch("supervise_post_extraction.write_supervision_report")
    @patch("supervise_post_extraction.run_python_script")
    @patch("supervise_post_extraction.stage3_status")
    @patch("supervise_post_extraction.parse_args")
    def test_main_execute_copy_requires_gate_and_manifest(
        self,
        parse_args_mock,
        stage3_status_mock,
        run_python_script_mock,
        write_report_mock,
    ):
        parse_args_mock.return_value = types.SimpleNamespace(
            execute_copy=True,
            manifest=r"F:\DocIntel\output\reports\organizacao_drive_pessoal\i_drive_curated_manifest.csv",
            limit=0,
        )
        stage3_status_mock.return_value = {
            "pending_f1_f2": 0,
            "done_f1_f2": 10,
            "target_total_f1_f2": 10,
            "stage3_complete": True,
        }

        def fake_exists(path: str) -> bool:
            return path == supervise_post_extraction.GATE_OK

        with patch("supervise_post_extraction.os.path.exists", side_effect=fake_exists):
            supervise_post_extraction.main()

        self.assertEqual(
            run_python_script_mock.call_args_list,
            [
                call(supervise_post_extraction.GATE_SCRIPT),
                call(
                    supervise_post_extraction.ORG_SCRIPT,
                    [
                        "--execute",
                        "--manifest",
                        r"F:\DocIntel\output\reports\organizacao_drive_pessoal\i_drive_curated_manifest.csv",
                    ],
                ),
            ],
        )
        write_report_mock.assert_called_once()
