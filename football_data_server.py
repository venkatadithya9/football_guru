import sys
import logging

from typing_extensions import TypedDict
from typing import Annotated

from langchain_core.tools import tool

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.managed.is_last_step import RemainingSteps

from fastmcp import FastMCP
# from mcp.server import MCPServer
import httpx2

class InputState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

class State(InputState):
    loaded_memory: str
    remaining_steps: int

# --------- KEYS AND CONSTANTS ---------------------

FOOTBALL_DATA_API_KEY = "4f9e5ccd63e24dd0b1843bb8f16c86bd"
BASE_ADDRESS = "http://api.football-data.org/v4/"

# --------- LOOK UP TABLES --------------

LEAGUES = {"pl": 2021,
           "laliga": 2014,
            "bundesliga": 2002,
             "ligue1": 2015,
              "seria": 2019 }

# ---------- HELPER FUNCTIONS -----------------

async def make_request(url: str) -> dict:
    """
    Make an asynchronous HTTP GET request to the specified URL with the provided headers.

    Args:
        url (str): The URL to send the GET request to.
        headers (dict): A dictionary of HTTP headers to include in the request.

    Returns:
        dict: The JSON response from the server.

    Raises:
        httpx.HTTPStatusError: If the response status code indicates an error.
    """

    headers = {"X-Auth-Token": FOOTBALL_DATA_API_KEY}

    async with httpx2.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    return None

# --------- MCP DEFINITION --------------

mcp = FastMCP("football_data_server")

@mcp.tool()
async def get_league_standings(league: str) -> str:
    """
    Get the standings for a given league.

    Args:
        league (str): The name of the league (e.g., "pl" for Premier League, "laliga" for La Liga, "bundesliga" for Bundesliga, "ligue1" for Ligue 1, "seria" for Serie A).
    
    """
    league_id = LEAGUES.get(league.lower())
    if not league_id:
        raise ValueError(f"League '{league}' not found.")
    
    url = f"{BASE_ADDRESS}competitions/{league_id}/standings"
    data = await make_request(url)

    if not data or "standings" not in data:
        return "No standings data could be retrieved."
    

# async def main():
#     async with MCPAdapter("https://football.com/mcp") as adapter:
#         tools = await adapter.list_tools()




