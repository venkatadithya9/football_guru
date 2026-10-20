"""FastMCP server providing Model Context Protocol resources and tools for football data.

Architecture:
1. Resources (Zero external API calls when cached):
   - football://standings/{league}/{season}
   - football://teams/{league}/{season}
   - football://teams/{team_id}/statistics/{season}
   - football://players/{league}/{season}
   - football://players/{team_id}/roster/{season}
   - football://seasons/summary/{season}
   - football://status/quota

2. Tools (Dynamic queries and real-time operations):
   - get_live_scores: Live match scores across top 5 leagues (with 30s cache)
   - get_fixtures_by_date: Query match schedule for a given date
   - get_league_standings: Query league table
   - get_team_statistics: Query specific team metrics
   - get_player_statistics: Query player leaderboards or team rosters
   - sync_league_data: Admin tool to refresh standings/stats with quota guard
   - check_api_quota: Inspect current API usage and rate limits
"""

import json
import logging
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

from football_mcp.api_client import RateLimitedApiClient
from football_mcp.config import (
    REAL_CURRENT_SEASON,
    SIMULATED_CURRENT_SEASON,
    TOP_5_LEAGUES,
    resolve_league,
)
from football_mcp.database import FootballDatabase
from football_mcp.sync_service import SyncService

logger = logging.getLogger("football_mcp.server")

# Initialize FastMCP Server
mcp = FastMCP("FootballDataServer")

# Shared backend instances
db = FootballDatabase()
api_client = RateLimitedApiClient(db=db)
sync_service = SyncService(db=db, api_client=api_client)


# ==============================================================================
# MCP RESOURCES
# ==============================================================================

@mcp.resource("football://status/quota")
def resource_quota_status() -> str:
    """Resource returning current API quota and rate-limit status."""
    logger.info("📦 [RESOURCE READ] football://status/quota")
    status = api_client.get_quota_status()
    return json.dumps(status, indent=2)


@mcp.resource("football://standings/{league}/{season}")
def resource_standings(league: str, season: str) -> str:
    """
    Resource providing the full league standings table.
    Reads from local SQLite database (0 API calls if already cached).
    """
    logger.info(f"📦 [RESOURCE READ] football://standings/{league}/{season}")
    league_info = resolve_league(league)
    if not league_info:
        logger.warning(f"   ↳ Unknown league: {league}")
        return json.dumps({"error": f"Unknown league: {league}. Available: pl, laliga, bundesliga, serie_a, ligue1"})

    try:
        season_int = int(season)
    except ValueError:
        season_int = SIMULATED_CURRENT_SEASON

    standings = sync_service.sync_standings(league_info.id, season_int)
    logger.info(f"   ↳ Returned {len(standings)} teams in standings for {league_info.name} ({season_int})")
    if not standings:
        return json.dumps({
            "league": league_info.name,
            "season": season_int,
            "message": "No standings cached yet. Call sync_league_data to populate.",
            "standings": []
        }, indent=2)

    # Format into markdown-friendly summary + raw table
    formatted = [
        {
            "rank": r["rank"],
            "team": r["team_name"],
            "played": r["played"],
            "won": r["win"],
            "drawn": r["draw"],
            "lost": r["lose"],
            "goals_for": r["goals_for"],
            "goals_against": r["goals_against"],
            "goal_diff": r["goals_diff"],
            "points": r["points"],
            "form": r["form"],
        }
        for r in standings
    ]

    return json.dumps({
        "league": league_info.name,
        "season": season_int,
        "total_teams": len(formatted),
        "standings": formatted,
    }, indent=2)


@mcp.resource("football://teams/{league}/{season}")
def resource_league_teams(league: str, season: str) -> str:
    """
    Resource providing overview of all teams in a league for a given season.
    """
    logger.info(f"📦 [RESOURCE READ] football://teams/{league}/{season}")
    league_info = resolve_league(league)
    if not league_info:
        logger.warning(f"   ↳ Unknown league: {league}")
        return json.dumps({"error": f"Unknown league: {league}"})

    try:
        season_int = int(season)
    except ValueError:
        season_int = SIMULATED_CURRENT_SEASON

    teams_stats = db.get_league_teams_statistics(league_info.id, season_int)
    if not teams_stats:
        # Fallback to team directory
        teams = db.get_teams_by_league(league_info.id)
        logger.info(f"   ↳ Returning directory of {len(teams)} teams for {league_info.name}")
        return json.dumps({
            "league": league_info.name,
            "season": season_int,
            "teams": teams,
        }, indent=2)

    logger.info(f"   ↳ Returning statistics for {len(teams_stats)} teams in {league_info.name} ({season_int})")
    return json.dumps({
        "league": league_info.name,
        "season": season_int,
        "teams_count": len(teams_stats),
        "teams_statistics": teams_stats,
    }, indent=2)


@mcp.resource("football://teams/{team_id}/statistics/{season}")
def resource_team_statistics(team_id: str, season: str) -> str:
    """
    Resource providing comprehensive statistics for a specific team.
    """
    logger.info(f"📦 [RESOURCE READ] football://teams/{team_id}/statistics/{season}")
    try:
        t_id = int(team_id)
        season_int = int(season)
    except ValueError:
        logger.warning(f"   ↳ Invalid team_id ({team_id}) or season ({season})")
        return json.dumps({"error": "Invalid team_id or season format"})

    stats = db.get_team_statistics(t_id, season_int)
    if not stats:
        logger.info(f"   ↳ No cached statistics found for team {t_id} ({season_int})")
        return json.dumps({
            "team_id": t_id,
            "season": season_int,
            "message": "No statistics cached for this team. Use sync_league_data to fetch.",
        }, indent=2)

    logger.info(f"   ↳ Returned statistics for team '{stats.get('team_name', t_id)}' ({season_int})")
    return json.dumps(stats, indent=2)


@mcp.resource("football://players/{league}/{season}")
def resource_league_players(league: str, season: str) -> str:
    """
    Resource providing top player statistics and leaderboards for a league.
    """
    logger.info(f"📦 [RESOURCE READ] football://players/{league}/{season}")
    league_info = resolve_league(league)
    if not league_info:
        logger.warning(f"   ↳ Unknown league: {league}")
        return json.dumps({"error": f"Unknown league: {league}"})

    try:
        season_int = int(season)
    except ValueError:
        season_int = SIMULATED_CURRENT_SEASON

    # Retrieve leaders
    top_scorers = db.get_league_players_leaderboard(league_info.id, season_int, sort_by="goals", limit=15)
    top_assists = db.get_league_players_leaderboard(league_info.id, season_int, sort_by="assists", limit=15)

    if not top_scorers and not top_assists:
        # Attempt sync if not cached
        logger.info(f"   ↳ No cached player leaders for {league_info.name} ({season_int}). Triggering sync...")
        top_scorers = sync_service.sync_player_leaders(league_info.id, season_int)
        top_assists = db.get_league_players_leaderboard(league_info.id, season_int, sort_by="assists", limit=15)

    logger.info(f"   ↳ Returned {len(top_scorers)} scorers and {len(top_assists)} playmakers for {league_info.name}")
    return json.dumps({
        "league": league_info.name,
        "season": season_int,
        "top_scorers": top_scorers,
        "top_assists": top_assists,
    }, indent=2)


@mcp.resource("football://players/{team_id}/roster/{season}")
def resource_team_roster(team_id: str, season: str) -> str:
    """
    Resource providing player statistics for a specific team roster.
    """
    logger.info(f"📦 [RESOURCE READ] football://players/{team_id}/roster/{season}")
    try:
        t_id = int(team_id)
        season_int = int(season)
    except ValueError:
        return json.dumps({"error": "Invalid team_id or season format"})

    roster = db.get_team_players(t_id, season_int)
    logger.info(f"   ↳ Returned {len(roster)} players for team {t_id} ({season_int})")
    return json.dumps({
        "team_id": t_id,
        "season": season_int,
        "player_count": len(roster),
        "players": roster,
    }, indent=2)


@mcp.resource("football://seasons/summary/{season}")
def resource_season_summary(season: str) -> str:
    """
    Resource summarizing the top 5 leagues for a given season.
    """
    logger.info(f"📦 [RESOURCE READ] football://seasons/summary/{season}")
    try:
        season_int = int(season)
    except ValueError:
        season_int = SIMULATED_CURRENT_SEASON

    summary = {}
    for lid, linfo in TOP_5_LEAGUES.items():
        standings = db.get_standings(lid, season_int)
        leaders = db.get_league_players_leaderboard(lid, season_int, sort_by="goals", limit=3)
        summary[linfo.name] = {
            "top_team": standings[0]["team_name"] if standings else "Not Synced",
            "top_scorer": f"{leaders[0]['player_name']} ({leaders[0]['goals']} goals)" if leaders else "Not Synced",
            "teams_tracked": len(standings),
        }

    return json.dumps({
        "season": season_int,
        "is_simulated_current": season_int == SIMULATED_CURRENT_SEASON,
        "leagues": summary,
    }, indent=2)


# ==============================================================================
# MCP TOOLS
# ==============================================================================

@mcp.tool()
def get_live_scores(leagues: Optional[List[str]] = None) -> str:
    """
    Get real-time scores for matches currently in-play across the top 5 European leagues.
    Cached for 30 seconds to prevent unnecessary API calls.

    Args:
        leagues: Optional list of league keys or aliases to filter (e.g. ['pl', 'laliga']).
                 If omitted, checks active matches across all top 5 European leagues.
    """
    logger.info(f"🔧 [TOOL CALL] get_live_scores | leagues={leagues}")
    league_ids: List[int] = []
    if leagues:
        for l in leagues:
            linfo = resolve_league(l)
            if linfo:
                league_ids.append(linfo.id)
    else:
        league_ids = list(TOP_5_LEAGUES.keys())

    try:
        fixtures = api_client.get_live_fixtures(league_ids=league_ids)
        if not fixtures:
            logger.info("   ↳ No live matches currently in progress")
            return "No live matches are currently in progress in the specified leagues."

        output = []
        for f in fixtures:
            fixture_info = f.get("fixture", {})
            league_obj = f.get("league", {})
            teams = f.get("teams", {})
            goals = f.get("goals", {})
            status = fixture_info.get("status", {})

            home_team = teams.get("home", {}).get("name", "Home")
            away_team = teams.get("away", {}).get("name", "Away")
            home_goals = goals.get("home", 0)
            away_goals = goals.get("away", 0)
            elapsed = status.get("elapsed", "0")
            short_status = status.get("short", "")

            output.append(
                f"[{league_obj.get('name', 'League')}] {home_team} {home_goals} - {away_goals} {away_team} "
                f"({elapsed}', {short_status})"
            )

        logger.info(f"   ↳ Returning {len(fixtures)} live matches")
        return "\n".join(output)

    except Exception as e:
        logger.error(f"Error fetching live scores: {e}")
        return f"Error retrieving live scores: {e}"


@mcp.tool()
def get_fixtures_by_date(date: str, league: Optional[str] = None) -> str:
    """
    Get scheduled or completed fixtures for a specific date (YYYY-MM-DD).

    Args:
        date: Target date in format YYYY-MM-DD (e.g. '2026-09-20').
        league: Optional league key or alias (e.g. 'pl', 'laliga').
    """
    logger.info(f"🔧 [TOOL CALL] get_fixtures_by_date | date='{date}', league='{league}'")
    league_id = None
    if league:
        linfo = resolve_league(league)
        if linfo:
            league_id = linfo.id

    try:
        fixtures = api_client.get_fixtures_by_date(date_str=date, league_id=league_id)
        if not fixtures:
            logger.info(f"   ↳ No fixtures found for date: {date}")
            return f"No fixtures found for date: {date}"

        lines = [f"Fixtures for {date}:"]
        for f in fixtures[:30]:  # Limit output length
            league_name = f.get("league", {}).get("name", "League")
            teams = f.get("teams", {})
            goals = f.get("goals", {})
            status = f.get("fixture", {}).get("status", {}).get("short", "NS")
            home = teams.get("home", {}).get("name", "Home")
            away = teams.get("away", {}).get("name", "Away")
            hg = goals.get("home") if goals.get("home") is not None else "-"
            ag = goals.get("away") if goals.get("away") is not None else "-"

            lines.append(f"- [{league_name}] {home} {hg} - {ag} {away} ({status})")

        logger.info(f"   ↳ Returning {len(fixtures)} fixtures for {date}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving fixtures: {e}"


@mcp.tool()
def get_league_standings(league: str, season: int = SIMULATED_CURRENT_SEASON) -> str:
    """
    Get standings table for one of the top 5 European leagues.
    Uses local cache when available.

    Args:
        league: League name, short key or alias (e.g. 'pl', 'laliga', 'bundesliga', 'serie_a', 'ligue1').
        season: Season year (defaults to 2024).
    """
    logger.info(f"🔧 [TOOL CALL] get_league_standings | league='{league}', season={season}")
    linfo = resolve_league(league)
    if not linfo:
        logger.warning(f"   ↳ Unknown league: '{league}'")
        return f"Unknown league '{league}'. Available: pl, laliga, bundesliga, serie_a, ligue1."

    standings = sync_service.sync_standings(linfo.id, season)
    if not standings:
        return f"No standings available for {linfo.name} ({season})."

    header = f"=== {linfo.name} Standings ({season}) ===\n"
    lines = [f"{'Rank':<4} {'Team':<25} {'P':<3} {'W':<3} {'D':<3} {'L':<3} {'GD':<4} {'Pts':<4} {'Form'}"]
    lines.append("-" * 65)

    for r in standings:
        gd = f"{r['goals_diff']:+d}"
        lines.append(
            f"{r['rank']:<4} {r['team_name']:<25} {r['played']:<3} {r['win']:<3} {r['draw']:<3} "
            f"{r['lose']:<3} {gd:<4} {r['points']:<4} {r['form']}"
        )

    logger.info(f"   ↳ Served standings table for {linfo.name} ({len(standings)} clubs)")
    return header + "\n".join(lines)


@mcp.tool()
def get_team_statistics(league: str, team_name_or_id: str, season: int = SIMULATED_CURRENT_SEASON) -> str:
    """
    Get detailed team performance statistics.

    Args:
        league: League identifier ('pl', 'laliga', etc.).
        team_name_or_id: Team name (e.g. 'Arsenal') or team ID.
        season: Season year (default: 2024).
    """
    logger.info(f"🔧 [TOOL CALL] get_team_statistics | league='{league}', team='{team_name_or_id}', season={season}")
    linfo = resolve_league(league)
    if not linfo:
        logger.warning(f"   ↳ Unknown league: '{league}'")
        return f"Unknown league: {league}"

    team_id = None
    if team_name_or_id.isdigit():
        team_id = int(team_name_or_id)
    else:
        # Search by name in DB teams
        teams = db.get_teams_by_league(linfo.id)
        for t in teams:
            if team_name_or_id.lower() in t["name"].lower():
                team_id = t["id"]
                break

    if not team_id:
        logger.warning(f"   ↳ Team '{team_name_or_id}' not found in {linfo.name}")
        return f"Could not find team '{team_name_or_id}' in {linfo.name}. Sync the standings first to register teams."

    stats = sync_service.sync_team_statistics(linfo.id, team_id, season)
    if not stats:
        return f"No statistics found for team {team_name_or_id} ({season})."

    summary = (
        f"=== {stats['team_name']} ({linfo.name} {season}) ===\n"
        f"- Matches Played: {stats['fixtures_played']}\n"
        f"- Record: {stats['wins']} Wins, {stats['draws']} Draws, {stats['loses']} Losses\n"
        f"- Goals: {stats['goals_for']} Scored, {stats['goals_against']} Conceded\n"
        f"- Clean Sheets: {stats['clean_sheets']}\n"
        f"- Failed to Score: {stats['failed_to_score']}\n"
        f"- Form: {stats['form']}\n"
    )
    logger.info(f"   ↳ Returned statistics for team '{stats['team_name']}'")
    return summary


@mcp.tool()
def get_player_statistics(
    league: str,
    season: int = SIMULATED_CURRENT_SEASON,
    metric: str = "goals",
    limit: int = 15,
) -> str:
    """
    Get top player leaderboards for a league.

    Args:
        league: League identifier (e.g. 'pl', 'laliga').
        season: Season year (default: 2024).
        metric: Ranking metric ('goals', 'assists', 'rating', 'tackles', 'cards').
        limit: Max number of players to return (default: 15).
    """
    logger.info(f"🔧 [TOOL CALL] get_player_statistics | league='{league}', season={season}, metric='{metric}', limit={limit}")
    linfo = resolve_league(league)
    if not linfo:
        logger.warning(f"   ↳ Unknown league: '{league}'")
        return f"Unknown league: {league}"

    players = db.get_league_players_leaderboard(linfo.id, season, sort_by=metric, limit=limit)
    if not players:
        # Attempt sync
        logger.info(f"   ↳ Cache empty for {linfo.name} players ({season}). Syncing player leaders...")
        sync_service.sync_player_leaders(linfo.id, season)
        players = db.get_league_players_leaderboard(linfo.id, season, sort_by=metric, limit=limit)

    if not players:
        return f"No player statistics available for {linfo.name} ({season})."

    lines = [f"=== {linfo.name} Player Leaders by {metric.upper()} ({season}) ==="]
    for idx, p in enumerate(players, 1):
        lines.append(
            f"{idx}. {p['player_name']} ({p['team_name']}) - "
            f"Goals: {p['goals']}, Assists: {p['assists']}, Mins: {p['minutes']}, Rating: {p['rating'] or 'N/A'}"
        )

    logger.info(f"   ↳ Returning {len(players)} players ranked by {metric} for {linfo.name}")
    return "\n".join(lines)


@mcp.tool()
def sync_league_data(
    league: str,
    season: int = SIMULATED_CURRENT_SEASON,
    sync_players: bool = True,
    force: bool = False,
) -> str:
    """
    Synchronize data for a league from API-Football into the local SQLite database.
    Guarded by rate limits (10 req/min) and daily quota limits.

    Args:
        league: League identifier ('pl', 'laliga', 'bundesliga', 'serie_a', 'ligue1').
        season: Season year (default: 2024).
        sync_players: Whether to also fetch top scorers & assists (2 API calls).
        force: Force refresh even if cached.
    """
    logger.info(f"🔧 [TOOL CALL] sync_league_data | league='{league}', season={season}, sync_players={sync_players}, force={force}")
    linfo = resolve_league(league)
    if not linfo:
        return f"Unknown league: {league}"

    quota_before = api_client.get_quota_status()
    if not quota_before["can_make_request"] and not force:
        logger.warning(f"   ↳ Sync blocked by quota guard: {quota_before['requests_remaining']} remaining")
        return (
            f"Sync aborted: Only {quota_before['requests_remaining']} requests remaining today. "
            f"Safety limit is {quota_before['safety_threshold']}."
        )

    results = []
    # 1. Sync Standings
    standings = sync_service.sync_standings(linfo.id, season, force=force)
    results.append(f"Standings synced: {len(standings)} teams")

    # 2. Sync Player Leaders
    if sync_players:
        leaders = sync_service.sync_player_leaders(linfo.id, season, force=force)
        results.append(f"Player leaders synced: {len(leaders)} players")

    quota_after = api_client.get_quota_status()
    results.append(f"Remaining daily quota: {quota_after['requests_remaining']}")
    logger.info(f"   ↳ Sync complete: {len(standings)} teams, quota remaining: {quota_after['requests_remaining']}")

    return f"Successfully synced {linfo.name} ({season}):\n" + "\n".join(f"- {r}" for r in results)


@mcp.tool()
def check_api_quota() -> str:
    """
    Check current API-Football quota usage, remaining requests, and rate-limit guard status.
    """
    logger.info("🔧 [TOOL CALL] check_api_quota")
    status = api_client.get_quota_status()
    logger.info(f"   ↳ Quota: {status['requests_remaining']}/{status['max_daily_quota']} remaining (used today: {status['requests_made_today']})")
    return (
        f"=== API-Football Quota Status ===\n"
        f"- Requests Made Today: {status['requests_made_today']}\n"
        f"- Requests Remaining: {status['requests_remaining']} / {status['max_daily_quota']}\n"
        f"- Safety Cutoff Threshold: {status['safety_threshold']}\n"
        f"- Safe to Make Request: {'YES' if status['can_make_request'] else 'NO (Safety Triggered)'}\n"
        f"- Minute Rate Limit: {status['rate_limit_per_minute']} req/min\n"
    )

if __name__ == "__main__":
    mcp.run(transport="http", host="localhost", port=8000)