#!/bin/bash

# Development startup script for Campaign Generator

echo "Starting Campaign Generator Development Environment..."
echo ""

# Start backend server in background
echo "Starting FastAPI WebSocket server..."
uv run python server.py &
BACKEND_PID=$!

# Wait for backend to start
sleep 2

# Start frontend
echo "Starting React development server..."
cd client && npm run dev

# Cleanup on exit
trap "kill $BACKEND_PID" EXIT

