# Campaign Generator - Architecture

## 📁 Project Structure

```
ms-campaign-generation-ai/
├── server.py                 # FastAPI application entry point
├── contacts_mcp.py          # MCP server for Frederick API integration
├── test_contacts_mcp.py     # Tests for MCP server
│
├── src/
│   ├── __init__.py          # Package initialization
│   │
│   ├── api/                 # API layer (FastAPI routes & handlers)
│   │   ├── __init__.py
│   │   ├── connection_manager.py    # WebSocket connection management
│   │   └── websocket_handler.py     # WebSocket endpoint logic
│   │
│   ├── workflows/           # Workflow orchestration
│   │   ├── __init__.py
│   │   ├── executor.py              # Workflow execution engine
│   │   ├── websocket_workflow.py    # LangGraph workflow definition
│   │   └── websocket_nodes.py       # Interactive WebSocket nodes
│   │
│   ├── nodes.py             # Core processing nodes (LLM-based)
│   ├── models.py            # Pydantic models & TypedDict
│   └── prompts.py           # LLM prompt templates
│
└── client/                  # React JavaScript UI
    ├── src/
    │   ├── components/      # React components
    │   ├── hooks/          # Custom React hooks
    │   ├── services/       # API services
    │   └── styles/         # CSS stylesheets
    └── package.json
```

## 🏗️ Architecture Layers

### 1. **API Layer** (`src/api/`)
Handles HTTP/WebSocket communication and connection management.

**Components:**
- **`connection_manager.py`**: Manages WebSocket connections
  - Connection lifecycle (connect/disconnect)
  - Message routing to specific clients
  - Connection status tracking

- **`websocket_handler.py`**: WebSocket endpoint handlers
  - Message type routing
  - User message processing
  - Response handling

### 2. **Workflow Layer** (`src/workflows/`)
Orchestrates the campaign generation workflow using LangGraph.

**Components:**
- **`executor.py`**: Main workflow execution engine
  - State management per client
  - Workflow step coordination
  - Error handling and cleanup

- **`websocket_workflow.py`**: LangGraph workflow definition
  - Node connections and routing
  - Conditional edges
  - Checkpointing configuration

- **`websocket_nodes.py`**: Interactive nodes that pause for user input
  - Clarification questions
  - Smart list selection
  - New list confirmation

### 3. **Processing Layer** (`src/`)
Core business logic and LLM processing.

**Components:**
- **`nodes.py`**: LLM-based processing nodes
  - Prompt parsing
  - Clarification processing
  - Smart list matching

- **`prompts.py`**: LLM prompt templates
  - System prompts
  - User prompt formatting

- **`models.py`**: Data models
  - Type definitions
  - State structures

## 🔄 Data Flow

```
User Message (WebSocket)
    ↓
WebSocket Handler
    ↓
Workflow Executor
    ↓
┌─────────────────────────────┐
│   LangGraph Workflow        │
│                             │
│  1. Parse Prompt            │
│  2. Clarifications (loop)   │
│  3. Check Smart Lists       │
│  4. Confirm Selection       │
│  5. Final Summary           │
└─────────────────────────────┘
    ↓
Response (WebSocket)
    ↓
User Interface
```

## 🔌 Key Design Patterns

### 1. **Separation of Concerns**
- **API layer**: Communication only
- **Workflow layer**: Orchestration only
- **Processing layer**: Business logic only

### 2. **Dependency Injection**
- Connection manager passed to handlers
- LLM instance injected into executor
- Send message function injected into nodes

### 3. **Async/Await Pattern**
- All I/O operations are async
- Background tasks for long-running operations
- Non-blocking WebSocket message loop

### 4. **State Management**
- Per-client session storage
- LangGraph checkpointing
- Clean state on workflow completion

## 📦 Module Responsibilities

### `ConnectionManager`
- ✅ Accept/reject connections
- ✅ Track active connections
- ✅ Send messages to specific clients
- ✅ Handle disconnections

### `WorkflowExecutor`
- ✅ Initialize LLM and workflows
- ✅ Manage client sessions
- ✅ Execute workflow steps
- ✅ Build campaign summaries
- ✅ Clean up completed sessions

### `websocket_nodes`
- ✅ Interactive clarification collection
- ✅ Smart list option presentation
- ✅ User response handling
- ✅ Async Future-based synchronization

### `nodes`
- ✅ LLM prompt parsing
- ✅ Clarification processing
- ✅ API integration (MCP)
- ✅ Smart list matching logic

## 🚀 Extensibility

The modular architecture makes it easy to:

1. **Add new workflow steps**:
   - Create new node in `websocket_nodes.py`
   - Add to `websocket_workflow.py`
   - Update `executor.py` with step logic

2. **Add new API endpoints**:
   - Create handler in `src/api/`
   - Add route to `server.py`

3. **Add new processing logic**:
   - Add function to `nodes.py`
   - Use in workflow executor

4. **Add new models**:
   - Define in `models.py`
   - Import where needed

## 🧪 Testing Strategy

- **Unit tests**: Test individual nodes and functions
- **Integration tests**: Test workflow execution
- **E2E tests**: Test full WebSocket communication

## 📝 Development Guidelines

1. **Keep modules focused**: Each module should have one responsibility
2. **Use type hints**: All functions should have type annotations
3. **Document public APIs**: All public functions need docstrings
4. **Handle errors gracefully**: Wrap risky operations in try/except
5. **Log important events**: Use print statements for debugging (replace with proper logging later)

## 🔮 Future Enhancements

- [ ] Replace print statements with proper logging (structlog/loguru)
- [ ] Add metrics and monitoring
- [ ] Implement persistent checkpointing (database/Redis)
- [ ] Add authentication/authorization
- [ ] Implement rate limiting
- [ ] Add workflow visualization endpoint
- [ ] Create admin dashboard

