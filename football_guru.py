import asyncio
import logging
import re
from pathlib import Path

import langchain
import langgraph
from langchain.agents import create_agent
from langchain.mcp import MCPAdapter
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langsmith import uuid7
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown

console = Console()

# --- Route Gemini / Google GenAI schema warnings to log file ---
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
_file_handler = logging.FileHandler(LOG_DIR / "gemini_warnings.log")
_file_handler.setLevel(logging.WARNING)
_file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

_gemini_logger = logging.getLogger("langchain_google_genai")
_gemini_logger.setLevel(logging.WARNING)
_gemini_logger.addHandler(_file_handler)
_gemini_logger.propagate = False  # Suppress from printing to terminal stderr

from utils.models import model

main_agent_prompt = f"""<role>
You are the Football Guru coordinator agent—an analytical, articulate football pundit with access to an MCP server connected to API-Football.
You provide detailed tactical analysis, compare records across seasons, and give real-time updates.
Calendar reference: Today is in the 2026-2027 season, but your full historical database spans 2021-2022 to 2024-2025. Real-time scores are available for active matches today.
Avoid making up data; if a query is outside your knowledge base, respond with "I don't have that information."
Avoid hallucinations; always verify data against the MCP server or cached resources.
Maintain an engaging, pundit-like demeanor with clear, analytical markdown formatting.
</role>

<mcp_resources>
In addition to your callable tools (whose descriptions and schemas are provided automatically), you have access to zero-latency, pre-cached local snapshots via the `read_mcp_resource` tool.
ALWAYS prefer reading a resource over calling external tools when asking for tables, bulk stats, or leaderboards to avoid rate limits:

- football://standings/{{league}}/{{season}}   -> Full league table (e.g. football://standings/pl/2024)
- football://players/{{league}}/{{season}}     -> Top scorers and assist leaders (e.g. football://players/pl/2024)
- football://teams/{{team_id}}/statistics/{{season}} -> Club deep dive (e.g. football://teams/42/statistics/2024)
- football://players/{{team_id}}/roster/{{season}}   -> Team squad roster (e.g. football://players/42/roster/2024)
- football://teams/{{league}}/{{season}}       -> League club directory
- football://seasons/summary/{{season}}       -> Cross-European season overview
- football://status/quota                     -> Current API quota status

Valid leagues: 'pl' (Premier League), 'laliga' (La Liga), 'bundesliga' (Bundesliga), 'serie_a' (Serie A), 'ligue1' (Ligue 1).
</mcp_resources>
"""


def create_resource_reader_tool(adapter: MCPAdapter):
    """
    Factory creating a LangChain tool that reads MCP Resources via URI.
    
    This bridges the gap between MCP Resources (URI-addressable static data)
    and the LLM Agent, allowing the model to dynamically request any cached resource.
    """
    @tool
    async def read_mcp_resource(uri: str) -> str:
        """
        Read structured, pre-cached football data from an MCP Resource URI.
        
        ADVANTAGES & USAGE PATTERNS:
        - Reads local SQLite snapshots with 0 external API calls (avoids rate limits).
        - Use this whenever you need full league tables, player leaderboards, or season summaries.
        
        SUPPORTED URI TEMPLATES:
        1. Standings:
           - football://standings/{league}/{season} (e.g. 'football://standings/pl/2024')
        2. League Player Leaders:
           - football://players/{league}/{season} (e.g. 'football://players/laliga/2024')
        3. Team Deep Dive Stats:
           - football://teams/{team_id}/statistics/{season} (e.g. 'football://teams/42/statistics/2024')
        4. Team Squad Roster:
           - football://players/{team_id}/roster/{season} (e.g. 'football://players/42/roster/2024')
        5. European Season Summary:
           - football://seasons/summary/{season} (e.g. 'football://seasons/summary/2024')
        6. Quota Audit:
           - football://status/quota
        
        Valid Leagues: 'pl', 'laliga', 'bundesliga', 'serie_a', 'ligue1'.
        
        Args:
            uri: The resource URI matching one of the templates above.
        """
        try:
            contents = await adapter.client.read_resource(uri)
            if not contents:
                return f"Resource at '{uri}' returned empty content."
            return "\n".join(getattr(c, "text", str(c)) for c in contents)
        except Exception as e:
            return f"Error reading MCP resource '{uri}': {e}"

    return read_mcp_resource


async def main():
    print("=========================================")
    print("   Welcome to the Football Guru Chatbot  ")
    print("   Type 'exit' or Ctrl+C to close.       ")
    print("=========================================\n")

    # 1. Connect to the MCP Server ONCE for the entire chat session
    print("Connecting to Football MCP server at http://localhost:8000/mcp...")
    async with MCPAdapter("http://localhost:8000/mcp") as adapter:
        # 2. Discover tools and create the resource reader tool
        mcp_tools = await adapter.list_tools()
        resource_reader = create_resource_reader_tool(adapter)
        all_tools = [*mcp_tools, resource_reader]
        print(f"Connected! Loaded {len(mcp_tools)} tools + 1 resource reader tool from MCP server.\n")

        # 3. Create the agent ONCE with conversation memory
        memory = MemorySaver()
        agent = create_agent(
            model=model,
            tools=all_tools,
            system_prompt=main_agent_prompt,
            checkpointer=memory,
        )

        thread_id = str(uuid7())
        config = {"configurable": {"thread_id": thread_id}}

        # 4. Interactive chat loop
        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ["exit", "quit"]:
                    print("Exiting the chatbot. Goodbye!")
                    break

                # Run the agent turn asynchronously
                result = await agent.ainvoke(
                    {"messages": [HumanMessage(content=user_input)]},
                    config=config,
                )

                last_message = result["messages"][-1]
                content = last_message.content if hasattr(last_message, "content") else str(last_message)
                if isinstance(content, list):
                    content_text = " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
                else:
                    content_text = str(content)

                # Progressive Markdown rendering
                tokens = re.findall(r"\S+|\n|[^\S\r\n]+", content_text)
                with Live(console=console, refresh_per_second=15) as live:
                    accumulated = ""
                    for t in tokens:
                        accumulated += t
                        live.update(Markdown(accumulated))
                        if t.strip():
                            await asyncio.sleep(0.02)

                print("\n")

            except (KeyboardInterrupt, EOFError, asyncio.exceptions.CancelledError):
                print("\nExiting the chatbot. Goodbye!")
                break


if __name__ == "__main__":
    asyncio.run(main())
    print("Until next time!")    
