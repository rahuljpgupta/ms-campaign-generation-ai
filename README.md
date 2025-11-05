# Marketing Campaign Generation AI

AI-powered marketing campaign generation using LangChain and LangGraph.

## Features

Automated campaign workflow:
1. Parse user prompts to extract audience, template, and datetime
2. Clarify ambiguous or missing information (max 5 questions with intelligent prioritization)
3. Create/verify smart lists for audience targeting
4. Generate email templates with existing assets
5. Allow template editing (manual or via prompt)
6. Confirm and schedule campaigns

## Tech Stack

- **LangChain & LangGraph**: Workflow orchestration
- **Groq**: LLM inference (openai/gpt-oss-120b)
- **HuggingFace**: Embeddings (sentence-transformers)
- **ChromaDB**: Vector storage
- **FastMCP**: MCP server creation
- **Python 3.12+**: Programming language
- **UV**: Package manager

## Setup

### Quick Setup (Recommended)

```bash
# Run the automated setup script
./setup.sh
```

This script will:
- Install Graphviz (if not already installed)
- Install Python dependencies with proper paths for your system
- Auto-detect your architecture (ARM/Intel/Linux)

### Manual Setup

<details>
<summary>Click to expand manual installation steps</summary>

### 1. Install System Dependencies

```bash
# Install graphviz (required for workflow visualization)
brew install graphviz
```

### 2. Install Python Dependencies

```bash
# For macOS (Apple Silicon/ARM), use this command:
CFLAGS="-I/opt/homebrew/include" LDFLAGS="-L/opt/homebrew/lib" uv sync

# For macOS (Intel), use:
# CFLAGS="-I/usr/local/include" LDFLAGS="-L/usr/local/lib" uv sync

# For Linux:
# uv sync
```

**Note**: The environment variables are needed for `pygraphviz` to find the Graphviz C library headers.

</details>

### Configure Environment

Create a `.env` file in the project root:

```bash
# Groq API Key for LLM inference
GROQ_API_KEY=your_groq_api_key_here

# HuggingFace API Token (optional, for private models)
HUGGINGFACE_API_TOKEN=your_huggingface_token_here

# ChromaDB settings (optional)
CHROMA_PERSIST_DIRECTORY=./chroma_db

# Frederick API Configuration
FREDERICK_API_BASE=https://api.staging.hirefrederick.com/v2
FREDERICK_API_KEY=your_frederick_api_key_here
FREDERICK_BEARER_TOKEN=your_bearer_token_here
FREDERICK_LOCATION_ID=your_default_location_id
```

## Usage

### Run Web UI (Recommended)

Start the FastAPI backend server:

```bash
# Install web dependencies
uv add fastapi uvicorn websockets

# Run the WebSocket server
uv run python server.py
```

The UI has been migrated to the `platatouille/client` project.

Access the UI at `http://localhost:3000`

### Run MCP Server

The MCP (Model Context Protocol) server provides tools to interact with Frederick's API:

```bash
# Run the contacts MCP server
uv run python contacts_mcp.py

# Test the MCP tools
uv run python test_contacts_mcp.py
```

**Available MCP Tools:**
- `get_existing_smart_lists(location_id)`: Fetch all smart lists for a location (used in workflow)

### Run Campaign Generator

```bash
# Run via main entry point
uv run python main.py

# Or run as module
uv run python -m src
```

This will:
- Generate a workflow visualization (`campaign_workflow.png`)
- Parse the campaign prompt interactively
- Display extracted audience, template, and datetime information

### Example Prompt

```
Create a Black Friday sale campaign for all the contacts in New York 
which have also visited my studio to offer 30% discount on Black Friday 
promotion and send it on 30th November 9AM
```

## Project Structure

```
ms-campaign-generation-ai/
├── src/                          # Core Python package
│   ├── __init__.py              # Package initialization
│   ├── __main__.py              # Module entry point
│   ├── campaign_generator.py   # Main CampaignGenerator class
│   ├── models.py                # Pydantic models and state definitions
│   ├── prompts.py               # LLM prompt templates
│   ├── nodes.py                 # Workflow node implementations
│   └── workflow.py              # LangGraph workflow builder
├── (client moved to platatouille/client) # UI now integrated in Platatouille
│   │   ├── services/           # WebSocket service
│   │   ├── types/              # Type definitions (JSDoc)
│   │   └── styles/             # CSS styles
│   ├── package.json            # Node dependencies
│   └── vite.config.js          # Vite configuration
├── server.py                     # FastAPI WebSocket server
├── contacts_mcp.py               # MCP server for Frederick API
├── test_contacts_mcp.py          # Test script for MCP server
├── main.py                       # CLI entry point
├── pyproject.toml                # Project dependencies (UV)
├── requirements.txt              # Pip-compatible dependencies
├── .env                          # Environment variables (create this)
└── README.md                     # This file
```

### Module Breakdown

**Core Campaign Generator:**
- **`models.py`**: Data models (`ParsedPrompt`, `CampaignState`)
- **`prompts.py`**: All LLM prompt templates (parsing, clarifications)
- **`nodes.py`**: Workflow node functions (parse, clarify, process)
- **`workflow.py`**: LangGraph workflow construction
- **`campaign_generator.py`**: Main orchestrator class
- **`main.py`**: Command-line interface

**MCP Server:**
- **`contacts_mcp.py`**: FastMCP server with Frederick API tools
- **`test_contacts_mcp.py`**: Test suite for MCP tools

## Development Status

- [x] Parse user prompt into components (Step 1)
- [x] Clarify ambiguous/missing information with interactive loop (max 5 questions) (Step 2)
- [x] Fetch existing smart lists and match with audience (Step 3)
- [x] Present top 3 matches with confirmation or create new option (Step 4)
- [ ] Create new smart list (Step 5)
- [ ] Generate email templates (Step 6)
- [ ] Template editing support (Step 7)
- [ ] Schedule confirmation (Step 8)

## Key Features

### 🎯 Intelligent Clarification System
- Asks maximum 5 most critical questions
- Prioritizes: audience criteria > offer details > datetime
- Makes reasonable assumptions for minor details
- Users can skip questions (press Enter) for AI to use best judgment
- Loops until all critical information is collected

### 📋 Smart List Matching
- Fetches existing smart lists from Frederick API via MCP
- Uses LLM to intelligently match audience with existing lists
- Presents up to 3 best matches with relevance scores
- Shows match reasons and contact counts
- User can select existing list or create new one
- Automatically handles cases with no matches

## Troubleshooting

### `pygraphviz` Build Failure

If you encounter an error like `fatal error: 'graphviz/cgraph.h' file not found` during `uv sync`:

**Solution**: Use the provided setup script which handles this automatically:
```bash
./setup.sh
```

**Or manually** set the compiler flags:
```bash
# macOS Apple Silicon (ARM)
CFLAGS="-I/opt/homebrew/include" LDFLAGS="-L/opt/homebrew/lib" uv sync

# macOS Intel
CFLAGS="-I/usr/local/include" LDFLAGS="-L/usr/local/lib" uv sync
```

Make sure Graphviz is installed first: `brew install graphviz`

### WebSocket Connection Issues

If the UI shows "Connecting to server..." indefinitely:
1. Check backend is running: `uv run python server.py`
2. Check for port conflicts (port 8000)
3. Verify `.env` file has required API keys
4. Check browser console for CORS errors

### LLM Errors

If you see LLM-related errors:
1. Verify `GROQ_API_KEY` is set in `.env`
2. Check API key is valid at [Groq Console](https://console.groq.com)
3. Ensure you have API credits available