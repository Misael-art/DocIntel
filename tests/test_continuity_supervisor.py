import unittest
from unittest.mock import patch

import continuity_supervisor


class ContinuitySupervisorTests(unittest.TestCase):
    @patch("continuity_supervisor.subprocess.run")
    @patch("continuity_supervisor.write_state")
    @patch("continuity_supervisor.log")
    def test_run_post_processing_never_executes_copy_operations(
        self,
        _log,
        _write_state,
        run_mock,
    ):
        state = {"post_processing_done": False, "launch_count": 0}

        continuity_supervisor.run_post_processing(state)

        calls = run_mock.call_args_list
        self.assertEqual(len(calls), 1)
        command = calls[0].args[0]
        self.assertIn(continuity_supervisor.POST_SCRIPT, command)
        self.assertNotIn("--execute", command)
        self.assertNotIn("--execute-copy", command)
        self.assertTrue(state["post_processing_done"])
        self.assertTrue(state["organization_planned"])
