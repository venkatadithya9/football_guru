"""Unit tests for configuration and league resolution."""

import unittest
from football_mcp.config import (
    TOP_5_LEAGUES,
    resolve_league,
    get_all_league_ids,
    get_live_league_ids_param,
    SIMULATED_CURRENT_SEASON,
    REAL_CURRENT_SEASON,
)


class TestConfig(unittest.TestCase):
    def test_top_5_leagues_count(self):
        self.assertEqual(len(TOP_5_LEAGUES), 5)
        self.assertIn(39, TOP_5_LEAGUES)   # PL
        self.assertIn(140, TOP_5_LEAGUES)  # La Liga
        self.assertIn(78, TOP_5_LEAGUES)   # Bundesliga
        self.assertIn(135, TOP_5_LEAGUES)  # Serie A
        self.assertIn(61, TOP_5_LEAGUES)   # Ligue 1

    def test_resolve_league_by_id(self):
        self.assertEqual(resolve_league(39).name, "Premier League")
        self.assertEqual(resolve_league("39").name, "Premier League")
        self.assertEqual(resolve_league(140).name, "La Liga")

    def test_resolve_league_by_key(self):
        self.assertEqual(resolve_league("pl").id, 39)
        self.assertEqual(resolve_league("laliga").id, 140)
        self.assertEqual(resolve_league("bundesliga").id, 78)
        self.assertEqual(resolve_league("serie_a").id, 135)
        self.assertEqual(resolve_league("ligue1").id, 61)

    def test_resolve_league_by_alias(self):
        self.assertEqual(resolve_league("Premier League").id, 39)
        self.assertEqual(resolve_league("epl").id, 39)
        self.assertEqual(resolve_league("seria").id, 135)
        self.assertEqual(resolve_league("buli").id, 78)
        self.assertEqual(resolve_league("la liga").id, 140)
        self.assertIsNone(resolve_league("unknown_league"))

    def test_live_league_param(self):
        param = get_live_league_ids_param()
        for lid in [39, 140, 78, 135, 61]:
            self.assertIn(str(lid), param)

    def test_seasons(self):
        self.assertEqual(SIMULATED_CURRENT_SEASON, 2024)
        self.assertEqual(REAL_CURRENT_SEASON, 2026)


if __name__ == "__main__":
    unittest.main()
