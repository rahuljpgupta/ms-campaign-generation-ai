/**
 * Main App component
 */

import React from 'react';
import { ChatPanel } from './components/ChatPanel';
import { useWebSocket } from './hooks/useWebSocket';
import './styles/App.css';

const App = () => {
  const clientId = React.useMemo(() => `client-${Date.now()}`, []);
  const { 
    messages, 
    isConnected, 
    inputEnabled,
    pendingQuestion,
    sendMessage,
    sendResponse 
  } = useWebSocket(clientId);

  return (
    <div className="app-container">
      <div className="main-content">
        <div className="empty-main">
          <h1>Campaign Generator</h1>
          <p>Use the chat panel on the right to create your marketing campaigns</p>
        </div>
      </div>
      <div className="chat-sidebar">
        <ChatPanel
          messages={messages}
          isConnected={isConnected}
          inputEnabled={inputEnabled}
          pendingQuestion={pendingQuestion}
          onSendMessage={sendMessage}
          onSendResponse={sendResponse}
        />
      </div>
    </div>
  );
};

export default App;

