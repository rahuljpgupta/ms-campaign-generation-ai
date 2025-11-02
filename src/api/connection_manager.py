"""
WebSocket connection manager for handling multiple client connections
"""

from fastapi import WebSocket
from typing import Dict
import asyncio


class ConnectionManager:
    """Manages WebSocket connections and message broadcasting"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, client_id: str, websocket: WebSocket):
        """
        Accept and register a new WebSocket connection
        
        Args:
            client_id: Unique identifier for the client
            websocket: WebSocket connection instance
        """
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"Client {client_id} connected")
    
    def disconnect(self, client_id: str):
        """
        Remove a client connection
        
        Args:
            client_id: Unique identifier for the client
        """
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            print(f"Client {client_id} disconnected")
    
    async def send_message(self, client_id: str, message: dict):
        """
        Send a message to a specific client
        
        Args:
            client_id: Target client identifier
            message: Message dictionary to send
        """
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)
    
    def is_connected(self, client_id: str) -> bool:
        """
        Check if a client is connected
        
        Args:
            client_id: Client identifier to check
            
        Returns:
            True if client is connected, False otherwise
        """
        return client_id in self.active_connections

