import sys
import logging

from typing_extensions import TypedDict
from typing import Annotated

from langchain_core.tools import tool

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.managed.is_last_step import RemainingSteps

from langchain.mcp import MCPAdapter
from mcp.server import MCPServer

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

# --------- MCP DEFINITION --------------

mcp = MCPServer("football_data_server")




# async def main():
#     async with MCPAdapter("https://football.com/mcp") as adapter:
#         tools = await adapter.list_tools()




