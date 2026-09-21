"""Database persistence layer using SQLite for Football MCP server.

Maintains cached resources for:
1. League standings (weekly update cadence for current season, frozen for past seasons).
2. Team statistics (updated post-match or on demand, frozen for past seasons).
3. Player statistics (aggregated at league and team level, frozen for past seasons).
4. Season completion metadata.
5. API request logging for strict rate limit & quota tracking.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from football_mcp.config import DB_PATH, SIMULATED_CURRENT_SEASON


class FootballDatabase:
    """SQLite database manager for football resources and API logs."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=20.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_schema(self) -> None:
        """Initialize tables and indexes if they do not exist."""
        with self._get_connection() as conn:
            conn.executescript("""
            -- Leagues Table
            CREATE TABLE IF NOT EXISTS leagues (
                id INTEGER PRIMARY KEY,
                key TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                country TEXT NOT NULL,
                code TEXT,
                logo TEXT
            );

            -- Teams Table
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY,
                league_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                code TEXT,
                logo TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (league_id) REFERENCES leagues(id)
            );

            -- Standings Table
            CREATE TABLE IF NOT EXISTS standings (
                league_id INTEGER NOT NULL,
                season INTEGER NOT NULL,
                rank INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                team_name TEXT NOT NULL,
                points INTEGER NOT NULL,
                played INTEGER NOT NULL,
                win INTEGER NOT NULL,
                draw INTEGER NOT NULL,
                lose INTEGER NOT NULL,
                goals_for INTEGER NOT NULL,
                goals_against INTEGER NOT NULL,
                goals_diff INTEGER NOT NULL,
                form TEXT,
                status TEXT,
                description TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (league_id, season, team_id),
                FOREIGN KEY (league_id) REFERENCES leagues(id)
            );

            -- Team Statistics Table
            CREATE TABLE IF NOT EXISTS team_statistics (
                team_id INTEGER NOT NULL,
                league_id INTEGER NOT NULL,
                season INTEGER NOT NULL,
                team_name TEXT NOT NULL,
                fixtures_played INTEGER NOT NULL,
                wins INTEGER NOT NULL,
                draws INTEGER NOT NULL,
                loses INTEGER NOT NULL,
                goals_for INTEGER NOT NULL,
                goals_against INTEGER NOT NULL,
                clean_sheets INTEGER NOT NULL,
                failed_to_score INTEGER NOT NULL,
                form TEXT,
                raw_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (team_id, league_id, season),
                FOREIGN KEY (league_id) REFERENCES leagues(id)
            );

            -- Player Statistics Table (Aggregated at player, team, league, season)
            CREATE TABLE IF NOT EXISTS player_statistics (
                player_id INTEGER NOT NULL,
                player_name TEXT NOT NULL,
                team_id INTEGER NOT NULL,
                team_name TEXT NOT NULL,
                league_id INTEGER NOT NULL,
                season INTEGER NOT NULL,
                position TEXT,
                rating REAL,
                appearances INTEGER DEFAULT 0,
                lineups INTEGER DEFAULT 0,
                minutes INTEGER DEFAULT 0,
                goals INTEGER DEFAULT 0,
                assists INTEGER DEFAULT 0,
                shots_total INTEGER DEFAULT 0,
                shots_on INTEGER DEFAULT 0,
                passes_total INTEGER DEFAULT 0,
                passes_accuracy REAL DEFAULT 0,
                tackles_total INTEGER DEFAULT 0,
                duels_total INTEGER DEFAULT 0,
                duels_won INTEGER DEFAULT 0,
                dribbles_success INTEGER DEFAULT 0,
                yellow_cards INTEGER DEFAULT 0,
                red_cards INTEGER DEFAULT 0,
                penalties_scored INTEGER DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (player_id, team_id, league_id, season),
                FOREIGN KEY (league_id) REFERENCES leagues(id)
            );

            -- Season Metadata Table
            CREATE TABLE IF NOT EXISTS season_metadata (
                league_id INTEGER NOT NULL,
                season INTEGER NOT NULL,
                is_completed INTEGER NOT NULL DEFAULT 0, -- 1 for seasons < 2024
                last_standings_sync TEXT,
                last_stats_sync TEXT,
                last_players_sync TEXT,
                PRIMARY KEY (league_id, season),
                FOREIGN KEY (league_id) REFERENCES leagues(id)
            );

            -- API Request Audit Log (Tracks daily & minute quota usage)
            CREATE TABLE IF NOT EXISTS api_request_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                requests_remaining INTEGER,
                response_time_ms REAL
            );

            -- Indexes for fast resource reads
            CREATE INDEX IF NOT EXISTS idx_standings_lookup 
                ON standings (league_id, season, rank);

            CREATE INDEX IF NOT EXISTS idx_team_stats_lookup 
                ON team_statistics (team_id, season);

            CREATE INDEX IF NOT EXISTS idx_player_stats_league_season 
                ON player_statistics (league_id, season, goals DESC);

            CREATE INDEX IF NOT EXISTS idx_player_stats_team 
                ON player_statistics (team_id, season);

            CREATE INDEX IF NOT EXISTS idx_api_log_timestamp 
                ON api_request_log (timestamp);
            """)

    # ----------------- LEAGUES & TEAMS -----------------

    def upsert_league(self, league_id: int, key: str, name: str, country: str, code: Optional[str], logo: Optional[str]) -> None:
        """Upsert a league record."""
        with self._get_connection() as conn:
            conn.execute("""
            INSERT INTO leagues (id, key, name, country, code, logo)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                key = excluded.key,
                name = excluded.name,
                country = excluded.country,
                code = excluded.code,
                logo = excluded.logo
            """, (league_id, key, name, country, code, logo))

    def upsert_team(self, team_id: int, league_id: int, name: str, code: Optional[str], logo: Optional[str]) -> None:
        """Upsert a team record."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
            INSERT INTO teams (id, league_id, name, code, logo, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                league_id = excluded.league_id,
                name = excluded.name,
                code = excluded.code,
                logo = excluded.logo,
                updated_at = excluded.updated_at
            """, (team_id, league_id, name, code, logo, now))

    def get_teams_by_league(self, league_id: int) -> List[Dict[str, Any]]:
        """Retrieve all teams registered for a league."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM teams WHERE league_id = ? ORDER BY name ASC",
                (league_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ----------------- STANDINGS -----------------

    def save_standings(self, league_id: int, season: int, standings_rows: List[Dict[str, Any]]) -> None:
        """
        Save or replace standings for a given league and season.

        Args:
            league_id: ID of the competition
            season: Season year (e.g. 2024)
            standings_rows: List of dicts with rank, team info, points, form, etc.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            with conn:
                for row in standings_rows:
                    conn.execute("""
                    INSERT INTO standings (
                        league_id, season, rank, team_id, team_name, points,
                        played, win, draw, lose, goals_for, goals_against,
                        goals_diff, form, status, description, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(league_id, season, team_id) DO UPDATE SET
                        rank = excluded.rank,
                        team_name = excluded.team_name,
                        points = excluded.points,
                        played = excluded.played,
                        win = excluded.win,
                        draw = excluded.draw,
                        lose = excluded.lose,
                        goals_for = excluded.goals_for,
                        goals_against = excluded.goals_against,
                        goals_diff = excluded.goals_diff,
                        form = excluded.form,
                        status = excluded.status,
                        description = excluded.description,
                        updated_at = excluded.updated_at
                    """, (
                        league_id,
                        season,
                        row["rank"],
                        row["team_id"],
                        row["team_name"],
                        row["points"],
                        row["played"],
                        row["win"],
                        row["draw"],
                        row["lose"],
                        row["goals_for"],
                        row["goals_against"],
                        row["goals_diff"],
                        row.get("form", ""),
                        row.get("status", ""),
                        row.get("description", ""),
                        now
                    ))

                # Update season metadata
                is_completed = 1 if season < SIMULATED_CURRENT_SEASON else 0
                conn.execute("""
                INSERT INTO season_metadata (league_id, season, is_completed, last_standings_sync)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(league_id, season) DO UPDATE SET
                    last_standings_sync = excluded.last_standings_sync,
                    is_completed = CASE WHEN excluded.is_completed = 1 THEN 1 ELSE is_completed END
                """, (league_id, season, is_completed, now))

    def get_standings(self, league_id: int, season: int) -> List[Dict[str, Any]]:
        """Retrieve standings table sorted by rank."""
        with self._get_connection() as conn:
            rows = conn.execute("""
            SELECT * FROM standings
            WHERE league_id = ? AND season = ?
            ORDER BY rank ASC
            """, (league_id, season)).fetchall()
            return [dict(r) for r in rows]

    # ----------------- TEAM STATISTICS -----------------

    def save_team_statistics(
        self,
        team_id: int,
        league_id: int,
        season: int,
        team_name: str,
        fixtures_played: int,
        wins: int,
        draws: int,
        loses: int,
        goals_for: int,
        goals_against: int,
        clean_sheets: int,
        failed_to_score: int,
        form: str,
        raw_json: Dict[str, Any]
    ) -> None:
        """Save detailed team statistics."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
            INSERT INTO team_statistics (
                team_id, league_id, season, team_name, fixtures_played,
                wins, draws, loses, goals_for, goals_against,
                clean_sheets, failed_to_score, form, raw_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(team_id, league_id, season) DO UPDATE SET
                team_name = excluded.team_name,
                fixtures_played = excluded.fixtures_played,
                wins = excluded.wins,
                draws = excluded.draws,
                loses = excluded.loses,
                goals_for = excluded.goals_for,
                goals_against = excluded.goals_against,
                clean_sheets = excluded.clean_sheets,
                failed_to_score = excluded.failed_to_score,
                form = excluded.form,
                raw_json = excluded.raw_json,
                updated_at = excluded.updated_at
            """, (
                team_id, league_id, season, team_name, fixtures_played,
                wins, draws, loses, goals_for, goals_against,
                clean_sheets, failed_to_score, form, json.dumps(raw_json), now
            ))

    def get_team_statistics(self, team_id: int, season: int, league_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Retrieve team statistics by team ID and season."""
        with self._get_connection() as conn:
            if league_id:
                row = conn.execute("""
                SELECT * FROM team_statistics
                WHERE team_id = ? AND season = ? AND league_id = ?
                """, (team_id, season, league_id)).fetchone()
            else:
                row = conn.execute("""
                SELECT * FROM team_statistics
                WHERE team_id = ? AND season = ?
                ORDER BY updated_at DESC LIMIT 1
                """, (team_id, season)).fetchone()

            if not row:
                return None
            res = dict(row)
            if "raw_json" in res and res["raw_json"]:
                try:
                    res["details"] = json.loads(res["raw_json"])
                except Exception:
                    res["details"] = {}
            return res

    def get_league_teams_statistics(self, league_id: int, season: int) -> List[Dict[str, Any]]:
        """Retrieve summary statistics for all teams in a league for a given season."""
        with self._get_connection() as conn:
            rows = conn.execute("""
            SELECT team_id, league_id, season, team_name, fixtures_played,
                   wins, draws, loses, goals_for, goals_against,
                   clean_sheets, failed_to_score, form, updated_at
            FROM team_statistics
            WHERE league_id = ? AND season = ?
            ORDER BY wins DESC, goals_for DESC
            """, (league_id, season)).fetchall()
            return [dict(r) for r in rows]

    # ----------------- PLAYER STATISTICS -----------------

    def save_player_statistics(self, player_record: Dict[str, Any]) -> None:
        """Upsert a single player statistics record."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
            INSERT INTO player_statistics (
                player_id, player_name, team_id, team_name, league_id, season,
                position, rating, appearances, lineups, minutes, goals, assists,
                shots_total, shots_on, passes_total, passes_accuracy,
                tackles_total, duels_total, duels_won, dribbles_success,
                yellow_cards, red_cards, penalties_scored, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(player_id, team_id, league_id, season) DO UPDATE SET
                player_name = excluded.player_name,
                team_name = excluded.team_name,
                position = excluded.position,
                rating = excluded.rating,
                appearances = excluded.appearances,
                lineups = excluded.lineups,
                minutes = excluded.minutes,
                goals = excluded.goals,
                assists = excluded.assists,
                shots_total = excluded.shots_total,
                shots_on = excluded.shots_on,
                passes_total = excluded.passes_total,
                passes_accuracy = excluded.passes_accuracy,
                tackles_total = excluded.tackles_total,
                duels_total = excluded.duels_total,
                duels_won = excluded.duels_won,
                dribbles_success = excluded.dribbles_success,
                yellow_cards = excluded.yellow_cards,
                red_cards = excluded.red_cards,
                penalties_scored = excluded.penalties_scored,
                updated_at = excluded.updated_at
            """, (
                player_record["player_id"],
                player_record["player_name"],
                player_record["team_id"],
                player_record["team_name"],
                player_record["league_id"],
                player_record["season"],
                player_record.get("position"),
                player_record.get("rating"),
                player_record.get("appearances", 0),
                player_record.get("lineups", 0),
                player_record.get("minutes", 0),
                player_record.get("goals", 0),
                player_record.get("assists", 0),
                player_record.get("shots_total", 0),
                player_record.get("shots_on", 0),
                player_record.get("passes_total", 0),
                player_record.get("passes_accuracy", 0.0),
                player_record.get("tackles_total", 0),
                player_record.get("duels_total", 0),
                player_record.get("duels_won", 0),
                player_record.get("dribbles_success", 0),
                player_record.get("yellow_cards", 0),
                player_record.get("red_cards", 0),
                player_record.get("penalties_scored", 0),
                now
            ))

    def save_player_statistics_batch(self, player_records: List[Dict[str, Any]]) -> None:
        """Batch save multiple player statistics records within a single transaction."""
        for record in player_records:
            self.save_player_statistics(record)

    def get_league_players_leaderboard(
        self,
        league_id: int,
        season: int,
        sort_by: str = "goals",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Query league player statistics aggregated at the league level.

        Supported sort_by: 'goals', 'assists', 'rating', 'minutes', 'tackles_total', 'yellow_cards'
        """
        valid_columns = {
            "goals": "goals DESC, assists DESC",
            "assists": "assists DESC, goals DESC",
            "rating": "rating DESC NULLS LAST",
            "minutes": "minutes DESC",
            "tackles": "tackles_total DESC",
            "cards": "yellow_cards DESC, red_cards DESC",
        }
        order_clause = valid_columns.get(sort_by.lower(), "goals DESC")

        with self._get_connection() as conn:
            query = f"""
            SELECT player_id, player_name, team_id, team_name, league_id, season,
                   position, rating, appearances, minutes, goals, assists,
                   shots_total, shots_on, passes_total, passes_accuracy,
                   tackles_total, dribbles_success, yellow_cards, red_cards
            FROM player_statistics
            WHERE league_id = ? AND season = ?
            ORDER BY {order_clause}
            LIMIT ?
            """
            rows = conn.execute(query, (league_id, season, limit)).fetchall()
            return [dict(r) for r in rows]

    def get_team_players(self, team_id: int, season: int) -> List[Dict[str, Any]]:
        """Retrieve all player statistics for a specific team in a season."""
        with self._get_connection() as conn:
            rows = conn.execute("""
            SELECT * FROM player_statistics
            WHERE team_id = ? AND season = ?
            ORDER BY appearances DESC, minutes DESC
            """, (team_id, season)).fetchall()
            return [dict(r) for r in rows]

    # ----------------- SEASON METADATA & FREEZE -----------------

    def is_season_completed(self, league_id: int, season: int) -> bool:
        """Check if season data is marked completed and frozen."""
        if season < SIMULATED_CURRENT_SEASON:
            return True
        with self._get_connection() as conn:
            row = conn.execute("""
            SELECT is_completed FROM season_metadata
            WHERE league_id = ? AND season = ?
            """, (league_id, season)).fetchone()
            return bool(row["is_completed"]) if row else False

    def get_season_metadata(self, league_id: int, season: int) -> Optional[Dict[str, Any]]:
        """Get sync timestamps and completion status for a season."""
        with self._get_connection() as conn:
            row = conn.execute("""
            SELECT * FROM season_metadata
            WHERE league_id = ? AND season = ?
            """, (league_id, season)).fetchone()
            return dict(row) if row else None

    # ----------------- API REQUEST LOG & RATE LIMIT AUDIT -----------------

    def log_api_request(
        self,
        endpoint: str,
        status_code: int,
        requests_remaining: Optional[int] = None,
        response_time_ms: float = 0.0
    ) -> None:
        """Log an external API request for rate-limit and quota tracking."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
            INSERT INTO api_request_log (timestamp, endpoint, status_code, requests_remaining, response_time_ms)
            VALUES (?, ?, ?, ?, ?)
            """, (now, endpoint, status_code, requests_remaining, response_time_ms))

    def get_requests_today_count(self) -> int:
        """Count how many requests have been made today (UTC calendar day)."""
        today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            row = conn.execute("""
            SELECT COUNT(*) as cnt FROM api_request_log
            WHERE timestamp LIKE ?
            """, (f"{today_prefix}%",)).fetchone()
            return row["cnt"] if row else 0

    def get_latest_requests_remaining(self) -> Optional[int]:
        """Get the latest requests_remaining reported by the API-Football server header."""
        with self._get_connection() as conn:
            row = conn.execute("""
            SELECT requests_remaining FROM api_request_log
            WHERE requests_remaining IS NOT NULL
            ORDER BY id DESC LIMIT 1
            """).fetchone()
            return row["requests_remaining"] if row else None
