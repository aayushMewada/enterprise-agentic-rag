import unittest
from unittest.mock import patch

from agent.tools import execute_tool, get_tool_schemas


class AgentToolTests(unittest.TestCase):
    def test_tool_schemas_publish_all_read_only_tools(self):
        names = {
            schema["function"]["name"]
            for schema in get_tool_schemas()
        }
        self.assertEqual(
            names,
            {
                "search_knowledge_base",
                "list_knowledge_documents",
                "get_request_status",
            },
        )

    def test_get_request_status_returns_seed_record(self):
        result = execute_tool("get_request_status", {"request_id": "REQ-104"})

        self.assertTrue(result["ok"])
        self.assertTrue(result["data"]["found"])
        self.assertEqual(result["data"]["request"]["status"], "Incomplete")
        self.assertEqual(
            result["data"]["request"]["document_issues"],
            ["Address proof is missing"],
        )

    def test_get_request_status_rejects_malformed_id(self):
        result = execute_tool("get_request_status", {"request_id": "104"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "invalid_arguments")

    def test_unknown_tool_is_rejected(self):
        result = execute_tool("delete_everything", {})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "unknown_tool")

    def test_list_documents_reads_synthetic_inventory(self):
        result = execute_tool(
            "list_knowledge_documents",
            {"year": "2026", "company": "Synthetic Wealth Management"},
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["count"], 5)

    @patch("agent.tools.rerank_chunks")
    @patch("agent.tools.retrieve_chunks")
    def test_search_knowledge_base_returns_evidence(
        self,
        retrieve_chunks_mock,
        rerank_chunks_mock,
    ):
        chunk = {
            "text": "Address proof must be issued within 90 days.",
            "source": "account_opening_policy.txt",
            "page_start": None,
            "year": "2026",
            "company": "Synthetic Wealth Management",
            "score": 0.8,
            "rerank_score": 5.2,
        }
        retrieve_chunks_mock.return_value = [chunk]
        rerank_chunks_mock.return_value = [chunk]

        result = execute_tool(
            "search_knowledge_base",
            {"query": "How recent must address proof be?"},
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["evidence"][0]["citation_id"], 1)
        self.assertEqual(result["data"]["evidence"][0]["rerank_score"], 5.2)


if __name__ == "__main__":
    unittest.main()
