"""
WebSocket endpoint handlers for campaign generation
"""

from fastapi import WebSocket, WebSocketDisconnect
import asyncio

from .connection_manager import ConnectionManager
from ..workflows.executor import WorkflowExecutor
from ..workflows import websocket_nodes

# Global connection manager
manager = ConnectionManager()

# Global workflow executor
executor = WorkflowExecutor()


async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    Main WebSocket endpoint for client connections
    
    Args:
        websocket: WebSocket connection
        client_id: Unique client identifier
    """
    await manager.connect(client_id, websocket)
    
    # Send welcome message
    await manager.send_message(client_id, {
        "type": "assistant",
        "message": "Hey! Ready to create an amazing campaign? Tell me what you're thinking.",
        "timestamp": asyncio.get_event_loop().time()
    })
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "handshake":
                # Store location data and credentials from initial handshake
                location = data.get("location", {})
                credentials = data.get("credentials", {})
                
                manager.set_location(client_id, location)
                manager.set_credentials(client_id, credentials)
                
                # Acknowledge handshake (silently - no need to tell user about technical details)
                # await manager.send_message(client_id, {
                #     "type": "system",
                #     "message": f"Location context received: {location.get('name', 'Unknown')}",
                #     "timestamp": asyncio.get_event_loop().time()
                # })
            
            elif message_type == "user_message":
                user_message = data.get("message", "")
                
                # Echo user message
                await manager.send_message(client_id, {
                    "type": "user",
                    "message": user_message,
                    "timestamp": asyncio.get_event_loop().time()
                })
                
                # Process with campaign generator as background task
                # This allows the WebSocket loop to continue receiving messages
                asyncio.create_task(executor.process_campaign(client_id, user_message, manager))
            
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
            
            elif message_type == "reset":
                # Reset the campaign creation flow
                executor.reset_client_state(client_id)
                
                await manager.send_message(client_id, {
                    "type": "assistant",
                    "message": "All set! Let's start fresh. What would you like to create?",
                    "timestamp": asyncio.get_event_loop().time()
                })
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        print(f"Client {client_id} disconnected")
    except Exception as e:
        print(f"Error with client {client_id}: {e}")
        manager.disconnect(client_id)


async def handle_user_response(client_id: str, question_id: str, response: str):
    """
    Handle user's response to clarification questions or selections
    
    Args:
        client_id: Client identifier
        question_id: Question identifier
        response: User's response
    """
    from ..workflows.review_smart_list_nodes import set_response as set_review_response
    from ..workflows.retry_smart_list_nodes import set_response as set_retry_response
    from ..workflows.review_email_template_nodes import set_response as set_email_review_response
    from ..workflows.schedule_confirmation_nodes import set_response as set_schedule_response
    
    # Set the response for the pending question
    # Try all response handlers (regular, review, retry, email review, schedule)
    websocket_nodes.set_response(question_id, response)
    set_review_response(question_id, response)
    set_retry_response(question_id, response)
    set_email_review_response(question_id, response)
    set_schedule_response(question_id, response)
    
    # The websocket node functions are awaiting the response and will
    # continue execution automatically. This function just needs to
    # set the response to unblock them.

