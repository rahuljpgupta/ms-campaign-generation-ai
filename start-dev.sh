#!/bin/bash

# Development startup script for Campaign Generator Backend

echo "Starting Campaign Generator Backend Server..."
echo ""
echo "Note: The UI is now integrated in platatouille/client"
echo "Start the Platatouille app separately using: foreman start -f Procfile.dev"
echo ""

# Start backend server
echo "Starting FastAPI WebSocket server on http://localhost:8000..."
uv run python server.py

