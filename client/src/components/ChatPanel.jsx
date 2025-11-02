/**
 * Main chat panel component
 */

import React, { useEffect, useRef } from 'react';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import '../styles/ChatPanel.css';

export const ChatPanel = ({ 
  messages, 
  isConnected, 
  inputEnabled,
  pendingQuestion,
  onSendMessage,
  onSendResponse 
}) => {
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = (text) => {
    if (pendingQuestion) {
      onSendResponse(pendingQuestion.id, text);
    } else {
      onSendMessage(text);
    }
  };

  const handleOptionClick = (optionId) => {
    if (pendingQuestion) {
      onSendResponse(pendingQuestion.id, optionId);
    }
  };

  const getPlaceholder = () => {
    if (!isConnected) return 'Connecting to server...';
    if (!inputEnabled) return 'Processing...';
    if (pendingQuestion) {
      if (pendingQuestion.type === 'options') {
        return 'Click an option above or type your choice...';
      }
      return 'Type your answer...';
    }
    return 'Describe your campaign...';
  };

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <h2>Campaign Assistant</h2>
        <div className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
          {isConnected ? '● Connected' : '● Disconnected'}
        </div>
      </div>

      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="empty-state">
            <p>👋 Hi! I'm your AI Campaign Assistant.</p>
            <p>Tell me about the campaign you'd like to create.</p>
          </div>
        ) : (
          <>
            {messages.map((message, index) => (
              <div key={message.id}>
                <ChatMessage message={message} />
                
                {/* Show options if this is the latest message with options */}
                {message.type === 'options' && 
                 message.options && 
                 index === messages.length - 1 && 
                 pendingQuestion && (
                  <div className="chat-options">
                    {message.options.map((option) => (
                      <button
                        key={option.id}
                        className="chat-option-button"
                        onClick={() => handleOptionClick(option.id)}
                        disabled={!inputEnabled}
                      >
                        <div className="option-label">{option.label}</div>
                        {option.description && (
                          <div className="option-description">{option.description}</div>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      <ChatInput
        onSend={handleSend}
        disabled={!isConnected || !inputEnabled}
        placeholder={getPlaceholder()}
      />
    </div>
  );
};

