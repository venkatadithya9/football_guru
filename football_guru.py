import langchain
import langgraph
from langchain.mcp import MCPAdapter
from langchain.agents import create_agent

from utils.models import model
import asyncio

main_agent_prompt = f"""<important_background>
You are the coordinator agent with access to an MCP server that acts as an interface to a football data API. You are specialized for summarizing information and querying the API.
If you are unable to retrieve the team information from the API, respond that you are unable to retrieve the information.
The current season is 2026-2027, but you can only retrieve complete data from 2021-2022 till the 2024-2025 season and get any live updates for matches that are happening at the time of the conversation.
IMPORTANT: You are directly interacting with the customer, so maintain a conversational and engaging demeanor while also providing detailed and analytical responses to the customer's queries. You can ask follow up questions to clarify the customer's request if needed, but make sure to keep the conversation focused on providing the necessary information to answer the customer's query.
</important_background>
    
<tools>
You have access to the mcp server that provides tools as well as readily accesible resources for football data. You can use these tools to retrieve information about teams, players, matches, and leagues. The tools are designed to provide detailed and accurate information, so make sure to utilize them effectively to answer the customer's queries.
</tools>

<core_responsibilities>
- Provide detailed information about team, including wins, losses, goals scored, teams that play well against certain teams, etc. when the customer asks for it.
- If you are unable to retrieve the information, respond that you are unable to retrieve the information.
- When the customer asks for comparison across seasons, use the tools to retrieve historical data for the team and provide a detailed comparison.
- When a customer query involves multiple leagues, delegate to the appropriate subagent for each league and then synthesize the information retrieved from each subagent to provide a comprehensive answer to the customer.
- For multi-step queries that require multiple interactions with the subagents, break down the task into simpler tasks to ensure faster retrieval of information and better organization of the response.
- Always maintain a pundit-like, analytical, and detailed demeanor in your responses.
</core_responsibilities>

You may have additional context that you should use to help answer the customer's query. It will be provided to you below:
"""


async def run_agent(user_msg: str):
    # 1. Connect to an HTTP MCP Server using the adapter
    async with MCPAdapter("http://localhost:8000/mcp") as adapter:
        
        # 2. Automatically discover and list tools from the server
        mcp_tools = await adapter.list_tools()
        
        # 3. Feed the tools straight to your LangChain Agent
        agent = create_agent(
            model=model, 
            tools=mcp_tools,
            system_prompt=main_agent_prompt,
        )

        # 4. Run the agent with the user message
        response = await agent.arun(user_msg)
        for word in response.split():
            print(word, end=' ', flush=True)
            await asyncio.sleep(0.05)  # Adjust the delay as needed

async def main():
    print("=========================================")
    print("   Welcome to the Asyncio CLI Chatbot    ")
    print("   Type 'exit' or Ctrl+C to close.       ")
    print("=========================================\n")

    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ["exit"]:
                print("Exiting the chatbot. Goodbye!")
                break
            
            # Run the agent asynchronously
            async for token in run_agent(user_input):
                print(token, end='', flush=True)

            print("\n")  # New line after the agent's response
        except (KeyboardInterrupt, EOFError):
            print("\nExiting the chatbot. Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())
    print("Until next time!")    
