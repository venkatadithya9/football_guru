"""Command-line interface to inspect, run, or sync the Football MCP server."""

import argparse
import sys
from football_mcp.api_client import RateLimitedApiClient
from football_mcp.config import TOP_5_LEAGUES, SIMULATED_CURRENT_SEASON
from football_mcp.database import FootballDatabase
from football_mcp.server import mcp
from football_mcp.sync_service import SyncService


def main():
    parser = argparse.ArgumentParser(description="Football MCP Server CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # 'run' command: start the FastMCP server
    run_parser = subparsers.add_parser("run", help="Start the FastMCP server via stdio")
    run_parser.add_argument("--transport", default="stdio", choices=["stdio", "sse"], help="Transport protocol")

    # 'quota' command: check API quota
    subparsers.add_parser("quota", help="Check current API quota usage")

    # 'sync' command: sync a league
    sync_parser = subparsers.add_parser("sync", help="Synchronize a league to local database")
    sync_parser.add_argument("--league", required=True, help="League key (pl, laliga, bundesliga, serie_a, ligue1)")
    sync_parser.add_argument("--season", type=int, default=SIMULATED_CURRENT_SEASON, help="Season year (default: 2024)")
    sync_parser.add_argument("--no-players", action="store_true", help="Skip syncing top player leaders")
    sync_parser.add_argument("--force", action="store_true", help="Force refresh from API")

    # 'standings' command: display cached standings
    standings_parser = subparsers.add_parser("standings", help="Display cached standings")
    standings_parser.add_argument("--league", required=True, help="League key")
    standings_parser.add_argument("--season", type=int, default=SIMULATED_CURRENT_SEASON, help="Season year")

    args = parser.parse_args()

    db = FootballDatabase()
    api_client = RateLimitedApiClient(db=db)
    sync_service = SyncService(db=db, api_client=api_client)

    if args.command == "run" or args.command is None:
        print("Starting Football MCP Server (FastMCP)...", file=sys.stderr)
        mcp.run()

    elif args.command == "quota":
        q = api_client.get_quota_status()
        print("\n=== API Quota Status ===")
        print(f"Requests Made Today : {q['requests_made_today']}")
        print(f"Requests Remaining  : {q['requests_remaining']} / {q['max_daily_quota']}")
        print(f"Safety Threshold    : {q['safety_threshold']}")
        print(f"Safe for API Calls  : {'YES' if q['can_make_request'] else 'NO'}")
        print(f"Rate Limit          : {q['rate_limit_per_minute']} req/min\n")

    elif args.command == "sync":
        print(f"Syncing {args.league} ({args.season})...")
        standings = sync_service.sync_standings(args.league, args.season, force=args.force)
        print(f"Synced {len(standings)} teams in standings.")
        if not args.no_players:
            leaders = sync_service.sync_player_leaders(args.league, args.season, force=args.force)
            print(f"Synced {len(leaders)} player leaders.")
        print(f"Remaining quota: {api_client.get_quota_status()['requests_remaining']}")

    elif args.command == "standings":
        from football_mcp.server import get_league_standings
        print(get_league_standings(args.league, args.season))


if __name__ == "__main__":
    main()
