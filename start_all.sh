#!/usr/bin/env bash
# start_all.sh
# One-click startup for both backend and frontend

echo "=========================================================="
echo "⚽ Starting Football Guru Full Stack Application"
echo "=========================================================="

trap 'kill $(jobs -p) 2>/dev/null' EXIT

# 1. Start Backend in conda 'test'
./run_backend.sh &

# 2. Wait for backend to be ready
sleep 3

# 3. Start Frontend
./run_frontend.sh
