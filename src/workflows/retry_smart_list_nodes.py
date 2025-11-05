"""
Nodes for handling smart list creation retry logic
"""

import asyncio
from typing import Callable
from ..models import CampaignState


# Store for pending responses
pending_responses = {}


def set_response(question_id: str, response: str):
    """Set the response for a pending question"""
    if question_id in pending_responses:
        future = pending_responses.pop(question_id)
        if not future.done():
            future.set_result(response)


async def retry_smart_list_creation_ws(state: CampaignState, send_message: Callable) -> dict:
    """
    Ask user for better audience description to retry smart list creation
    
    Args:
        state: Current campaign state
        send_message: Function to send messages via WebSocket
    
    Returns:
        Updated state with user's new description
    """
    # Generate unique question ID
    question_id = f"retry_audience_{asyncio.get_event_loop().time()}"
    
    # Get the error details message from state if available
    error_details = state.get("error_details_message", "Could you provide more details or rephrase your audience description? I'll regenerate the filters and try again.")
    
    print(f"[Retry] Asking user for better description (question_id: {question_id})")
    
    # Send the question to the user
    await send_message({
        "type": "question",
        "message": f"{error_details}\n\n**Please provide a COMPLETE audience description:**\n(Not just modifications, but a full description like 'Female customers in California who have visited in the last 30 days')",
        "question_id": question_id,
        "timestamp": asyncio.get_event_loop().time(),
        "disable_input": False
    })
    
    # Wait for user's response
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    pending_responses[question_id] = future
    
    print(f"[Retry] Waiting for user's response to question_id: {question_id}")
    better_description = await future
    print(f"[Retry] Received new audience description: {better_description}")
    
    # Update the audience description and continue
    return {
        "audience": better_description,
        "current_step": "regenerate_fredql_after_retry"
    }

