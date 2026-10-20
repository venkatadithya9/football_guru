"""
Football Guru Streaming API Server
Provides real-time Server-Sent Events (SSE) streaming of agent thought process,
tool calls, and generated responses to the interactive frontend.
"""

import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

import langchain
import langgraph
from langchain.agents import create_agent
from langchain.mcp import MCPAdapter
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langsmith import uuid7

# Ensure environment variables are loaded
load_dotenv(override=True)

from utils.models import model

# --- Logging configuration ---
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("football_api")

# --- Agent System Prompt ---
from football_guru import main_agent_prompt, create_resource_reader_tool

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")

class AgentManager:
    """Manages MCP adapter connection, tool discovery, and LangGraph agent lifecycle."""

    def __init__(self, mcp_url: str = MCP_SERVER_URL):
        self.mcp_url = mcp_url
        self.adapter: Optional[MCPAdapter] = None
        self.agent: Optional[Any] = None
        self.tools: List[Any] = []
        self.memory = MemorySaver()
        self.connected = False
        self.error: Optional[str] = None

    async def connect(self) -> bool:
        """Attempt to connect to the MCP server and instantiate the LangGraph agent."""
        try:
            logger.info(f"Connecting to Football MCP server at {self.mcp_url}...")
            # Close previous adapter if open
            if self.adapter:
                try:
                    await self.adapter.__aexit__(None, None, None)
                except Exception:
                    pass

            self.adapter = MCPAdapter(self.mcp_url)
            await self.adapter.__aenter__()

            mcp_tools = await self.adapter.list_tools()
            resource_reader = create_resource_reader_tool(self.adapter)
            self.tools = [*mcp_tools, resource_reader]

            self.agent = create_agent(
                model=model,
                tools=self.tools,
                system_prompt=main_agent_prompt,
                checkpointer=self.memory,
            )
            self.connected = True
            self.error = None
            logger.info(f"Agent successfully initialized with {len(self.tools)} tools.")
            return True
        except Exception as e:
            self.connected = False
            self.error = str(e)
            logger.error(f"Failed to connect to MCP server: {e}")
            return False

    async def close(self):
        """Clean up MCP adapter connection on shutdown."""
        if self.adapter:
            try:
                await self.adapter.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing MCP adapter: {e}")
        self.connected = False


agent_manager = AgentManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: attempt MCP connection
    asyncio.create_task(agent_manager.connect())
    yield
    # Shutdown: cleanly close MCP adapter
    await agent_manager.close()


app = FastAPI(
    title="Football Guru Agent API",
    description="SSE streaming API for the Football Guru tactical assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS setup for Vite frontend (runs on port 5173 by default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request and Response Models ---

class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None


class ResetRequest(BaseModel):
    thread_id: Optional[str] = None


# --- Thought & Token Streaming Parser ---

class StreamParser:
    """
    Parses LLM streaming events into distinct 'thought' and 'token' categories.
    Handles Gemini thinking tags (<thought>...</thought>), kwargs reasoning_content,
    and regular answer tokens.
    """

    def __init__(self):
        self.in_thought_tag = False
        self.thought_buffer = ""
        self.tag_buffer = ""

    def process_chunk(self, chunk: Any) -> List[Dict[str, str]]:
        events = []

        # 1. Check metadata / kwargs for explicit reasoning tokens (Gemini 2.0 / 3.8 thinking)
        if hasattr(chunk, "additional_kwargs") and chunk.additional_kwargs:
            reasoning = chunk.additional_kwargs.get("reasoning_content") or chunk.additional_kwargs.get("thought")
            if reasoning:
                events.append({"type": "thought", "content": reasoning})

        # 2. Extract text content
        raw_content = chunk.content if hasattr(chunk, "content") else str(chunk)
        if isinstance(raw_content, list):
            text_parts = []
            for part in raw_content:
                if isinstance(part, dict):
                    if part.get("type") == "thought":
                        events.append({"type": "thought", "content": part.get("thought", "")})
                    elif part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif "text" in part:
                        text_parts.append(part["text"])
                else:
                    text_parts.append(str(part))
            text = "".join(text_parts)
        else:
            text = str(raw_content)

        if not text:
            return events

        # 3. Parse <thought> tags if present in the text stream
        i = 0
        while i < len(text):
            if not self.in_thought_tag:
                if text[i:].startswith("<thought>"):
                    self.in_thought_tag = True
                    i += len("<thought>")
                    continue
                else:
                    # Regular text token
                    # Collect until next <thought> or end
                    next_open = text.find("<thought>", i)
                    if next_open == -1:
                        events.append({"type": "token", "content": text[i:]})
                        break
                    else:
                        events.append({"type": "token", "content": text[i:next_open]})
                        i = next_open
            else:
                next_close = text.find("</thought>", i)
                if next_close == -1:
                    events.append({"type": "thought", "content": text[i:]})
                    break
                else:
                    events.append({"type": "thought", "content": text[i:next_close]})
                    self.in_thought_tag = False
                    i = next_close + len("</thought>")

        return events


# --- Streaming Generator ---

async def event_generator(user_message: str, thread_id: str) -> AsyncGenerator[str, None]:
    """Streams SSE formatted JSON events to the frontend."""

    # 1. Ensure Agent is connected
    if not agent_manager.connected or not agent_manager.agent:
        reconnected = await agent_manager.connect()
        if not reconnected:
            err_payload = json.dumps({
                "type": "error",
                "error": f"Cannot connect to MCP Server at {agent_manager.mcp_url}. Please ensure the FastMCP server is running.",
            })
            yield f"data: {err_payload}\n\n"
            return

    # Yield initial thread confirmation
    start_payload = json.dumps({"type": "start", "thread_id": thread_id})
    yield f"data: {start_payload}\n\n"

    parser = StreamParser()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        async for event in agent_manager.agent.astream_events(
            {"messages": [HumanMessage(content=user_message)]},
            config=config,
            version="v2",
        ):
            event_name = event.get("event")

            # --- Model Streaming Tokens & Thoughts ---
            if event_name == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk:
                    parsed_events = parser.process_chunk(chunk)
                    for pe in parsed_events:
                        yield f"data: {json.dumps(pe)}\n\n"

            # --- Tool Call Started ---
            elif event_name == "on_tool_start":
                tool_name = event.get("name", "tool")
                tool_input = event.get("data", {}).get("input", {})
                run_id = event.get("run_id", str(uuid7()))
                logger.info(f"Tool Started: {tool_name} with input {tool_input}")
                payload = json.dumps({
                    "type": "tool_start",
                    "run_id": run_id,
                    "tool": tool_name,
                    "input": tool_input,
                })
                yield f"data: {payload}\n\n"

            # --- Tool Call Completed ---
            elif event_name == "on_tool_end":
                tool_name = event.get("name", "tool")
                raw_output = event.get("data", {}).get("output", "")
                run_id = event.get("run_id", "")
                
                output_str = raw_output.content if hasattr(raw_output, "content") else str(raw_output)
                logger.info(f"Tool Completed: {tool_name}")
                payload = json.dumps({
                    "type": "tool_end",
                    "run_id": run_id,
                    "tool": tool_name,
                    "output": output_str,
                })
                yield f"data: {payload}\n\n"

        # Signal completion
        done_payload = json.dumps({"type": "done", "thread_id": thread_id})
        yield f"data: {done_payload}\n\n"

    except Exception as e:
        logger.error(f"Error during agent turn: {e}", exc_info=True)
        err_payload = json.dumps({"type": "error", "error": str(e)})
        yield f"data: {err_payload}\n\n"


# --- API Endpoints ---

@app.get("/api/status")
async def get_status():
    """Return status of MCP connection, tools count, and agent readiness."""
    if not agent_manager.connected:
        # Quick retry if requested
        await agent_manager.connect()

    return {
        "status": "ready" if agent_manager.connected else "mcp_disconnected",
        "mcp_url": agent_manager.mcp_url,
        "tools_count": len(agent_manager.tools),
        "error": agent_manager.error,
    }


@app.get("/api/quota")
async def get_quota():
    """Return API-Football quota and remaining requests."""
    try:
        from football_mcp.api_client import RateLimitedApiClient
        from football_mcp.database import FootballDatabase
        db = FootballDatabase()
        client = RateLimitedApiClient(db=db)
        return client.get_quota_status()
    except Exception as e:
        return {
            "requests_made_today": 0,
            "requests_remaining": 100,
            "max_daily_quota": 100,
            "safety_threshold": 10,
            "can_make_request": True,
            "rate_limit_per_minute": 10,
            "error": str(e),
        }


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """Chat endpoint returning a Server-Sent Events stream."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    thread_id = req.thread_id or str(uuid7())

    return StreamingResponse(
        event_generator(req.message, thread_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/reset")
async def reset_endpoint(req: Optional[ResetRequest] = None):
    """Generate a new thread ID to start a fresh chat session."""
    new_thread_id = str(uuid7())
    return {"status": "ok", "thread_id": new_thread_id}


@app.get("/api/leagues")
async def get_leagues_and_clubs():
    """
    Return the top European leagues and clubs with official API-Football
    crests, league badges, and country flags.
    """
    from football_mcp.config import TOP_5_LEAGUES
    from football_mcp.database import FootballDatabase

    db = FootballDatabase()

    FLAG_MAP = {
        39: "https://media.api-sports.io/flags/gb.svg",
        140: "https://media.api-sports.io/flags/es.svg",
        78: "https://media.api-sports.io/flags/de.svg",
        135: "https://media.api-sports.io/flags/it.svg",
        61: "https://media.api-sports.io/flags/fr.svg",
    }

    leagues_data = []
    for lid, linfo in TOP_5_LEAGUES.items():
        teams = db.get_teams_by_league(lid)
        teams_list = [
            {
                "id": t["id"],
                "name": t["name"],
                "code": t.get("code"),
                "logo": t.get("logo") or f"https://media.api-sports.io/football/teams/{t['id']}.png",
            }
            for t in teams[:10]  # Featured clubs
        ]

        leagues_data.append({
            "id": lid,
            "key": linfo.key,
            "name": linfo.name,
            "country": linfo.country,
            "flag": FLAG_MAP.get(lid, ""),
            "logo": f"https://media.api-sports.io/football/leagues/{lid}.png",
            "teams": teams_list,
        })

    return {"leagues": leagues_data}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("football_api:app", host="0.0.0.0", port=8001, reload=True)
