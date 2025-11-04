"""
WebSocket connection manager for handling multiple client connections
"""

from fastapi import WebSocket
from typing import Dict, Optional
import asyncio


class ConnectionManager:
    """Manages WebSocket connections and message broadcasting"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        # Store location data per client
        self.client_locations: Dict[str, dict] = {}
        # Store API credentials per client
        self.client_credentials: Dict[str, dict] = {}
    
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
        if client_id in self.client_locations:
            del self.client_locations[client_id]
        if client_id in self.client_credentials:
            del self.client_credentials[client_id]
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
    
    def set_location(self, client_id: str, location: dict):
        """
        Store location data for a client
        
        Args:
            client_id: Client identifier
            location: Location data dictionary
        """
        self.client_locations[client_id] = location
        print(f"Location data stored for client {client_id}: {location.get('name', 'Unknown')}")
    
    def get_location(self, client_id: str) -> Optional[dict]:
        """
        Get location data for a client
        
        Args:
            client_id: Client identifier
            
        Returns:
            Location data dictionary or None if not found
        """
        return self.client_locations.get(client_id)
    
    def set_credentials(self, client_id: str, credentials: dict):
        """
        Store API credentials for a client
        
        Args:
            client_id: Client identifier
            credentials: Credentials dictionary with api_key, bearer_token, api_url
        """
        self.client_credentials[client_id] = credentials
        print(f"API credentials stored for client {client_id}")
    
    def get_credentials(self, client_id: str) -> Optional[dict]:
        """
        Get API credentials for a client
        
        Args:
            client_id: Client identifier
            
        Returns:
            Credentials dictionary or None if not found
        """
        return self.client_credentials.get(client_id)

