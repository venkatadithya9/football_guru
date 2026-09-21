"""Unit tests for SyncService."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from football_mcp.api_client import RateLimitedApiClient
from football_mcp.database import FootballDatabase
from football_mcp.sync_service import SyncService


class TestSyncService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_sync.db"
        self.db = FootballDatabase(db_path=self.db_path)
        self.mock_client = MagicMock(spec=RateLimitedApiClient)
        self.mock_client.db = self.db
        self.service = SyncService(db=self.db, api_client=self.mock_client)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sync_standings_and_team_registration(self):
        # Mock API response for standings
        self.mock_client.get_standings.return_value = [
            {
                "league": {
                    "id": 39,
                    "name": "Premier League",
                    "standings": [
                        [
                            {
                                "rank": 1,
                                "team": {"id": 42, "name": "Arsenal", "logo": "https://arsenal.png"},
                                "points": 89,
                                "goalsDiff": 62,
                                "form": "WWWWW",
                                "all": {
                                    "played": 38,
                                    "win": 28,
                                    "draw": 5,
                                    "lose": 5,
                                    "goals": {"for": 91, "against": 29},
                                },
                            },
                            {
                                "rank": 2,
                                "team": {"id": 50, "name": "Manchester City", "logo": "https://city.png"},
                                "points": 88,
                                "goalsDiff": 62,
                                "form": "WWWDW",
                                "all": {
                                    "played": 38,
                                    "win": 27,
                                    "draw": 7,
                                    "lose": 4,
                                    "goals": {"for": 96, "against": 34},
                                },
                            },
                        ]
                    ],
                }
            }
        ]

        # First sync triggers API call
        standings = self.service.sync_standings("pl", 2024)
        self.assertEqual(len(standings), 2)
        self.assertEqual(standings[0]["team_name"], "Arsenal")
        self.assertEqual(self.mock_client.get_standings.call_count, 1)

        # Verify teams were also registered in DB
        teams = self.db.get_teams_by_league(39)
        self.assertEqual(len(teams), 2)

        # Second sync with cached data does NOT trigger API call
        cached = self.service.sync_standings("pl", 2024)
        self.assertEqual(len(cached), 2)
        self.assertEqual(self.mock_client.get_standings.call_count, 1)

    def test_sync_player_leaders(self):
        self.mock_client.get_top_scorers.return_value = [
            {
                "player": {"id": 1100, "name": "Erling Haaland"},
                "statistics": [
                    {
                        "team": {"id": 50, "name": "Manchester City"},
                        "league": {"id": 39},
                        "games": {"appearences": 31, "minutes": 2550, "rating": "7.60"},
                        "goals": {"total": 27, "assists": 5},
                        "shots": {"total": 110, "on": 65},
                        "passes": {"total": 450, "accuracy": 74},
                        "tackles": {"total": 8},
                        "cards": {"yellow": 1, "red": 0},
                    }
                ],
            }
        ]
        self.mock_client.get_top_assists.return_value = [
            {
                "player": {"id": 1200, "name": "Kevin De Bruyne"},
                "statistics": [
                    {
                        "team": {"id": 50, "name": "Manchester City"},
                        "league": {"id": 39},
                        "games": {"appearences": 18, "minutes": 1220, "rating": "7.85"},
                        "goals": {"total": 4, "assists": 10},
                        "shots": {"total": 35, "on": 15},
                        "passes": {"total": 850, "accuracy": 84},
                        "tackles": {"total": 15},
                        "cards": {"yellow": 2, "red": 0},
                    }
                ],
            }
        ]

        leaders = self.service.sync_player_leaders("pl", 2024)
        self.assertEqual(len(leaders), 2)
        self.assertEqual(leaders[0]["player_name"], "Erling Haaland")
        self.assertEqual(leaders[0]["goals"], 27)

        # Leaderboard query by assists
        assist_leaders = self.db.get_league_players_leaderboard(39, 2024, sort_by="assists")
        self.assertEqual(assist_leaders[0]["player_name"], "Kevin De Bruyne")
        self.assertEqual(assist_leaders[0]["assists"], 10)

    def test_aggregate_fixture_players(self):
        fixture_data = [
            {
                "team": {"id": 42, "name": "Arsenal"},
                "players": [
                    {
                        "player": {"id": 19465, "name": "David Raya"},
                        "statistics": [
                            {
                                "games": {"minutes": 90, "position": "G", "rating": "7.5"},
                                "goals": {"total": 0, "assists": 0},
                                "passes": {"total": 35},
                                "tackles": {"total": 0},
                                "cards": {"yellow": 0, "red": 0},
                            }
                        ],
                    }
                ],
            }
        ]
        updated = self.service.aggregate_fixture_players(fixture_data, league_id=39, season=2024)
        self.assertEqual(updated, 1)

        raya_stats = self.db.get_team_players(42, 2024)
        self.assertEqual(len(raya_stats), 1)
        self.assertEqual(raya_stats[0]["player_name"], "David Raya")
        self.assertEqual(raya_stats[0]["minutes"], 90)


if __name__ == "__main__":
    unittest.main()
