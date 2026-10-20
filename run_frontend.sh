#!/usr/bin/env bash
# run_frontend.sh
# Installs dependencies if needed and launches the React Vite frontend

cd "$(dirname "$0")/frontend" || exit 1

echo "======================================================"
echo "⚽ Starting Football Guru React + Vite Frontend"
echo "======================================================"

if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies with npm..."
    npm install
fi

echo "🚀 Starting Vite dev server on http://localhost:5173..."
npm run dev
