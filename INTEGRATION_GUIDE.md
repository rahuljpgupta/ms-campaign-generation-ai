# Campaign Generator - WebSocket Integration Guide

## Overview
The Campaign Generator now has full UI integration with the backend workflow via WebSockets.

## Architecture

### Backend Components
1. **server.py** - FastAPI WebSocket server
   - Handles WebSocket connections
   - Routes messages between UI and workflow
   - Manages client sessions

2. **src/websocket_nodes.py** - WebSocket-aware workflow nodes
   - `ask_clarifications_ws()` - Sends questions via WebSocket
   - `confirm_smart_list_selection_ws()` - Sends options for smart list selection
   - `confirm_new_list_ws()` - Asks for confirmation to create new list

3. **src/nodes.py** - Core workflow nodes
   - `parse_prompt()` - Parses user campaign request
   - `process_clarifications()` - Processes user clarifications
   - `check_smart_lists()` - Fetches and matches smart lists

### Frontend Components
1. **src/hooks/useWebSocket.js** - WebSocket connection hook
   - Manages connection state
   - Tracks input enabled/disabled state
   - Handles pending questions

2. **src/components/ChatPanel.jsx** - Main chat interface
   - Displays messages and options
   - Handles user input routing
   - Shows dynamic placeholders

3. **src/components/ChatMessage.jsx** - Individual message display
   - Supports multiple message types
   - Shows question numbers
   - Formats content properly

## Message Types

### Backend → Frontend
- `system` - System notifications
- `assistant` - Assistant responses
- `assistant_thinking` - Processing indicator
- `question` - Question requiring text answer
- `options` - Multiple choice selection
- `confirmation` - Yes/no confirmation
- `error` - Error messages

### Frontend → Backend
- `user_message` - New campaign request
- `user_response` - Answer to question/option selection

## Input State Management

The input field is automatically enabled/disabled based on workflow state:
- **Disabled** when:
  - Disconnected from server
  - Workflow is processing
  - Backend sends `disable_input: true`
  
- **Enabled** when:
  - Waiting for new campaign request
  - Asking clarification questions
  - Presenting smart list options
  - Requesting confirmations

## Running the Application

### 1. Start Backend Server
```bash
# In project root
python server.py
```

### 2. Start Frontend (in another terminal)
```bash
cd client
npm install  # first time only
npm run dev
```

### 3. Or use the convenience script
```bash
./start-dev.sh
```

## Workflow Example

1. User enters: "Create a Black Friday campaign for New York contacts"
2. Backend parses the request
3. System asks clarification questions (if needed)
4. User answers each question
5. Backend fetches existing smart lists
6. UI displays matched lists as clickable options
7. User selects a list or creates new one
8. System shows campaign summary
9. Input re-enabled for next campaign

## Key Features

✅ **Interactive clarifications** - Up to 5 questions with progress indicator
✅ **Smart list matching** - Visual option selection with relevance scores
✅ **Input state management** - Automatic enable/disable based on workflow
✅ **Real-time feedback** - Processing indicators and status updates
✅ **Error handling** - Graceful error messages and reconnection
✅ **Session management** - Per-client workflow state

## Environment Variables

Required in `.env`:
- `FREDERICK_API_KEY` - Frederick API access
- `FREDERICK_LOCATION_ID` - Default location ID
- `GROQ_API_KEY` - Groq LLM access

## Next Steps

The following workflow steps are ready to be implemented:
1. Create new smart list
2. Generate email template
3. Allow template editing
4. Schedule confirmation
5. Campaign deployment

