/**
 * Individual chat message component
 */

import React from 'react';
import '../styles/ChatMessage.css';

export const ChatMessage = ({ message }) => {
  const getMessageClass = (type) => {
    switch (type) {
      case 'user':
        return 'message-user';
      case 'assistant':
        return 'message-assistant';
      case 'system':
        return 'message-system';
      case 'assistant_thinking':
        return 'message-thinking';
      case 'error':
        return 'message-error';
      case 'question':
      case 'options':
      case 'confirmation':
        return 'message-question';
      default:
        return '';
    }
  };

  const getMessagePrefix = (type, questionNumber, totalQuestions) => {
    switch (type) {
      case 'user':
        return 'You';
      case 'assistant':
        return 'Assistant';
      case 'system':
        return 'System';
      case 'assistant_thinking':
        return 'Assistant';
      case 'error':
        return 'Error';
      case 'question':
        if (questionNumber && totalQuestions) {
          return `Question ${questionNumber}/${totalQuestions}`;
        }
        return 'Question';
      case 'options':
        return 'Select Option';
      case 'confirmation':
        return 'Confirmation';
      default:
        return '';
    }
  };

  return (
    <div className={`chat-message ${getMessageClass(message.type)}`}>
      <div className="message-prefix">
        {getMessagePrefix(message.type, message.questionNumber, message.totalQuestions)}
      </div>
      <div className="message-content" style={{ whiteSpace: 'pre-wrap' }}>
        {message.message}
      </div>
      <div className="message-timestamp">
        {new Date(message.timestamp).toLocaleTimeString()}
      </div>
    </div>
  );
};

