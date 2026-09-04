import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent.orchestrator import run_agent


def _response(content=None, tool_calls=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    tool_calls=tool_calls,
                )
            )
        ]
    )


def _tool_call(name, arguments, call_id="call-1"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.responses.pop(0)


class FakeGroqClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))


class AgentOrchestratorTests(unittest.TestCase):
    def test_agent_returns_direct_answer_without_tools(self):
        client = FakeGroqClient([_response(content="Hello. How can I help?")])

        result = run_agent("Hello", client=client)

        self.assertEqual(result["answer"], "Hello. How can I help?")
        self.assertEqual(result["trace"], [])
        self.assertEqual(result["stop_reason"], "completed")

    @patch("agent.orchestrator.execute_tool")
    def test_agent_executes_tool_and_returns_final_answer(self, execute_tool_mock):
        execute_tool_mock.return_value = {
            "ok": True,
            "tool": "get_request_status",
            "requires_approval": False,
            "data": {
                "found": True,
                "request": {
                    "request_id": "REQ-104",
                    "status": "Incomplete",
                },
            },
        }
        client = FakeGroqClient(
            [
                _response(
                    tool_calls=[
                        _tool_call(
                            "get_request_status",
                            '{"request_id":"REQ-104"}',
                        )
                    ]
                ),
                _response(content="REQ-104 is Incomplete."),
            ]
        )

        result = run_agent("Check REQ-104", client=client)

        execute_tool_mock.assert_called_once_with(
            "get_request_status",
            {"request_id": "REQ-104"},
        )
        self.assertEqual(result["answer"], "REQ-104 is Incomplete.")
        self.assertEqual(result["trace"][0]["tool"], "get_request_status")
        self.assertTrue(result["trace"][0]["ok"])

        second_request_messages = client.chat.completions.requests[1]["messages"]
        self.assertEqual(second_request_messages[-1]["role"], "tool")
        self.assertEqual(second_request_messages[-1]["tool_call_id"], "call-1")

    def test_agent_rejects_invalid_step_limit(self):
        client = FakeGroqClient([])

        with self.assertRaises(ValueError):
            run_agent("Hello", max_steps=6, client=client)


if __name__ == "__main__":
    unittest.main()
