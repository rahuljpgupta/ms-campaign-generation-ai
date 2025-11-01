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

### 1. Install System Dependencies

```bash
# Install graphviz (required for workflow visualization)
brew install graphviz
```

### 2. Install Python Dependencies

```bash
# Sync all dependencies
uv sync
```

### 3. Configure Environment

Create a `.env` file in the project root:

```bash
# Groq API Key for LLM inference
GROQ_API_KEY=your_groq_api_key_here

# HuggingFace API Token (optional, for private models)
HUGGINGFACE_API_TOKEN=your_huggingface_token_here

# ChromaDB settings (optional)
CHROMA_PERSIST_DIRECTORY=./chroma_db
```

## Usage

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
├── src/
│   ├── __init__.py              # Package initialization
│   ├── __main__.py              # Module entry point
│   ├── campaign_generator.py   # Main CampaignGenerator class
│   ├── models.py                # Pydantic models and state definitions
│   ├── prompts.py               # LLM prompt templates
│   ├── nodes.py                 # Workflow node implementations
│   └── workflow.py              # LangGraph workflow builder
├── main.py                       # CLI entry point
├── pyproject.toml                # Project dependencies (UV)
├── requirements.txt              # Pip-compatible dependencies
├── .env                          # Environment variables (create this)
└── README.md                     # This file
```

### Module Breakdown

- **`models.py`**: Data models (`ParsedPrompt`, `CampaignState`)
- **`prompts.py`**: All LLM prompt templates (parsing, clarifications)
- **`nodes.py`**: Workflow node functions (parse, clarify, process)
- **`workflow.py`**: LangGraph workflow construction
- **`campaign_generator.py`**: Main orchestrator class
- **`main.py`**: Command-line interface

## Development Status

- [x] Parse user prompt into components (Step 1)
- [x] Clarify ambiguous/missing information with interactive loop (max 5 questions) (Step 2)
- [ ] Check/create smart lists (Steps 3-4)
- [ ] Generate email templates (Step 5)
- [ ] Template editing support (Step 6)
- [ ] Schedule confirmation (Step 7)

## Key Features

### 🎯 Intelligent Clarification System
- Asks maximum 5 most critical questions
- Prioritizes: audience criteria > offer details > datetime
- Makes reasonable assumptions for minor details
- Users can skip questions (press Enter) for AI to use best judgment
- Loops until all critical information is collected