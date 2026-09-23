"""Unit & Integration tests for AML Graph Copilot (AI Agent)."""
import json
import unittest
from pathlib import Path

from agent import (
    get_node_info,
    find_common_recipients,
    get_cluster_summary,
    ask_aml_agent,
    AGENT_TOOLS,
)
from starlette.testclient import TestClient
from api.app import create_app


class AMLAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = TestClient(cls.app)

    def test_get_node_info_valid(self):
        # Проверяем известного консолидатора
        raw = get_node_info("100000003115284100")
        data = json.loads(raw)
        self.assertNotIn("error", data)
        self.assertEqual(data["gid"], "100000003115284100")
        self.assertEqual(data["role"], "consolidator")
        self.assertGreater(data["in_volume_kzt"], 0)
        self.assertIn("cluster_id", data)
        self.assertIn("evidence", data)

    def test_get_node_info_invalid(self):
        raw = get_node_info("999999999999999999")
        data = json.loads(raw)
        self.assertIn("error", data)

    def test_find_common_recipients(self):
        raw = find_common_recipients(["100000000331309100", "100000007629096100"])
        data = json.loads(raw)
        self.assertIn("count", data)
        self.assertIn("input_gids", data)
        self.assertIn("common_recipients", data)

    def test_get_cluster_summary(self):
        raw = get_cluster_summary(11)
        data = json.loads(raw)
        self.assertNotIn("error", data)
        self.assertEqual(data["cluster_id"], 11)
        self.assertIn("hypothesis", data)
        self.assertIn("n_nodes", data)
        self.assertIn("sum_kzt_internal", data)

    def test_ask_aml_agent_basic(self):
        q = "Каков финансовый профиль узла 100000003115284100?"
        ans = ask_aml_agent(q)
        self.assertTrue(len(ans) > 50)
        self.assertIn("100000003115284100", ans)
        self.assertIn("consolidator", ans)

    def test_ask_aml_agent_common_recipients(self):
        q = "Кто аккумулирует средства с клиентов 100000000331309100 и 100000007629096100?"
        ans = ask_aml_agent(q)
        self.assertTrue(len(ans) > 50)
        self.assertIn("100000000331309100", ans)

    def test_api_copilot_tools(self):
        res = self.client.get("/api/copilot/tools")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("tools", data)
        self.assertEqual(len(data["tools"]), 3)

    def test_api_copilot_examples(self):
        res = self.client.get("/api/copilot/examples")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("examples", data)
        self.assertGreater(len(data["examples"]), 0)

    def test_api_copilot_ask(self):
        payload = {"query": "Дай сводку по сообществу 11"}
        res = self.client.post("/api/copilot/ask", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("11", data["answer"])


if __name__ == "__main__":
    unittest.main()
