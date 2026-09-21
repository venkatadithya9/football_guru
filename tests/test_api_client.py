"""Unit tests for RateLimitedApiClient."""

import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from football_mcp.api_client import QuotaExceededException, RateLimitedApiClient
from football_mcp.database import FootballDatabase


class TestApiClient(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_api_db.db"
        self.db = FootballDatabase(db_path=self.db_path)
        self.client = RateLimitedApiClient(
            api_key="test_dummy_key",
            base_url="https://v3.football.api-sports.io",
            db=self.db,
            safety_threshold=5,
            min_interval_sec=0.1,  # Short interval for fast test execution
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_quota_status_initial(self):
        status = self.client.get_quota_status()
        self.assertEqual(status["requests_made_today"], 0)
        self.assertEqual(status["max_daily_quota"], 100)
        self.assertTrue(status["can_make_request"])

    def test_quota_safety_cutoff(self):
        # Simulate that latest reported remaining requests is 4 (below safety threshold of 5)
        self.db.log_api_request("/test", 200, requests_remaining=4)
        status = self.client.get_quota_status()
        self.assertFalse(status["can_make_request"])

        with self.assertRaises(QuotaExceededException):
            self.client.make_request("standings", params={"league": 39, "season": 2024})

    def test_throttling_interval(self):
        # Test that consecutive requests respect the minimum interval
        self.client.min_interval_sec = 0.2
        t0 = time.time()
        self.client._wait_for_rate_limit()
        t1 = time.time()
        self.client._wait_for_rate_limit()
        t2 = time.time()
        self.assertGreaterEqual(t2 - t1, 0.18)

    @patch("requests.get")
    def test_successful_request_and_audit_logging(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"x-ratelimit-requests-remaining": "88"}
        mock_resp.json.return_value = {"response": [{"league": {"id": 39}}]}
        mock_get.return_value = mock_resp

        res = self.client.make_request("standings", params={"league": 39, "season": 2024})
        self.assertEqual(res["response"][0]["league"]["id"], 39)

        # Verify DB logged the call
        self.assertEqual(self.db.get_requests_today_count(), 1)
        self.assertEqual(self.db.get_latest_requests_remaining(), 88)

    @patch("requests.get")
    def test_live_fixtures_cache(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.json.return_value = {"response": [{"fixture": {"id": 999}}]}
        mock_get.return_value = mock_resp

        # First call hits mock_get
        data1 = self.client.get_live_fixtures()
        self.assertEqual(len(data1), 1)
        self.assertEqual(mock_get.call_count, 1)

        # Second call immediately should be served from memory cache (call_count remains 1)
        data2 = self.client.get_live_fixtures()
        self.assertEqual(len(data2), 1)
        self.assertEqual(mock_get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
