/**
 * Type definitions for chat messages and state
 * (Using JSDoc for type hints)
 */

/**
 * @typedef {'user' | 'assistant' | 'system' | 'assistant_thinking' | 'error'} MessageType
 */

/**
 * @typedef {Object} Message
 * @property {string} id
 * @property {MessageType} type
 * @property {string} message
 * @property {number} timestamp
 * @property {string} [questionId]
 */

/**
 * @typedef {Object} ChatState
 * @property {Message[]} messages
 * @property {boolean} isConnected
 * @property {boolean} isTyping
 */

export {};

