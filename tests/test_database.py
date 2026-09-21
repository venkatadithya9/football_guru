"""Unit tests for SQLite persistence layer."""

import shutil
import tempfile
import unittest
from pathlib import Path

from football_mcp.database import FootballDatabase


class TestFootballDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_football.db"
        self.db = FootballDatabase(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_upsert_league_and_team(self):
        self.db.upsert_league(39, "pl", "Premier League", "England", "GB-ENG", "https://logo.png")
        self.db.upsert_team(42, 39, "Arsenal", "ARS", "https://arsenal.png")

        teams = self.db.get_teams_by_league(39)
        self.assertEqual(len(teams), 1)
        self.assertEqual(teams[0]["name"], "Arsenal")
        self.assertEqual(teams[0]["code"], "ARS")

    def test_save_and_get_standings(self):
        self.db.upsert_league(39, "pl", "Premier League", "England", "GB-ENG", None)
        standings_rows = [
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
                "description": "Promotion - Champions League",
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
                "description": "Promotion - Champions League",
            },
        ]
        self.db.save_standings(39, 2024, standings_rows)
        retrieved = self.db.get_standings(39, 2024)
        self.assertEqual(len(retrieved), 2)
        self.assertEqual(retrieved[0]["rank"], 1)
        self.assertEqual(retrieved[0]["team_name"], "Arsenal")
        self.assertEqual(retrieved[0]["points"], 89)

    def test_save_and_get_team_statistics(self):
        self.db.upsert_league(39, "pl", "Premier League", "England", "GB-ENG", None)
        raw_stats = {
            "goals": {"for": {"total": {"home": 48, "away": 43, "total": 91}}},
            "clean_sheet": {"total": 18},
        }
        self.db.save_team_statistics(
            team_id=42,
            league_id=39,
            season=2024,
            team_name="Arsenal",
            fixtures_played=38,
            wins=28,
            draws=5,
            loses=5,
            goals_for=91,
            goals_against=29,
            clean_sheets=18,
            failed_to_score=4,
            form="WWWWW",
            raw_json=raw_stats,
        )

        res = self.db.get_team_statistics(42, 2024, league_id=39)
        self.assertIsNotNone(res)
        self.assertEqual(res["team_name"], "Arsenal")
        self.assertEqual(res["clean_sheets"], 18)
        self.assertIn("details", res)
        self.assertEqual(res["details"]["clean_sheet"]["total"], 18)

    def test_player_statistics_and_leaderboard(self):
        self.db.upsert_league(39, "pl", "Premier League", "England", "GB-ENG", None)
        players = [
            {
                "player_id": 101,
                "player_name": "Bukayo Saka",
                "team_id": 42,
                "team_name": "Arsenal",
                "league_id": 39,
                "season": 2024,
                "position": "Attacker",
                "rating": 7.75,
                "appearances": 35,
                "minutes": 2900,
                "goals": 16,
                "assists": 9,
                "shots_total": 85,
                "shots_on": 40,
                "passes_total": 1200,
                "passes_accuracy": 82.5,
                "tackles_total": 45,
                "yellow_cards": 3,
                "red_cards": 0,
            },
            {
                "player_id": 102,
                "player_name": "Erling Haaland",
                "team_id": 50,
                "team_name": "Manchester City",
                "league_id": 39,
                "season": 2024,
                "position": "Attacker",
                "rating": 7.60,
                "appearances": 31,
                "minutes": 2550,
                "goals": 27,
                "assists": 5,
                "shots_total": 110,
                "shots_on": 65,
                "passes_total": 450,
                "passes_accuracy": 74.0,
                "tackles_total": 8,
                "yellow_cards": 1,
                "red_cards": 0,
            },
        ]
        self.db.save_player_statistics_batch(players)

        # Leaderboard by goals
        top_scorers = self.db.get_league_players_leaderboard(39, 2024, sort_by="goals", limit=10)
        self.assertEqual(len(top_scorers), 2)
        self.assertEqual(top_scorers[0]["player_name"], "Erling Haaland")
        self.assertEqual(top_scorers[0]["goals"], 27)

        # Leaderboard by assists
        top_assists = self.db.get_league_players_leaderboard(39, 2024, sort_by="assists", limit=10)
        self.assertEqual(top_assists[0]["player_name"], "Bukayo Saka")
        self.assertEqual(top_assists[0]["assists"], 9)

        # Team players
        arsenal_players = self.db.get_team_players(42, 2024)
        self.assertEqual(len(arsenal_players), 1)
        self.assertEqual(arsenal_players[0]["player_name"], "Bukayo Saka")

    def test_season_freeze_logic(self):
        # Seasons prior to 2024 should be completed automatically
        self.assertTrue(self.db.is_season_completed(39, 2023))
        self.assertTrue(self.db.is_season_completed(39, 2022))

    def test_api_request_log(self):
        self.assertEqual(self.db.get_requests_today_count(), 0)
        self.db.log_api_request("/standings", 200, requests_remaining=96, response_time_ms=120.5)
        self.db.log_api_request("/teams/statistics", 200, requests_remaining=95, response_time_ms=95.0)

        self.assertEqual(self.db.get_requests_today_count(), 2)
        self.assertEqual(self.db.get_latest_requests_remaining(), 95)


if __name__ == "__main__":
    unittest.main()
