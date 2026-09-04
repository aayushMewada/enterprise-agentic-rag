import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.approvals import approve_pending_action, create_pending_approval


TICKET_ARGUMENTS = {
    "request_id": "REQ-104",
    "category": "Documentation Follow-up",
    "priority": "Normal",
    "reason": "Request a valid address proof document.",
    "policy_citations": [
        "SYN-AO-001 section 2",
        "SYN-EX-003 section 1",
        "SYN-SLA-004 section 1",
        "SYN-SLA-004 section 2",
    ],
}


class ApprovalTests(unittest.TestCase):
    def test_approval_executes_frozen_ticket_proposal_once(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            approvals_path = root / "approvals.json"
            tickets_path = root / "tickets.json"

            with (
                patch("agent.approvals.APPROVALS_PATH", approvals_path),
                patch("agent.tools.RUNTIME_TICKETS_PATH", tickets_path),
            ):
                approval = create_pending_approval(
                    "create_followup_ticket",
                    TICKET_ARGUMENTS,
                )
                result = approve_pending_action(
                    approval["approval_id"],
                    approved_by="test-reviewer",
                )

                self.assertTrue(result["result"]["ok"])
                self.assertTrue(result["result"]["data"]["created"])
                self.assertEqual(
                    result["result"]["data"]["ticket"]["approved_by"],
                    "test-reviewer",
                )

                with self.assertRaises(ValueError):
                    approve_pending_action(
                        approval["approval_id"],
                        approved_by="test-reviewer",
                    )


if __name__ == "__main__":
    unittest.main()
