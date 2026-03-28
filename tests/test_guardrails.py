import unittest

from docintel.core.enums import ExecutionMode, ValidationStatus
from docintel.core.models import ExecutionRequest
from docintel.guardrails import evaluate_execution_request


class GuardrailTests(unittest.TestCase):
    def test_dry_run_is_allowed_without_manifest(self):
        decision = evaluate_execution_request(
            ExecutionRequest(
                mode=ExecutionMode.DRY_RUN,
                manual_approval_present=False,
                manifest_path=None,
                validation_completed=False,
            )
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.status, ValidationStatus.PASSED)

    def test_apply_is_blocked_until_all_prerequisites_exist(self):
        decision = evaluate_execution_request(
            ExecutionRequest(
                mode=ExecutionMode.APPLY,
                manual_approval_present=False,
                manifest_path=None,
                validation_completed=False,
            )
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.status, ValidationStatus.BLOCKED)
        self.assertIn("MANUAL_APPROVAL_REQUIRED", decision.blockers)
        self.assertIn("VALIDATION_NOT_COMPLETED", decision.blockers)
        self.assertIn("EXECUTABLE_MANIFEST_REQUIRED", decision.blockers)
