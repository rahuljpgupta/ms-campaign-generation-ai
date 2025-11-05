#!/bin/bash

# Setup script for Campaign Generator
# Handles installation of dependencies with proper Graphviz paths

set -e

echo "=========================================="
echo "Campaign Generator - Setup Script"
echo "=========================================="
echo ""

# Check if graphviz is installed
echo "Checking for Graphviz installation..."
if ! command -v dot &> /dev/null; then
    echo "❌ Graphviz is not installed!"
    echo "Installing Graphviz via Homebrew..."
    brew install graphviz
else
    echo "✅ Graphviz is already installed"
fi

echo ""
echo "Installing Python dependencies..."

# Detect architecture and set appropriate paths
if [[ $(uname -m) == "arm64" ]]; then
    echo "Detected: Apple Silicon (ARM)"
    CFLAGS="-I/opt/homebrew/include" LDFLAGS="-L/opt/homebrew/lib" uv sync
elif [[ $(uname) == "Darwin" ]]; then
    echo "Detected: macOS Intel"
    CFLAGS="-I/usr/local/include" LDFLAGS="-L/usr/local/lib" uv sync
else
    echo "Detected: Linux/Other"
    uv sync
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Create a .env file with your API keys (see README.md)"
echo "2. Run 'uv run python server.py' to start the backend"
echo "3. Access the UI at http://localhost:3000 (Platatouille client)"
echo ""

