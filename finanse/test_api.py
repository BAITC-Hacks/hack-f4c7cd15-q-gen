"""Automated tests for MoneyGraph AML Intelligence FastAPI Backend."""
import unittest
from starlette.testclient import TestClient
from api.app import create_app


class TestAMLAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = create_app()
        cls.client = TestClient(app)

    def test_01_health(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["nodes_loaded"], 2248)
        self.assertEqual(data["edges_loaded"], 3119)
        self.assertTrue(data["database_connected"])

    def test_02_stats_overview(self):
        resp = self.client.get("/api/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["nodes"], 2248)
        self.assertEqual(data["edges"], 3119)
        self.assertEqual(data["seeds"], 81)
        self.assertEqual(data["clusters"], 91)
        self.assertEqual(data["truncated"], 444)
        self.assertIn("consolidator", data["roles_distribution"])
        self.assertIn("coordinator", data["roles_distribution"])
        self.assertIn("transit", data["roles_distribution"])
        self.assertGreater(data["top_targets_count"], 20)

    def test_03_nodes_pagination_and_filter(self):
        # Default pagination
        resp = self.client.get("/api/nodes?page=1&page_size=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["items"]), 10)
        self.assertEqual(data["total"], 2248)
        self.assertEqual(data["page"], 1)

        # Filter by role
        resp_cons = self.client.get("/api/nodes?role=consolidator")
        self.assertEqual(resp_cons.status_code, 200)
        data_cons = resp_cons.json()
        self.assertGreater(data_cons["total"], 0)
        for item in data_cons["items"]:
            self.assertEqual(item["role"], "consolidator")

        # Search by GID
        sample_gid = data_cons["items"][0]["gid"]
        resp_search = self.client.get(f"/api/nodes?query={sample_gid[:8]}")
        self.assertEqual(resp_search.status_code, 200)
        self.assertGreater(resp_search.json()["total"], 0)

    def test_04_node_dossier_existing_and_missing(self):
        # Demo consolidator
        gid = "100000003115284100"
        resp = self.client.get(f"/api/nodes/{gid}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["metrics"]["gid"], gid)
        self.assertEqual(data["metrics"]["role"], "consolidator")
        self.assertIn(data["recommended_action"], ["IMMEDIATE_BLOCK_AND_LE", "HIGH_ALERT_MONITOR", "ROUTINE_OBSERVATION", "LOW_RISK"])
        self.assertGreater(len(data["incoming_transfers"]), 0)
        self.assertIsNotNone(data["cluster_hypothesis"])

        # Non-existent node
        resp_404 = self.client.get("/api/nodes/999999999999999999")
        self.assertEqual(resp_404.status_code, 404)

    def test_05_counterparties_and_transactions(self):
        gid = "100000003115284100"
        resp_cp = self.client.get(f"/api/nodes/{gid}/counterparties?direction=in")
        self.assertEqual(resp_cp.status_code, 200)
        incoming = resp_cp.json()
        self.assertGreater(len(incoming), 0)
        for cp in incoming:
            self.assertEqual(cp["direction"], "in")

        resp_tx = self.client.get(f"/api/nodes/{gid}/transactions")
        self.assertEqual(resp_tx.status_code, 200)
        self.assertIsInstance(resp_tx.json(), list)

    def test_06_graph_and_subgraph(self):
        # Filtered graph
        resp = self.client.get("/api/graph?min_priority=0.4&limit_nodes=50")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertLessEqual(data["total_nodes"], 50)
        self.assertGreater(data["total_nodes"], 0)

        # Ego subgraph depth 1
        gid = "100000000331309100"
        resp_sub = self.client.get(f"/api/graph/subgraph/{gid}?depth=1")
        self.assertEqual(resp_sub.status_code, 200)
        sub_data = resp_sub.json()
        self.assertGreater(sub_data["total_nodes"], 1)
        self.assertGreater(sub_data["total_edges"], 0)

    def test_07_clusters(self):
        resp = self.client.get("/api/clusters")
        self.assertEqual(resp.status_code, 200)
        clusters = resp.json()
        self.assertEqual(len(clusters), 91)
        self.assertGreater(clusters[0]["sum_kzt_internal"], 0)

        # Single cluster
        resp_c0 = self.client.get("/api/clusters/0")
        self.assertEqual(resp_c0.status_code, 200)
        c0_data = resp_c0.json()
        self.assertEqual(c0_data["cluster"]["cluster_id"], 0)
        self.assertGreater(c0_data["total_members"], 0)

    def test_08_top_targets_and_demo(self):
        resp = self.client.get("/api/top-targets?limit=25")
        self.assertEqual(resp.status_code, 200)
        targets = resp.json()
        self.assertEqual(len(targets), 25)
        self.assertEqual(targets[0]["rank"], 1)
        self.assertGreaterEqual(targets[0]["priority_score"], targets[1]["priority_score"])

        resp_demo = self.client.get("/api/demo-cases")
        self.assertEqual(resp_demo.status_code, 200)
        demo = resp_demo.json()
        roles = {d["role"] for d in demo}
        self.assertTrue({"consolidator", "transit", "coordinator"}.issubset(roles))

    def test_09_trace(self):
        # Trace from seed to any high-priority target
        seed_gid = "100000003115284100"
        resp = self.client.get(f"/api/trace?source_gid={seed_gid}&max_hops=3")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["source_gid"], seed_gid)
        self.assertIsInstance(data["routes"], list)

    def test_10_file_downloads(self):
        for filename in ("nodes_roles.csv", "clusters.csv", "top_nodes.csv", "temporal_matches.csv"):
            resp = self.client.get(f"/download/{filename}")
            self.assertEqual(resp.status_code, 200, f"Failed to download {filename}")
            self.assertGreater(len(resp.content), 100)

    def test_11_legacy_endpoints(self):
        resp = self.client.get("/api/analytics")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("summary", resp.json())

        resp_ex = self.client.get("/api/route-example")
        self.assertEqual(resp_ex.status_code, 200)
        self.assertIn("source", resp_ex.json())

    def test_12_cors_headers(self):
        resp = self.client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(resp.headers.get("access-control-allow-origin"), ["*", "http://localhost:5173"])
        self.assertIn("x-process-time-ms", resp.headers)


if __name__ == "__main__":
    unittest.main()
