/**
 * Custom React hook for WebSocket connection
 */

import { useEffect, useRef, useState } from 'react';
import { WebSocketService } from '../services/websocket';

export const useWebSocket = (clientId) => {
  const [messages, setMessages] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [inputEnabled, setInputEnabled] = useState(true);
  const [pendingQuestion, setPendingQuestion] = useState(null);
  const wsRef = useRef(null);

  useEffect(() => {
    // Initialize WebSocket service
    const ws = new WebSocketService(clientId);
    wsRef.current = ws;

    // Set up message listener
    ws.onMessage((data) => {
      // Handle input state
      if (data.disable_input !== undefined) {
        setInputEnabled(!data.disable_input);
      } else if (data.type === 'question' || data.type === 'options' || data.type === 'confirmation') {
        setInputEnabled(true); // Enable for questions
      }
      
      // Handle questions and options
      if (data.type === 'question' || data.type === 'options' || data.type === 'confirmation') {
        setPendingQuestion({
          id: data.question_id,
          type: data.type,
          options: data.options,
        });
      }
      
      const newMessage = {
        id: `${Date.now()}-${Math.random()}`,
        type: data.type,
        message: data.message,
        timestamp: data.timestamp || Date.now(),
        questionId: data.question_id,
        options: data.options,
        questionNumber: data.question_number,
        totalQuestions: data.total_questions,
      };
      setMessages((prev) => [...prev, newMessage]);
    });

    // Set up connection listener
    ws.onConnectionChange((connected) => {
      setIsConnected(connected);
      if (connected) {
        setInputEnabled(true);
      } else {
        setInputEnabled(false);
      }
    });

    // Connect
    ws.connect();

    // Cleanup on unmount
    return () => {
      ws.disconnect();
    };
  }, [clientId]);

  const sendMessage = (message) => {
    if (wsRef.current) {
      wsRef.current.sendMessage(message);
      setPendingQuestion(null);
      setInputEnabled(false); // Disable while processing
    }
  };

  const sendResponse = (questionId, response) => {
    if (wsRef.current) {
      wsRef.current.sendResponse(questionId, response);
      setPendingQuestion(null);
      setInputEnabled(false); // Disable while processing
    }
  };

  return {
    messages,
    isConnected,
    inputEnabled,
    pendingQuestion,
    sendMessage,
    sendResponse,
  };
};

