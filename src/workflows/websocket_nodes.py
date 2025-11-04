"""
WebSocket-aware workflow nodes that communicate via WebSocket instead of terminal input
"""

import asyncio
from typing import Dict, Any, Callable
from ..models import CampaignState
from ..nodes import fetch_and_match_smart_lists as _fetch_and_match_smart_lists


# Global storage for pending responses
pending_responses: Dict[str, asyncio.Future] = {}


async def ask_clarifications_ws(state: CampaignState, send_message: Callable) -> dict:
    """
    WebSocket version of ask_clarifications.
    Sends questions via WebSocket and waits for responses.
    """
    await send_message({
        "type": "system",
        "message": f"I need to clarify {len(state['clarifications_needed'])} thing(s) about your campaign.",
        "timestamp": asyncio.get_event_loop().time()
    })
    
    clarification_responses = state.get("clarification_responses", {})
    questions_to_ask = state["clarifications_needed"][:5]
    
    # Send each question
    for i, question in enumerate(questions_to_ask, 1):
        question_id = f"clarification_{i}"
        
        await send_message({
            "type": "question",
            "message": question,
            "question_id": question_id,
            "question_number": i,
            "total_questions": len(questions_to_ask),
            "timestamp": asyncio.get_event_loop().time()
        })
        
        # Wait for response
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        pending_responses[question_id] = future
        
        response = await future
        clarification_responses[question] = response or "Not specified - please use best judgment"
    
    return {
        "clarification_responses": clarification_responses,
        "current_step": "process_clarifications"
    }


async def confirm_smart_list_selection_ws(state: CampaignState, send_message: Callable) -> dict:
    """
    WebSocket version of confirm_smart_list_selection.
    Sends list options via WebSocket and waits for selection.
    """
    matched_lists = state.get("matched_lists", [])
    
    await send_message({
        "type": "system",
        "message": f"Great! I found {len(matched_lists)} existing smart list(s) that match your audience.",
        "timestamp": asyncio.get_event_loop().time()
    })
    
    # Send list options
    options = []
    for i, lst in enumerate(matched_lists, 1):
        option = {
            "id": str(i),
            "label": lst.get('display_name') or lst.get('name'),
            "description": f"Relevance: {int(lst.get('relevance_score', 0) * 100)}% - {lst.get('reason', 'N/A')}",
            "metadata": {
                "list_id": lst.get("id"),
                "name": lst.get("name"),
                "filters": lst.get("filters", [])
            }
        }
        options.append(option)
    
    # Add "create new" option
    options.append({
        "id": "0",
        "label": "Create new smart list",
        "description": "I'll create a custom list based on your audience criteria",
        "metadata": {}
    })
    
    await send_message({
        "type": "options",
        "message": "Please select a smart list or create a new one:",
        "question_id": "smart_list_selection",
        "options": options,
        "timestamp": asyncio.get_event_loop().time()
    })
    
    # Wait for selection
    future = asyncio.Future()
    pending_responses["smart_list_selection"] = future
    choice = await future
    
    try:
        choice_num = int(choice)
        
        if choice_num == 0:
            await send_message({
                "type": "system",
                "message": "✓ I'll create a new smart list for your campaign.",
                "timestamp": asyncio.get_event_loop().time()
            })
            return {
                "create_new_list": True,
                "smart_list_id": "",
                "smart_list_name": "",
                "current_step": "generate_fredql"
            }
        elif 1 <= choice_num <= len(matched_lists):
            selected = matched_lists[choice_num - 1]
            await send_message({
                "type": "system",
                "message": f"✓ Using smart list: {selected.get('display_name') or selected.get('name')}",
                "timestamp": asyncio.get_event_loop().time()
            })
            return {
                "create_new_list": False,
                "smart_list_id": selected.get("id"),
                "smart_list_name": selected.get("name"),
                "current_step": "complete_selection"
            }
        else:
            await send_message({
                "type": "error",
                "message": "Invalid selection. Creating new list.",
                "timestamp": asyncio.get_event_loop().time()
            })
            return {
                "create_new_list": True,
                "smart_list_id": "",
                "smart_list_name": "",
                "current_step": "generate_fredql"
            }
    except ValueError:
        await send_message({
            "type": "error",
            "message": "Invalid input. Creating new list.",
            "timestamp": asyncio.get_event_loop().time()
        })
        return {
            "create_new_list": True,
            "smart_list_id": "",
            "smart_list_name": "",
            "current_step": "generate_fredql"
        }


async def confirm_new_list_ws(state: CampaignState, send_message: Callable) -> dict:
    """
    WebSocket version of confirm_new_list.
    Asks for confirmation to create a new list.
    """
    await send_message({
        "type": "system",
        "message": "No existing smart lists match your audience criteria.",
        "timestamp": asyncio.get_event_loop().time()
    })
    
    await send_message({
        "type": "system",
        "message": f"Target Audience: {state.get('audience', 'N/A')}",
        "timestamp": asyncio.get_event_loop().time()
    })
    
    await send_message({
        "type": "confirmation",
        "message": "Would you like me to create a new smart list?",
        "question_id": "confirm_new_list",
        "timestamp": asyncio.get_event_loop().time()
    })
    
    # Wait for confirmation
    future = asyncio.Future()
    pending_responses["confirm_new_list"] = future
    response = await future
    
    if response and response.lower() in ['yes', 'y', 'ok', 'sure', 'proceed']:
        await send_message({
            "type": "system",
            "message": "✓ I'll create a new smart list for your campaign.",
            "timestamp": asyncio.get_event_loop().time()
        })
        return {
            "create_new_list": True,
            "smart_list_id": "",
            "smart_list_name": "",
            "current_step": "generate_fredql"
        }
    else:
        await send_message({
            "type": "system",
            "message": "Campaign creation cancelled.",
            "timestamp": asyncio.get_event_loop().time()
        })
        return {
            "current_step": "cancelled"
        }


def set_response(question_id: str, response: str):
    """Set a response for a pending question"""
    if question_id in pending_responses:
        future = pending_responses[question_id]
        if not future.done():
            future.set_result(response)
        del pending_responses[question_id]


async def fetch_and_match_smart_lists_wrapper(state: CampaignState, llm, credentials: dict = None) -> dict:
    """
    Wrapper for fetch_and_match_smart_lists that can be used in LangGraph workflow
    """
    return await _fetch_and_match_smart_lists(state, llm, credentials)


async def generate_smart_list_fredql_ws(state: CampaignState, llm, send_message: Callable, location: dict = None) -> dict:
    """
    Generate FredQL for the smart list based on audience description
    
    Args:
        state: Current campaign state
        llm: LLM instance
        send_message: Function to send messages via WebSocket
        location: Location data from client
    
    Returns:
        Updated state with generated FredQL
    """
    audience_description = state.get("audience", "")
    
    await send_message({
        "type": "assistant_thinking",
        "message": "Generating smart list query from your audience description...",
        "timestamp": asyncio.get_event_loop().time(),
        "disable_input": True
    })
    
    try:
        from ..prompts import FREDQL_GENERATION_TEMPLATE
        from ..utils.location_utils import format_location_context
        import json
        
        # Format location context
        location_context = format_location_context(location)
        
        # Generate FredQL using LLM
        chain = FREDQL_GENERATION_TEMPLATE | llm
        response = chain.invoke({
            "audience_description": audience_description,
            "location_context": location_context
        })
        
        # Extract FredQL from response
        fredql_text = response.content.strip()
        
        # Try to parse as JSON to validate
        try:
            # Remove markdown code blocks if present
            if fredql_text.startswith("```"):
                fredql_text = fredql_text.split("```")[1]
                if fredql_text.startswith("json"):
                    fredql_text = fredql_text[4:]
                fredql_text = fredql_text.strip()
            
            fredql_query = json.loads(fredql_text)
            
            # Format for display
            fredql_display = json.dumps(fredql_query, indent=2)
            
            await send_message({
                "type": "assistant",
                "message": f"✓ Generated FredQL query for your audience:\n\n```json\n{fredql_display}\n```\n\n**Audience:** {audience_description}",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            
            return {
                "fredql_query": fredql_query,
                "current_step": "end_for_now"
            }
            
        except json.JSONDecodeError as e:
            # If parsing fails, still show the generated query but mark as error
            await send_message({
                "type": "assistant",
                "message": f"⚠️ Generated query (validation needed):\n\n```\n{fredql_text}\n```\n\n**Audience:** {audience_description}\n\nNote: Query may need manual review.",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            
            return {
                "fredql_query": fredql_text,
                "current_step": "end_for_now"
            }
    
    except Exception as e:
        await send_message({
            "type": "error",
            "message": f"Failed to generate FredQL query: {str(e)}",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": False
        })
        
        return {
            "current_step": "end_for_now"
        }

