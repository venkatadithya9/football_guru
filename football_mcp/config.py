"""Configuration and constants for the Football MCP server."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union
from dotenv import load_dotenv

# Load .env if present
load_dotenv(override=True)

# Base Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "football_mcp.db"
DB_PATH = Path(os.getenv("FOOTBALL_DB_PATH", str(DEFAULT_DB_PATH)))

# API Configuration
API_BASE_URL = "https://v3.football.api-sports.io"
DEFAULT_API_KEY = "cf468a50a5fd7777cee6b49e9b382d4f"
API_KEY = os.getenv("API_FOOTBALL_KEY") or os.getenv("FOOTBALL_API_KEY") or DEFAULT_API_KEY

# Rate Limits (Free Plan constraints)
MAX_REQUESTS_PER_DAY = 100
MAX_REQUESTS_PER_MINUTE = 10
MIN_SECONDS_BETWEEN_REQUESTS = 6.2  # 10 req/min = 1 req per 6s; 6.2s adds safety buffer
DAILY_QUOTA_SAFETY_THRESHOLD = 5    # Block non-essential requests when remaining <= 5

# Season Constants
# Note: Calendar year is 2026, but the free tier only provides data up to 2024.
# 2024 is treated as the simulated current season for learning and analytics.
SIMULATED_CURRENT_SEASON = 2024
REAL_CURRENT_SEASON = 2026
SUPPORTED_HISTORICAL_SEASONS = [2021, 2022, 2023, 2024]


@dataclass(frozen=True)
class LeagueInfo:
    id: int
    key: str
    name: str
    country: str
    code: str
    aliases: List[str]


# Top 5 European Leagues
TOP_5_LEAGUES: Dict[int, LeagueInfo] = {
    39: LeagueInfo(
        id=39,
        key="pl",
        name="Premier League",
        country="England",
        code="GB-ENG",
        aliases=["premier league", "epl", "premierleague", "pl", "england 1", "39"],
    ),
    140: LeagueInfo(
        id=140,
        key="laliga",
        name="La Liga",
        country="Spain",
        code="ES",
        aliases=["la liga", "laliga", "primera division", "primera", "spain 1", "140"],
    ),
    78: LeagueInfo(
        id=78,
        key="bundesliga",
        name="Bundesliga",
        country="Germany",
        code="DE",
        aliases=["bundesliga", "buli", "germany 1", "78"],
    ),
    135: LeagueInfo(
        id=135,
        key="serie_a",
        name="Serie A",
        country="Italy",
        code="IT",
        aliases=["serie a", "serie_a", "seria", "italy 1", "135"],
    ),
    61: LeagueInfo(
        id=61,
        key="ligue1",
        name="Ligue 1",
        country="France",
        code="FR",
        aliases=["ligue 1", "ligue_1", "ligue1", "france 1", "61"],
    ),
}

# Lookup maps for fast resolution
_KEY_MAP: Dict[str, LeagueInfo] = {league.key: league for league in TOP_5_LEAGUES.values()}
_ALIAS_MAP: Dict[str, LeagueInfo] = {}
for league in TOP_5_LEAGUES.values():
    _ALIAS_MAP[str(league.id)] = league
    _ALIAS_MAP[league.key.lower()] = league
    for alias in league.aliases:
        _ALIAS_MAP[alias.lower().strip()] = league


def resolve_league(identifier: Union[int, str]) -> Optional[LeagueInfo]:
    """
    Resolve a league by ID, key, or common alias.

    Args:
        identifier: League ID (e.g. 39), key ('pl'), or alias ('premier league', 'seria')

    Returns:
        LeagueInfo if matched, None otherwise.
    """
    if isinstance(identifier, int):
        return TOP_5_LEAGUES.get(identifier)

    cleaned = str(identifier).strip().lower()
    if cleaned.isdigit():
        return TOP_5_LEAGUES.get(int(cleaned))

    return _ALIAS_MAP.get(cleaned)


def get_all_league_ids() -> List[int]:
    """Get list of league IDs for the top 5 European leagues."""
    return list(TOP_5_LEAGUES.keys())


def get_live_league_ids_param() -> str:
    """Returns dash-separated league IDs string for live fixtures endpoint query."""
    return "-".join(str(lid) for lid in TOP_5_LEAGUES.keys())
