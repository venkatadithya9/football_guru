"""Data synchronization and aggregation engine for Football MCP.

Coordinates between RateLimitedApiClient and FootballDatabase to:
1. Sync and cache league standings & register teams.
2. Sync and cache team statistics (fixtures, goals, clean sheets, form).
3. Sync and aggregate player statistics (top scorers, assists, team rosters).
4. Enforce season freezing: if a season is completed (< 2024), never call external API.
5. Ingest fixture player statistics incrementally into season aggregates.
"""

import logging
from typing import Any, Dict, List, Optional, Union

from football_mcp.api_client import RateLimitedApiClient
from football_mcp.config import (
    SIMULATED_CURRENT_SEASON,
    TOP_5_LEAGUES,
    LeagueInfo,
    resolve_league,
)
from football_mcp.database import FootballDatabase

logger = logging.getLogger("football_mcp.sync_service")


class SyncService:
    """Orchestrates syncing, caching, and aggregating football resources."""

    def __init__(
        self,
        db: Optional[FootballDatabase] = None,
        api_client: Optional[RateLimitedApiClient] = None,
    ):
        self.db = db or FootballDatabase()
        self.api_client = api_client or RateLimitedApiClient(db=self.db)
        self._ensure_leagues_registered()

    def _ensure_leagues_registered(self) -> None:
        """Ensure top 5 leagues are registered in the database."""
        for league in TOP_5_LEAGUES.values():
            self.db.upsert_league(
                league_id=league.id,
                key=league.key,
                name=league.name,
                country=league.country,
                code=league.code,
                logo=f"https://media.api-sports.io/football/leagues/{league.id}.png",
            )

    # ----------------- STANDINGS SYNC -----------------

    def sync_standings(
        self,
        league_identifier: Union[int, str],
        season: int = SIMULATED_CURRENT_SEASON,
        force: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Sync standings from API into DB and return the standings table.

        If season is completed and already in DB (and not force), returns cached data directly (0 API calls).
        """
        league = resolve_league(league_identifier)
        if not league:
            raise ValueError(f"Unknown league identifier: {league_identifier}")

        # Check if already cached
        cached = self.db.get_standings(league.id, season)
        if cached and not force:
            logger.info(f"⚡ [CACHE HIT] Standings for {league.name} ({season}) loaded from local SQLite (0 API calls)")
            return cached

        # Otherwise fetch from API
        logger.info(f"🔄 [CACHE REFRESH] Fetching standings from API-Football for {league.name} ({season})...")
        response_data = self.api_client.get_standings(league.id, season)
        if not response_data:
            logger.warning(f"No standings returned from API for {league.name} ({season}).")
            return cached

        # Parse response
        league_obj = response_data[0].get("league", {})
        standings_groups = league_obj.get("standings", [])
        if not standings_groups:
            return cached

        # API-Football returns list of groups (for regular league, standings[0] is the table)
        table = standings_groups[0]
        parsed_rows = []

        for row in table:
            team_info = row.get("team", {})
            team_id = team_info.get("id")
            team_name = team_info.get("name", "Unknown")
            team_logo = team_info.get("logo")

            # Register team
            self.db.upsert_team(team_id=team_id, league_id=league.id, name=team_name, code=None, logo=team_logo)

            all_stats = row.get("all", {})
            goals_stats = all_stats.get("goals", {})

            parsed_rows.append({
                "rank": row.get("rank"),
                "team_id": team_id,
                "team_name": team_name,
                "points": row.get("points", 0),
                "played": all_stats.get("played", 0),
                "win": all_stats.get("win", 0),
                "draw": all_stats.get("draw", 0),
                "lose": all_stats.get("lose", 0),
                "goals_for": goals_stats.get("for", 0),
                "goals_against": goals_stats.get("against", 0),
                "goals_diff": row.get("goalsDiff", 0),
                "form": row.get("form", ""),
                "status": row.get("status", ""),
                "description": row.get("description", ""),
            })

        self.db.save_standings(league.id, season, parsed_rows)
        return self.db.get_standings(league.id, season)

    # ----------------- TEAM STATISTICS SYNC -----------------

    def sync_team_statistics(
        self,
        league_identifier: Union[int, str],
        team_id: int,
        season: int = SIMULATED_CURRENT_SEASON,
        force: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Sync comprehensive statistics for a team.
        """
        league = resolve_league(league_identifier)
        if not league:
            raise ValueError(f"Unknown league identifier: {league_identifier}")

        cached = self.db.get_team_statistics(team_id, season, league_id=league.id)
        if cached and not force:
            if season < SIMULATED_CURRENT_SEASON or self.db.is_season_completed(league.id, season):
                return cached
            return cached

        logger.info(f"Fetching team statistics from API for team {team_id} ({league.name}, {season})...")
        data = self.api_client.get_team_statistics(league.id, team_id, season)
        if not data:
            return cached

        team_info = data.get("team", {})
        team_name = team_info.get("name", "Unknown")
        fixtures_data = data.get("fixtures", {})
        played = fixtures_data.get("played", {}).get("total", 0)
        wins = fixtures_data.get("wins", {}).get("total", 0)
        draws = fixtures_data.get("draws", {}).get("total", 0)
        loses = fixtures_data.get("loses", {}).get("total", 0)

        goals_data = data.get("goals", {})
        goals_for = goals_data.get("for", {}).get("total", {}).get("total", 0)
        goals_against = goals_data.get("against", {}).get("total", {}).get("total", 0)

        clean_sheets = data.get("clean_sheet", {}).get("total", 0)
        failed_to_score = data.get("failed_to_score", {}).get("total", 0)
        form = data.get("form", "")

        self.db.save_team_statistics(
            team_id=team_id,
            league_id=league.id,
            season=season,
            team_name=team_name,
            fixtures_played=played,
            wins=wins,
            draws=draws,
            loses=loses,
            goals_for=goals_for,
            goals_against=goals_against,
            clean_sheets=clean_sheets,
            failed_to_score=failed_to_score,
            form=form,
            raw_json=data,
        )

        return self.db.get_team_statistics(team_id, season, league_id=league.id)

    # ----------------- PLAYER STATISTICS SYNC -----------------

    def sync_player_leaders(
        self,
        league_identifier: Union[int, str],
        season: int = SIMULATED_CURRENT_SEASON,
        force: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Sync top scorers and top assists for a league in just 2 API calls.
        Aggregates the top performers into the player_statistics table.
        """
        league = resolve_league(league_identifier)
        if not league:
            raise ValueError(f"Unknown league identifier: {league_identifier}")

        cached_leaders = self.db.get_league_players_leaderboard(league.id, season, sort_by="goals", limit=20)
        if cached_leaders and not force:
            if season < SIMULATED_CURRENT_SEASON or self.db.is_season_completed(league.id, season):
                return cached_leaders
            return cached_leaders

        records: List[Dict[str, Any]] = []

        # 1. Fetch Top Scorers (1 API Call)
        logger.info(f"Fetching top scorers for {league.name} ({season})...")
        top_scorers_resp = self.api_client.get_top_scorers(league.id, season)
        for item in top_scorers_resp:
            parsed = self._parse_player_api_item(item, league.id, season)
            if parsed:
                records.append(parsed)

        # 2. Fetch Top Assists (1 API Call)
        logger.info(f"Fetching top assists for {league.name} ({season})...")
        top_assists_resp = self.api_client.get_top_assists(league.id, season)
        for item in top_assists_resp:
            parsed = self._parse_player_api_item(item, league.id, season)
            if parsed:
                records.append(parsed)

        if records:
            self.db.save_player_statistics_batch(records)

        return self.db.get_league_players_leaderboard(league.id, season, sort_by="goals", limit=20)

    def sync_team_roster_players(
        self,
        league_identifier: Union[int, str],
        team_id: int,
        season: int = SIMULATED_CURRENT_SEASON,
        force: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Sync all players for a specific team roster (1 API call).
        """
        league = resolve_league(league_identifier)
        if not league:
            raise ValueError(f"Unknown league identifier: {league_identifier}")

        cached = self.db.get_team_players(team_id, season)
        if cached and not force:
            return cached

        logger.info(f"Fetching squad player stats for team {team_id} ({season})...")
        players_resp = self.api_client.get_team_players(team_id, season)
        records = []
        for item in players_resp:
            parsed = self._parse_player_api_item(item, league.id, season)
            if parsed:
                records.append(parsed)

        if records:
            self.db.save_player_statistics_batch(records)

        return self.db.get_team_players(team_id, season)

    def aggregate_fixture_players(
        self,
        fixture_players_data: List[Dict[str, Any]],
        league_id: int,
        season: int = SIMULATED_CURRENT_SEASON,
    ) -> int:
        """
        Ingest fixture-level player stats (from fixtures/players?fixture=ID) and update season totals.
        """
        records_updated = 0
        for team_block in fixture_players_data:
            team_info = team_block.get("team", {})
            team_id = team_info.get("id")
            team_name = team_info.get("name", "Unknown")

            for p_item in team_block.get("players", []):
                p_info = p_item.get("player", {})
                player_id = p_info.get("id")
                player_name = p_info.get("name", "Unknown")

                stats_list = p_item.get("statistics", [])
                if not stats_list:
                    continue
                stat = stats_list[0]

                games = stat.get("games", {})
                goals_stat = stat.get("goals", {})
                passes = stat.get("passes", {})
                tackles = stat.get("tackles", {})
                cards = stat.get("cards", {})

                # Construct player record
                rec = {
                    "player_id": player_id,
                    "player_name": player_name,
                    "team_id": team_id,
                    "team_name": team_name,
                    "league_id": league_id,
                    "season": season,
                    "position": games.get("position"),
                    "rating": float(games.get("rating")) if games.get("rating") else None,
                    "appearances": 1 if games.get("minutes", 0) > 0 else 0,
                    "minutes": games.get("minutes", 0) or 0,
                    "goals": goals_stat.get("total", 0) or 0,
                    "assists": goals_stat.get("assists", 0) or 0,
                    "passes_total": passes.get("total", 0) or 0,
                    "tackles_total": tackles.get("total", 0) or 0,
                    "yellow_cards": cards.get("yellow", 0) or 0,
                    "red_cards": cards.get("red", 0) or 0,
                }
                self.db.save_player_statistics(rec)
                records_updated += 1

        return records_updated

    def _parse_player_api_item(
        self, item: Dict[str, Any], league_id: int, season: int
    ) -> Optional[Dict[str, Any]]:
        """Helper to parse a player item from API-Football into the DB schema."""
        p_info = item.get("player", {})
        player_id = p_info.get("id")
        player_name = p_info.get("name", "Unknown")

        stats_list = item.get("statistics", [])
        if not stats_list:
            return None

        # Pick stats matching the requested league, or default to first
        stat = next((s for s in stats_list if s.get("league", {}).get("id") == league_id), stats_list[0])
        team_info = stat.get("team", {})
        team_id = team_info.get("id")
        team_name = team_info.get("name", "Unknown")

        games = stat.get("games", {})
        goals_data = stat.get("goals", {})
        shots_data = stat.get("shots", {})
        passes_data = stat.get("passes", {})
        tackles_data = stat.get("tackles", {})
        duels_data = stat.get("duels", {})
        dribbles_data = stat.get("dribbles", {})
        cards_data = stat.get("cards", {})
        penalties_data = stat.get("penalty", {})

        rating_val = games.get("rating")
        parsed_rating = None
        if rating_val is not None:
            try:
                parsed_rating = round(float(rating_val), 2)
            except (ValueError, TypeError):
                parsed_rating = None

        return {
            "player_id": player_id,
            "player_name": player_name,
            "team_id": team_id,
            "team_name": team_name,
            "league_id": league_id,
            "season": season,
            "position": games.get("position"),
            "rating": parsed_rating,
            "appearances": games.get("appearences", 0) or 0,
            "lineups": games.get("lineups", 0) or 0,
            "minutes": games.get("minutes", 0) or 0,
            "goals": goals_data.get("total", 0) or 0,
            "assists": goals_data.get("assists", 0) or 0,
            "shots_total": shots_data.get("total", 0) or 0,
            "shots_on": shots_data.get("on", 0) or 0,
            "passes_total": passes_data.get("total", 0) or 0,
            "passes_accuracy": float(passes_data.get("accuracy", 0) or 0),
            "tackles_total": tackles_data.get("total", 0) or 0,
            "duels_total": duels_data.get("total", 0) or 0,
            "duels_won": duels_data.get("won", 0) or 0,
            "dribbles_success": dribbles_data.get("success", 0) or 0,
            "yellow_cards": cards_data.get("yellow", 0) or 0,
            "red_cards": cards_data.get("red", 0) or 0,
            "penalties_scored": penalties_data.get("scored", 0) or 0,
        }
