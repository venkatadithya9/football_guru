"""Rate-limited API client for API-Football v3.

Strictly manages:
- 10 requests / minute rate limit (via sliding window throttle).
- 100 requests / day free quota (reads x-ratelimit-requests-remaining header).
- Safety threshold to block non-essential calls when daily quota <= 5.
- Real-time live fixtures querying with in-memory caching to prevent duplicate hits.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from football_mcp.config import (
    API_BASE_URL,
    API_KEY,
    DAILY_QUOTA_SAFETY_THRESHOLD,
    MAX_REQUESTS_PER_DAY,
    MAX_REQUESTS_PER_MINUTE,
    MIN_SECONDS_BETWEEN_REQUESTS,
)
from football_mcp.database import FootballDatabase

logger = logging.getLogger("football_mcp.api_client")


class QuotaExceededException(Exception):
    """Raised when daily quota limit or safety threshold is reached."""
    pass


class RateLimitedApiClient:
    """HTTP Client for API-Football v3 with built-in rate-limiting and quota safeguards."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        db: Optional[FootballDatabase] = None,
        safety_threshold: int = DAILY_QUOTA_SAFETY_THRESHOLD,
        min_interval_sec: float = MIN_SECONDS_BETWEEN_REQUESTS,
    ):
        self.api_key = api_key or API_KEY
        self.base_url = (base_url or API_BASE_URL).rstrip("/")
        self.db = db or FootballDatabase()
        self.safety_threshold = safety_threshold
        self.min_interval_sec = min_interval_sec
        self._last_request_time: float = 0.0

        # In-memory cache for live scores (30s TTL)
        self._live_cache: Optional[Dict[str, Any]] = None
        self._live_cache_time: float = 0.0
        self._live_cache_ttl: float = 30.0

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "x-apisports-key": self.api_key,
            "Accept": "application/json",
            "User-Agent": "FootballMCP/1.0",
        }

    def _wait_for_rate_limit(self) -> None:
        """Enforce the 10 req/minute limit by waiting between requests if needed."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.min_interval_sec:
            sleep_time = self.min_interval_sec - elapsed
            logger.info(f"Rate limiting: throttling for {sleep_time:.2f}s...")
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    async def _async_wait_for_rate_limit(self) -> None:
        """Asynchronous wait to enforce rate limit."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.min_interval_sec:
            sleep_time = self.min_interval_sec - elapsed
            logger.info(f"Rate limiting (async): throttling for {sleep_time:.2f}s...")
            await asyncio.sleep(sleep_time)
        self._last_request_time = time.time()

    def get_quota_status(self) -> Dict[str, Any]:
        """
        Check current quota status based on DB logs and last reported API headers.
        """
        req_count_today = self.db.get_requests_today_count()
        last_remaining = self.db.get_latest_requests_remaining()

        # If header wasn't logged yet, estimate from local count
        estimated_remaining = (
            last_remaining
            if last_remaining is not None
            else max(0, MAX_REQUESTS_PER_DAY - req_count_today)
        )

        can_make_request = estimated_remaining > self.safety_threshold

        return {
            "requests_made_today": req_count_today,
            "requests_remaining": estimated_remaining,
            "max_daily_quota": MAX_REQUESTS_PER_DAY,
            "safety_threshold": self.safety_threshold,
            "can_make_request": can_make_request,
            "rate_limit_per_minute": MAX_REQUESTS_PER_MINUTE,
        }

    def make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        bypass_safety: bool = False,
    ) -> Dict[str, Any]:
        """
        Synchronous request with rate-limiting and quota check.
        """
        endpoint = endpoint.lstrip("/")
        quota = self.get_quota_status()

        if not bypass_safety and not quota["can_make_request"]:
            msg = (
                f"API Quota Protection: {quota['requests_remaining']} requests remaining "
                f"(safety threshold: {self.safety_threshold}). Request to '{endpoint}' blocked."
            )
            logger.warning(msg)
            raise QuotaExceededException(msg)

        self._wait_for_rate_limit()

        url = f"{self.base_url}/{endpoint}"
        start_time = time.time()

        try:
            response = requests.get(url, headers=self.headers, params=params or {}, timeout=15.0)
            elapsed_ms = (time.time() - start_time) * 1000

            # Extract API header: x-ratelimit-requests-remaining
            remaining_header = response.headers.get("x-ratelimit-requests-remaining")
            requests_remaining = int(remaining_header) if remaining_header and remaining_header.isdigit() else None

            # Log to DB
            self.db.log_api_request(
                endpoint=endpoint,
                status_code=response.status_code,
                requests_remaining=requests_remaining,
                response_time_ms=elapsed_ms,
            )

            response.raise_for_status()
            data = response.json()

            # Check if API returned an error message in JSON
            if "errors" in data and data["errors"]:
                if isinstance(data["errors"], dict) and data["errors"]:
                    logger.error(f"API Error returned for {endpoint}: {data['errors']}")
                elif isinstance(data["errors"], list) and len(data["errors"]) > 0:
                    logger.error(f"API Errors returned for {endpoint}: {data['errors']}")

            return data

        except requests.RequestException as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self.db.log_api_request(
                endpoint=endpoint,
                status_code=getattr(e.response, "status_code", 0) if hasattr(e, "response") and e.response is not None else 500,
                requests_remaining=None,
                response_time_ms=elapsed_ms,
            )
            logger.error(f"HTTP request error calling {endpoint}: {e}")
            raise

    async def async_make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        bypass_safety: bool = False,
    ) -> Dict[str, Any]:
        """Asynchronous wrapper for make_request."""
        await self._async_wait_for_rate_limit()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.make_request(endpoint=endpoint, params=params, bypass_safety=bypass_safety),
        )

    # ----------------- SPECIFIC ENDPOINTS -----------------

    def get_api_status(self) -> Dict[str, Any]:
        """Query /status endpoint to verify credentials and remote quota."""
        # /status consumes 0 quota on API-Sports!
        return self.make_request("status", bypass_safety=True)

    def get_standings(self, league_id: int, season: int) -> List[Dict[str, Any]]:
        """Fetch league standings from API."""
        data = self.make_request("standings", params={"league": league_id, "season": season})
        response = data.get("response", [])
        return response

    def get_team_statistics(self, league_id: int, team_id: int, season: int) -> Dict[str, Any]:
        """Fetch team statistics for a competition and season."""
        data = self.make_request(
            "teams/statistics",
            params={"league": league_id, "team": team_id, "season": season},
        )
        return data.get("response", {})

    def get_top_scorers(self, league_id: int, season: int) -> List[Dict[str, Any]]:
        """Fetch top 20 scorers for a league and season."""
        data = self.make_request(
            "players/topscorers",
            params={"league": league_id, "season": season},
        )
        return data.get("response", [])

    def get_top_assists(self, league_id: int, season: int) -> List[Dict[str, Any]]:
        """Fetch top 20 assist providers for a league and season."""
        data = self.make_request(
            "players/topassists",
            params={"league": league_id, "season": season},
        )
        return data.get("response", [])

    def get_team_players(self, team_id: int, season: int) -> List[Dict[str, Any]]:
        """Fetch all player statistics for a team roster in a season."""
        data = self.make_request("players", params={"team": team_id, "season": season})
        return data.get("response", [])

    def get_live_fixtures(self, league_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """
        Fetch real-time live matches with a 30s in-memory cache to prevent spamming.
        """
        now = time.time()
        if (
            self._live_cache is not None
            and (now - self._live_cache_time) < self._live_cache_ttl
        ):
            logger.info("Serving live fixtures from 30s cache.")
            return self._live_cache.get("response", [])

        params: Dict[str, str] = {}
        if league_ids:
            params["live"] = "-".join(str(lid) for lid in league_ids)
        else:
            params["live"] = "all"

        data = self.make_request("fixtures", params=params, bypass_safety=True)
        self._live_cache = data
        self._live_cache_time = now
        return data.get("response", [])

    def get_fixtures_by_date(self, date_str: str, league_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch fixtures for a specific date (format: YYYY-MM-DD)."""
        params: Dict[str, Any] = {"date": date_str}
        if league_id:
            params["league"] = league_id
        data = self.make_request("fixtures", params=params)
        return data.get("response", [])
