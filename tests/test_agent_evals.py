import unittest

from evals.run_evals import score_scenario


class AgentEvaluationTests(unittest.TestCase):
    def test_scores_successful_approval_scenario(self):
        scenario = {
            "id": "approval",
            "required_tools": ["get_request_status", "create_followup_ticket"],
            "forbidden_tools": [],
            "expect_approval": True,
            "expected_stop_reason": "approval_required",
        }
        result = {
            "answer": "A ticket is awaiting approval.",
            "trace": [
                {"tool": "get_request_status", "ok": True},
                {"tool": "create_followup_ticket", "ok": True},
            ],
            "pending_approval": {"approval_id": "APR-TEST"},
            "stop_reason": "approval_required",
        }

        scored = score_scenario(scenario, result)

        self.assertTrue(scored.passed)
        self.assertEqual(scored.approval_id, "APR-TEST")

    def test_detects_forbidden_tool(self):
        scenario = {
            "id": "read_only",
            "required_tools": ["get_request_status"],
            "forbidden_tools": ["create_followup_ticket"],
            "expect_approval": False,
            "expected_stop_reason": "completed",
        }
        result = {
            "answer": "Done.",
            "trace": [
                {"tool": "get_request_status", "ok": True},
                {"tool": "create_followup_ticket", "ok": True},
            ],
            "stop_reason": "completed",
        }

        scored = score_scenario(scenario, result)

        self.assertFalse(scored.passed)

    def test_recognizes_failed_guarded_write(self):
        scenario = {
            "id": "guardrail",
            "required_tools": ["get_request_status"],
            "forbidden_tools": [],
            "expect_approval": False,
            "expected_stop_reason": "completed",
            "require_failed_tool": "create_followup_ticket",
        }
        result = {
            "answer": "The action was blocked.",
            "trace": [
                {"tool": "get_request_status", "ok": True},
                {"tool": "create_followup_ticket", "ok": False},
            ],
            "stop_reason": "completed",
        }

        scored = score_scenario(scenario, result)

        self.assertTrue(scored.passed)

    def test_recognizes_approval_stop_without_embedded_proposal(self):
        scenario = {
            "id": "approval_stop",
            "required_tools": ["create_followup_ticket"],
            "forbidden_tools": [],
            "expect_approval": True,
            "expected_stop_reason": "approval_required",
        }
        result = {
            "answer": "The proposed action requires approval.",
            "trace": [{"tool": "create_followup_ticket", "ok": True}],
            "stop_reason": "approval_required",
        }

        scored = score_scenario(scenario, result)

        self.assertTrue(scored.passed)


if __name__ == "__main__":
    unittest.main()
