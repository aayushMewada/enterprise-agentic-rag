import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


class AgentApiTests(unittest.TestCase):
    @patch("api.main.run_agent")
    def test_agent_query_returns_trace_and_approval(self, run_agent_mock):
        run_agent_mock.return_value = {
            "answer": "REQ-104 is incomplete.",
            "trace": [{"step": 1, "tool": "get_request_status", "ok": True}],
            "sources": [],
            "pending_approvals": [],
            "steps": 1,
            "stop_reason": "completed",
        }

        response = client.post(
            "/agent/query",
            json={"message": "Check REQ-104", "chat_history": []},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "REQ-104 is incomplete.")
        self.assertEqual(
            response.json()["trace"][0]["tool"],
            "get_request_status",
        )

    @patch("api.main.approve_pending_action")
    def test_approve_endpoint_uses_reviewed_proposal(self, approve_mock):
        approve_mock.return_value = {
            "result": {
                "ok": True,
                "data": {"ticket": {"ticket_id": "TKT-1002"}},
            }
        }

        response = client.post(
            "/agent/approvals/APR-12345678/approve",
            json={"reviewer": "test-reviewer"},
        )

        self.assertEqual(response.status_code, 200)
        approve_mock.assert_called_once_with(
            "APR-12345678",
            approved_by="test-reviewer",
        )

    @patch("api.main.reject_pending_action")
    def test_reject_endpoint_returns_validation_error(self, reject_mock):
        reject_mock.side_effect = ValueError("Approval is already Executed.")

        response = client.post(
            "/agent/approvals/APR-12345678/reject",
            json={"reviewer": "test-reviewer"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("already Executed", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
