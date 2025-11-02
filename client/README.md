# Campaign Generator UI

React JavaScript frontend for the Campaign Generator application.

## Features

- **Chat Interface**: Interactive chat UI similar to Cursor IDE
- **Real-time Communication**: WebSocket connection to FastAPI backend
- **Modern Design**: Dark theme with VS Code inspired styling
- **Responsive**: Works on desktop and mobile devices

## Tech Stack

- **React 18** with JavaScript (ES6+)
- **Vite** for fast development and building
- **WebSocket** for real-time bidirectional communication
- **CSS** for styling (no external UI libraries)

## Project Structure

```
client/
├── src/
│   ├── components/          # React components
│   │   ├── ChatPanel.jsx   # Main chat panel
│   │   ├── ChatMessage.jsx # Individual message
│   │   └── ChatInput.jsx   # Message input field
│   ├── hooks/              # Custom React hooks
│   │   └── useWebSocket.js # WebSocket hook
│   ├── services/           # Service layer
│   │   └── websocket.js    # WebSocket service
│   ├── types/              # Type definitions (JSDoc)
│   │   └── chat.js         # Chat message types
│   ├── styles/             # CSS stylesheets
│   │   ├── App.css
│   │   ├── ChatPanel.css
│   │   ├── ChatMessage.css
│   │   └── ChatInput.css
│   ├── App.jsx             # Main App component
│   └── main.jsx            # Entry point
├── index.html              # HTML template
├── package.json            # Dependencies
└── vite.config.js          # Vite config
```

## Getting Started

### Install Dependencies

```bash
cd client
npm install
```

### Run Development Server

```bash
npm run dev
```

The app will be available at `http://localhost:3000`

### Build for Production

```bash
npm run build
```

The built files will be in the `dist/` directory.

## Development

### Adding New Components

1. Create component in `src/components/`
2. Add corresponding CSS in `src/styles/`
3. Import and use in `App.tsx` or other components

### Modifying WebSocket Logic

Edit `src/services/websocket.ts` to change WebSocket behavior.

### Styling

All styles use CSS custom properties (variables) for easy theming.
Colors follow VS Code's dark theme palette.

## WebSocket Message Format

### Client → Server

```json
{
  "type": "user_message",
  "message": "Create a campaign..."
}
```

### Server → Client

```json
{
  "type": "assistant",
  "message": "I'll help you create that campaign...",
  "timestamp": 1234567890
}
```

### Message Types

- `user`: User messages
- `assistant`: AI responses
- `system`: System notifications
- `assistant_thinking`: AI processing indicator
- `error`: Error messages

