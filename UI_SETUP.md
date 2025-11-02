# UI Setup Guide

## Architecture Overview

The Campaign Generator UI consists of two parts:

1. **Backend**: FastAPI server with WebSocket support (`server.py`)
2. **Frontend**: React TypeScript application (`client/`)

## Quick Start

### Option 1: Use the Startup Script

```bash
./start-dev.sh
```

This will start both backend and frontend servers.

### Option 2: Manual Start

**Terminal 1 - Backend:**
```bash
uv run python server.py
```
Backend will run on `http://localhost:8000`

**Terminal 2 - Frontend:**
```bash
cd client
npm install  # First time only
npm run dev
```
Frontend will run on `http://localhost:3000`

## Backend (FastAPI WebSocket Server)

### File: `server.py`

**Features:**
- WebSocket endpoint at `/ws/{client_id}`
- CORS middleware for React app
- Connection management
- Message routing

**Key Components:**
- `ConnectionManager`: Manages WebSocket connections
- `websocket_endpoint`: Main WebSocket handler
- `process_campaign_message`: Processes user messages (TODO: integrate with CampaignGenerator)

**API Endpoints:**
- `GET /`: Health check
- `GET /health`: Server status
- `WS /ws/{client_id}`: WebSocket connection

## Frontend (React TypeScript)

### Structure

```
client/src/
├── components/          # React components
│   ├── ChatPanel.tsx   # Main chat container
│   ├── ChatMessage.tsx # Individual message display
│   └── ChatInput.tsx   # Message input field
├── hooks/              
│   └── useWebSocket.ts # WebSocket hook
├── services/           
│   └── websocket.ts    # WebSocket client service
├── types/              
│   └── chat.ts         # TypeScript interfaces
├── styles/             # CSS files
└── App.tsx             # Main app component
```

### Key Features

**WebSocket Service** (`services/websocket.ts`):
- Auto-reconnection
- Connection state management
- Message queuing
- Error handling

**useWebSocket Hook** (`hooks/useWebSocket.ts`):
- React integration
- State management
- Message history
- Connection status

**Chat Components**:
- `ChatPanel`: Main container with header and messages
- `ChatMessage`: Individual message with type-based styling
- `ChatInput`: Textarea with send button

### Message Types

```typescript
type MessageType = 'user' | 'assistant' | 'system' | 'assistant_thinking' | 'error';
```

### Styling

Dark theme inspired by VS Code:
- Background: `#1e1e1e`
- Sidebar: `#252526`
- User messages: `#0e639c` (blue)
- Assistant messages: `#2d2d30` (gray)
- System messages: `#1e3a5f` (dark blue)

## WebSocket Communication Protocol

### Client → Server

**User Message:**
```json
{
  "type": "user_message",
  "message": "Create a campaign for..."
}
```

**User Response (to clarifications):**
```json
{
  "type": "user_response",
  "question_id": "q1",
  "response": "New York"
}
```

### Server → Client

**Assistant Message:**
```json
{
  "type": "assistant",
  "message": "I'll help you...",
  "timestamp": 1234567890
}
```

**Thinking Indicator:**
```json
{
  "type": "assistant_thinking",
  "message": "Processing...",
  "timestamp": 1234567890
}
```

**Error:**
```json
{
  "type": "error",
  "message": "Something went wrong",
  "timestamp": 1234567890
}
```

## Integration with CampaignGenerator

### TODO: In `server.py`

1. **Import the workflow:**
```python
from src.campaign_generator import CampaignGenerator
```

2. **Create interactive workflow:**
   - Convert `ask_clarifications` to WebSocket-based
   - Convert `confirm_smart_list_selection` to WebSocket-based
   - Send progress updates during workflow execution

3. **Handle user responses:**
   - Store conversation state per client
   - Map question IDs to workflow steps
   - Resume workflow when response received

### Example Integration Flow

```
User: "Create campaign for NY customers"
  ↓
Server: Parse prompt
  ↓
Server: Need clarifications → Send questions
  ↓
User: Answers questions
  ↓
Server: Process answers
  ↓
Server: Check smart lists → Send matches
  ↓
User: Select list
  ↓
Server: Continue workflow...
```

## Development Tips

### Hot Reload

- Backend: `uvicorn server:app --reload`
- Frontend: Vite provides hot module replacement automatically

### Debugging WebSocket

Open browser console and check:
```javascript
// Connection status
console.log('WebSocket state:', ws.readyState);
// 0: CONNECTING, 1: OPEN, 2: CLOSING, 3: CLOSED

// Monitor messages
ws.onmessage = (e) => console.log('Received:', JSON.parse(e.data));
```

### Testing

```bash
# Backend
cd /Users/rahulgupta/Rahul/hackathon2025/ms-campaign-generation-ai
uv run pytest

# Frontend
cd client
npm test
```

## Deployment

### Backend

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd client
npm run build
# Serve dist/ folder with any static file server
```

## Next Steps

1. ✅ Basic WebSocket communication
2. ✅ Chat UI with message types
3. 🔲 Integrate CampaignGenerator workflow
4. 🔲 Add clarification question UI
5. 🔲 Add smart list selection UI
6. 🔲 Add campaign preview
7. 🔲 Add error handling and retry logic
8. 🔲 Add conversation history persistence
9. 🔲 Add user authentication
10. 🔲 Add campaign management dashboard

