"""
FastAPI server for Campaign Generator with WebSocket support
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import json
import asyncio
import os
from src.campaign_generator import CampaignGenerator
from src import websocket_nodes
from src.nodes import (
    parse_prompt,
    process_clarifications,
    check_smart_lists,
    fetch_and_match_smart_lists
)

app = FastAPI(title="Campaign Generator API")

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Campaign generator instance
campaign_gen = CampaignGenerator()

# Client session storage
client_sessions: Dict[str, Dict[str, Any]] = {}


class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
    
    async def send_message(self, client_id: str, message: dict):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)


manager = ConnectionManager()


@app.get("/")
async def root():
    return {"message": "Campaign Generator API", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for real-time chat with campaign generator
    """
    await manager.connect(websocket, client_id)
    
    # Send welcome message
    await manager.send_message(client_id, {
        "type": "system",
        "message": "Connected to Campaign Generator. How can I help you create a campaign today?",
        "timestamp": asyncio.get_event_loop().time()
    })
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "user_message":
                user_message = data.get("message", "")
                
                # Echo user message
                await manager.send_message(client_id, {
                    "type": "user",
                    "message": user_message,
                    "timestamp": asyncio.get_event_loop().time()
                })
                
                # Process with campaign generator as background task
                # This allows the WebSocket loop to continue receiving messages
                asyncio.create_task(process_campaign_message(client_id, user_message))
            
            elif message_type == "user_response":
                # Handle user responses to clarifications
                response = data.get("response", "")
                question_id = data.get("question_id", "")
                
                await manager.send_message(client_id, {
                    "type": "user",
                    "message": response,
                    "timestamp": asyncio.get_event_loop().time()
                })
                
                # Process response
                await handle_user_response(client_id, question_id, response)
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        print(f"Client {client_id} disconnected")
    except Exception as e:
        print(f"Error with client {client_id}: {e}")
        manager.disconnect(client_id)


async def process_campaign_message(client_id: str, message: str):
    """
    Process user message through campaign generator workflow
    """
    # Send processing indicator
    await manager.send_message(client_id, {
        "type": "assistant_thinking",
        "message": "Analyzing your campaign request...",
        "timestamp": asyncio.get_event_loop().time(),
        "disable_input": True
    })
    
    try:
        # Initialize session state
        if client_id not in client_sessions:
            client_sessions[client_id] = {
                "user_prompt": message,
                "audience": "",
                "template": "",
                "datetime": "",
                "location_id": os.getenv("FREDERICK_LOCATION_ID", ""),
                "smart_list_id": "",
                "smart_list_name": "",
                "create_new_list": False,
                "matched_lists": [],
                "email_template": "",
                "schedule_confirmed": False,
                "clarifications_needed": [],
                "clarification_responses": {},
                "current_step": "parse_prompt"
            }
        
        state = client_sessions[client_id]
        
        # Helper function to send messages
        async def send_msg(msg):
            await manager.send_message(client_id, msg)
        
        # Step 1: Parse prompt
        if state["current_step"] == "parse_prompt":
            await send_msg({
                "type": "assistant",
                "message": "Let me parse your campaign requirements...",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": True
            })
            
            parse_result = parse_prompt(state, campaign_gen.llm)
            state.update(parse_result)
            
            await send_msg({
                "type": "assistant",
                "message": f"✓ Understood:\n• Audience: {state['audience']}\n• Campaign: {state['template']}\n• Schedule: {state['datetime']}",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": True
            })
        
        # Step 2: Handle clarifications (loop until all are resolved)
        while state.get("clarifications_needed") and len(state["clarifications_needed"]) > 0:
            clarification_result = await websocket_nodes.ask_clarifications_ws(state, send_msg)
            state.update(clarification_result)
            
            # After clarifications, process them
            process_result = process_clarifications(state, campaign_gen.llm)
            state.update(process_result)
            
            # Loop will continue if more clarifications are needed
        
        # Step 3: Check smart lists
        if state["current_step"] in ["check_clarifications", "clarify_ambiguity"]:
            await send_msg({
                "type": "assistant_thinking",
                "message": "Checking for existing smart lists...",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": True
            })
            
            # Call async function directly instead of using sync wrapper
            check_result = await fetch_and_match_smart_lists(state, campaign_gen.llm)
            state.update(check_result)
        
        # Step 4: Handle smart list selection
        if state["current_step"] == "confirm_smart_list_selection":
            result = await websocket_nodes.confirm_smart_list_selection_ws(state, send_msg)
            state.update(result)
        elif state["current_step"] == "confirm_new_list":
            result = await websocket_nodes.confirm_new_list_ws(state, send_msg)
            state.update(result)
        
        # Final summary
        if state["current_step"] == "end_for_now":
            summary = "✅ Campaign setup complete!\n\n"
            summary += f"📊 **Audience:** {state['audience']}\n"
            summary += f"📧 **Campaign:** {state['template']}\n"
            summary += f"📅 **Schedule:** {state['datetime']}\n"
            
            if state.get('create_new_list'):
                summary += f"📋 **Smart List:** Will create new list\n"
            elif state.get('smart_list_id'):
                summary += f"📋 **Smart List:** {state.get('smart_list_name', 'Selected')}\n"
            
            await send_msg({
                "type": "assistant",
                "message": summary,
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            
            # Clear session
            if client_id in client_sessions:
                del client_sessions[client_id]
        
        elif state["current_step"] == "cancelled":
            await send_msg({
                "type": "system",
                "message": "Campaign creation cancelled. Start a new conversation to create another campaign.",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            
            # Clear session
            if client_id in client_sessions:
                del client_sessions[client_id]
        
    except Exception as e:
        await manager.send_message(client_id, {
            "type": "error",
            "message": f"Error processing request: {str(e)}",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": False
        })


async def handle_user_response(client_id: str, question_id: str, response: str):
    """
    Handle user's response to clarification questions or selections
    """
    # Set the response for the pending question
    websocket_nodes.set_response(question_id, response)
    
    # The websocket node functions are awaiting the response and will
    # continue execution automatically. This function just needs to
    # set the response to unblock them.


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

