"""Unit tests for FastMCP server tools and resources."""

import asyncio
import json
import unittest
from unittest.mock import patch

from football_mcp.server import mcp, db


class TestFastMCPServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Prepopulate database with dummy data for PL 2024 so resource reads return valid data
        cls.standings = [
            {
                "rank": 1,
                "team_id": 42,
                "team_name": "Arsenal",
                "points": 89,
                "played": 38,
                "win": 28,
                "draw": 5,
                "lose": 5,
                "goals_for": 91,
                "goals_against": 29,
                "goals_diff": 62,
                "form": "WWWWW",
                "status": "same",
                "description": "Champions League",
            },
            {
                "rank": 2,
                "team_id": 50,
                "team_name": "Manchester City",
                "points": 88,
                "played": 38,
                "win": 27,
                "draw": 7,
                "lose": 4,
                "goals_for": 96,
                "goals_against": 34,
                "goals_diff": 62,
                "form": "WWWDW",
                "status": "same",
                "description": "Champions League",
            },
        ]
        db.save_standings(39, 2024, cls.standings)
        db.save_player_statistics({
            "player_id": 1100,
            "player_name": "Erling Haaland",
            "team_id": 50,
            "team_name": "Manchester City",
            "league_id": 39,
            "season": 2024,
            "position": "Attacker",
            "rating": 7.6,
            "appearances": 31,
            "minutes": 2550,
            "goals": 27,
            "assists": 5,
        })

    def test_list_resource_templates(self):
        async def _test():
            templates = await mcp.list_resource_templates()
            uris = [t.uri_template for t in templates]
            self.assertIn("football://standings/{league}/{season}", uris)
            self.assertIn("football://teams/{league}/{season}", uris)
            self.assertIn("football://teams/{team_id}/statistics/{season}", uris)
            self.assertIn("football://players/{league}/{season}", uris)
            self.assertIn("football://seasons/summary/{season}", uris)

        asyncio.run(_test())

    def test_read_quota_resource(self):
        async def _test():
            content = await mcp.read_resource("football://status/quota")
            self.assertTrue(len(content.contents) > 0)
            data = json.loads(content.contents[0].content)
            self.assertIn("requests_made_today", data)
            self.assertIn("max_daily_quota", data)

        asyncio.run(_test())

    def test_read_standings_resource(self):
        async def _test():
            content = await mcp.read_resource("football://standings/pl/2024")
            self.assertTrue(len(content.contents) > 0)
            data = json.loads(content.contents[0].content)
            self.assertEqual(data["league"], "Premier League")
            self.assertEqual(data["season"], 2024)
            self.assertEqual(len(data["standings"]), 2)
            self.assertEqual(data["standings"][0]["team"], "Arsenal")

        asyncio.run(_test())

    def test_read_players_resource(self):
        async def _test():
            content = await mcp.read_resource("football://players/pl/2024")
            self.assertTrue(len(content.contents) > 0)
            data = json.loads(content.contents[0].content)
            self.assertEqual(data["league"], "Premier League")
            self.assertIn("top_scorers", data)
            self.assertEqual(data["top_scorers"][0]["player_name"], "Erling Haaland")

        asyncio.run(_test())

    def test_list_tools(self):
        async def _test():
            tools = await mcp.list_tools()
            tool_names = [t.name for t in tools]
            self.assertIn("get_live_scores", tool_names)
            self.assertIn("get_fixtures_by_date", tool_names)
            self.assertIn("get_league_standings", tool_names)
            self.assertIn("get_team_statistics", tool_names)
            self.assertIn("get_player_statistics", tool_names)
            self.assertIn("sync_league_data", tool_names)
            self.assertIn("check_api_quota", tool_names)

        asyncio.run(_test())

    def test_call_tool_standings(self):
        async def _test():
            res = await mcp.call_tool("get_league_standings", {"league": "pl", "season": 2024})
            self.assertTrue(len(res.content) > 0)
            text = res.content[0].text
            self.assertIn("Premier League Standings", text)
            self.assertIn("Arsenal", text)
            self.assertIn("Manchester City", text)

        asyncio.run(_test())

    def test_call_tool_check_quota(self):
        async def _test():
            res = await mcp.call_tool("check_api_quota", {})
            self.assertTrue(len(res.content) > 0)
            text = res.content[0].text
            self.assertIn("API-Football Quota Status", text)

        asyncio.run(_test())

    @patch("football_mcp.api_client.RateLimitedApiClient.get_live_fixtures")
    def test_call_tool_live_scores(self, mock_live):
        mock_live.return_value = [
            {
                "fixture": {"status": {"elapsed": 42, "short": "1H"}},
                "league": {"name": "Premier League"},
                "teams": {"home": {"name": "Arsenal"}, "away": {"name": "Chelsea"}},
                "goals": {"home": 2, "away": 1},
            }
        ]

        async def _test():
            res = await mcp.call_tool("get_live_scores", {"leagues": ["pl"]})
            self.assertTrue(len(res.content) > 0)
            text = res.content[0].text
            self.assertIn("[Premier League] Arsenal 2 - 1 Chelsea (42', 1H)", text)

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
