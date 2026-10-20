#!/usr/bin/env bash
# run_backend.sh
# Starts the Football Guru FastAPI backend in conda environment 'test'

CONDA_ENV="test"

echo "======================================================"
echo "⚽ Starting Football Guru Streaming Backend API"
echo "======================================================"

# Check if FastMCP server is running on port 8000
if ! nc -z localhost 8000 2>/dev/null && ! curl -s http://localhost:8000/mcp >/dev/null 2>&1; then
    echo "⚠️  FastMCP server does not appear to be running on port 8000."
    echo "   Starting FastMCP server in background with conda '$CONDA_ENV'..."
    conda run -n "$CONDA_ENV" python -m football_mcp.server &
    MCP_PID=$!
    echo "   FastMCP server started (PID: $MCP_PID)."
    sleep 2
else
    echo "✅ FastMCP server is running at http://localhost:8000/mcp"
fi

echo "🚀 Launching FastAPI SSE streaming server on port 8001..."
conda run -n "$CONDA_ENV" uvicorn football_api:app --host 0.0.0.0 --port 8001 --reload
