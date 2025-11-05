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


async def fetch_contact_properties_for_validation(location_id: str, credentials: dict = None) -> tuple[bool, list[str], str]:
    """
    Fetch valid contact properties from the API
    
    Args:
        location_id: Location ID
        credentials: API credentials
    
    Returns:
        Tuple of (success, property_names_list, formatted_properties_string)
    """
    try:
        from contacts_mcp import get_contact_properties
        
        credentials = credentials or {}
        result = await get_contact_properties(
            location_id,
            api_key=credentials.get("api_key"),
            bearer_token=credentials.get("bearer_token"),
            api_url=credentials.get("api_url")
        )
        
        if "error" in result:
            return False, [], ""
        
        # Extract property names
        property_names = []
        for prop in result.get("data", []):
            attrs = prop.get("attributes", {})
            prop_name = attrs.get("name")
            if prop_name:
                property_names.append(prop_name)
        
        # Format for prompt
        formatted = "\n".join([f"  - {name}" for name in sorted(property_names)])
        
        return True, property_names, formatted
    except Exception as e:
        return False, [], ""


def validate_contact_properties_in_fredql(fredql_query: dict, valid_properties: list[str]) -> tuple[bool, list[str]]:
    """
    Validate that all contact property names in FredQL query are valid
    
    Args:
        fredql_query: The FredQL query dictionary
        valid_properties: List of valid property names
    
    Returns:
        Tuple of (is_valid, list_of_invalid_properties)
    """
    invalid_properties = []
    
    def check_filters(filters):
        """Recursively check filters for contact properties"""
        if not filters:
            return
        
        for filter_item in filters:
            if isinstance(filter_item, dict):
                # Check if this is a contact_property filter
                if filter_item.get("filter_type") == "contact_property":
                    prop_name = filter_item.get("property_name")
                    if prop_name and prop_name not in valid_properties:
                        invalid_properties.append(prop_name)
                
                # Check nested filters (AND/OR groups)
                if "filters" in filter_item:
                    check_filters(filter_item["filters"])
    
    # Check top-level filters
    if "filters" in fredql_query:
        check_filters(fredql_query["filters"])
    
    # Also check if fredql_query is a list (outer array format)
    if isinstance(fredql_query, list):
        for group in fredql_query:
            if isinstance(group, list):
                check_filters(group)
    
    return len(invalid_properties) == 0, invalid_properties


async def generate_smart_list_fredql_ws(state: CampaignState, llm, send_message: Callable, location: dict = None, credentials: dict = None) -> dict:
    """
    Generate FredQL for the smart list based on audience description
    
    Args:
        state: Current campaign state
        llm: LLM instance
        send_message: Function to send messages via WebSocket
        location: Location data from client
        credentials: API credentials for fetching contact properties
    
    Returns:
        Updated state with generated FredQL
    """
    audience_description = state.get("audience", "")
    location_id = state.get("location_id")
    
    # Fetch contact properties first
    await send_message({
        "type": "assistant_thinking",
        "message": "Fetching valid contact properties for your location...",
        "timestamp": asyncio.get_event_loop().time(),
        "disable_input": True
    })
    
    success, valid_properties, formatted_properties = await fetch_contact_properties_for_validation(location_id, credentials)
    
    if not success or not valid_properties:
        # Use common fallback properties if fetch fails
        formatted_properties = """  - first_name
  - last_name
  - email
  - mobile_phone_number
  - city
  - state
  - postal_code
  - country
  - birth_date
  - gender
  - marketing_email_subscribed
  - active_membership
  - marketing_text_message_subscribed"""
        valid_properties = [
            "first_name", "last_name", "email", "mobile_phone_number",
            "city", "state", "postal_code", "country", "birth_date", "gender",
            "marketing_email_subscribed", "marketing_text_message_subscribed", "active_membership"
        ]
        print(f"Warning: Could not fetch contact properties. Using fallback list.")
    else:
        print(f"Fetched {len(valid_properties)} contact properties for location {location_id}")
    
    await send_message({
        "type": "assistant_thinking",
        "message": "Generating smart list query from your audience description...",
        "timestamp": asyncio.get_event_loop().time(),
        "disable_input": True
    })
    
    try:
        from ..prompts import FREDQL_GENERATION_TEMPLATE
        from ..utils.location_utils import format_location_context
        from ..constants.interaction_types import validate_interaction_types
        import json
        
        # Format location context
        location_context = format_location_context(location)
        
        # Prepare contact properties for prompt
        contact_properties_text = formatted_properties if formatted_properties else "Contact properties not available - proceed with caution"
        
        # Generate FredQL using LLM
        chain = FREDQL_GENERATION_TEMPLATE | llm
        response = chain.invoke({
            "audience_description": audience_description,
            "location_context": location_context,
            "contact_properties": contact_properties_text
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
            
            # Extract the actual query if wrapped in result object
            if isinstance(fredql_query, dict) and "fredql_query" in fredql_query:
                fredql_query = fredql_query["fredql_query"]
            
            # Validate interaction types in the generated FredQL (log warnings only)
            is_valid, invalid_types = validate_interaction_types(fredql_query)
            if not is_valid:
                # Continue anyway - user can fix in review loop
                pass
            
            # Validate contact properties (log warnings only)
            if valid_properties:
                props_valid, invalid_props = validate_contact_properties_in_fredql(fredql_query, valid_properties)
                if not props_valid:
                    # Continue anyway - user can fix in review loop
                    pass
            
            # FredQL generated successfully - proceed directly to creation
            
            await send_message({
                "type": "assistant_thinking",
                "message": "Creating smart list...",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": True
            })
            
            return {
                "fredql_query": fredql_query,
                "current_step": "create_smart_list"
            }
            
        except json.JSONDecodeError as e:
            # If parsing fails, show error and end
            print(f"Error: Failed to parse LLM response as JSON: {e}")
            await send_message({
                "type": "error",
                "message": f"I had trouble generating a valid smart list query. Please try rephrasing your audience description or start over.",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            
            return {
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


async def handle_manual_list_name_ws(state: CampaignState, send_message: Callable) -> dict:
    """
    Handle user providing a manually created smart list name
    
    Args:
        state: Current campaign state
        send_message: Function to send messages via WebSocket
    
    Returns:
        Updated state with manual list name
    """
    # Generate unique question ID
    question_id = f"manual_list_name_{asyncio.get_event_loop().time()}"
    
    # Get error details if available
    last_error = state.get("last_error", "")
    fredql_query = state.get("fredql_query", [])
    
    import json
    tried_fredql_str = json.dumps(fredql_query, indent=2) if fredql_query else "N/A"
    
    message = f"⚠️ I've tried creating the smart list 3 times but couldn't get it to work.\n\n"
    if last_error:
        message += f"**Last error:** {last_error}\n\n"
    if fredql_query:
        message += f"**Filters I tried:**\n```json\n{tried_fredql_str}\n```\n\n"
    message += "Please create the smart list manually in the UI and share its name with me so we can continue."
    
    # Send question to user
    await send_message({
        "type": "question",
        "message": message,
        "question_id": question_id,
        "timestamp": asyncio.get_event_loop().time(),
        "disable_input": False
    })
    
    # Wait for list name
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    pending_responses[question_id] = future
    list_name = await future
    
    if list_name and list_name.strip():
        await send_message({
            "type": "system",
            "message": f"✓ I'll use the smart list: {list_name.strip()}",
            "timestamp": asyncio.get_event_loop().time()
        })
        return {
            "smart_list_name": list_name.strip(),
            "create_new_list": False,
            "manual_list": True,
            "current_step": "end_for_now"
        }
    else:
        await send_message({
            "type": "system",
            "message": "Campaign creation cancelled - no list name provided.",
            "timestamp": asyncio.get_event_loop().time()
        })
        return {
            "current_step": "cancelled"
        }


async def confirm_create_smart_list_ws(state: CampaignState, send_message: Callable) -> dict:
    """
    Ask user to confirm creating the smart list with generated FredQL
    
    Args:
        state: Current campaign state
        send_message: Function to send messages via WebSocket
    
    Returns:
        Updated state with user's decision
    """
    await send_message({
        "type": "confirmation",
        "message": "Would you like me to create this smart list now?",
        "question_id": "confirm_create",
        "timestamp": asyncio.get_event_loop().time()
    })
    
    # Wait for confirmation
    future = asyncio.Future()
    pending_responses["confirm_create"] = future
    response = await future
    
    if response and response.lower() in ['yes', 'y', 'ok', 'sure', 'proceed', 'create']:
        await send_message({
            "type": "system",
            "message": "✓ Creating smart list...",
            "timestamp": asyncio.get_event_loop().time()
        })
        return {
            "current_step": "create_smart_list"
        }
    else:
        await send_message({
            "type": "system",
            "message": "Smart list creation cancelled. You can use the FredQL query above to create it manually later.",
            "timestamp": asyncio.get_event_loop().time()
        })
        return {
            "current_step": "end_for_now"
        }


async def create_smart_list_ws(state: CampaignState, send_message: Callable, credentials: dict = None) -> dict:
    """
    Create a new smart list using the generated FredQL query
    
    Args:
        state: Current campaign state
        send_message: Function to send messages via WebSocket
        credentials: API credentials from client
    
    Returns:
        Updated state with created smart list ID and name
    """
    location_id = state.get("location_id")
    fredql_query = state.get("fredql_query")
    audience_description = state.get("audience", "")
    
    if not location_id or not fredql_query:
        # If we're in a retry flow and got empty FredQL, try again
        if state.get("creation_attempts", 0) > 0:
            creation_attempts = state.get("creation_attempts", 0) + 1
            
            if creation_attempts >= 3:
                await send_message({
                    "type": "error",
                    "message": "After 3 attempts, I couldn't generate valid filters. Please create the smart list manually and share its name.",
                    "timestamp": asyncio.get_event_loop().time(),
                    "disable_input": False
                })
                return {
                    "creation_attempts": creation_attempts,
                    "current_step": "awaiting_manual_list_name"
                }
            
            return {
                "creation_attempts": creation_attempts,
                "error_details_message": "⚠️ The last description resulted in empty filters.\n\nPlease provide a COMPLETE audience description (not just modifications).\n\nExample: 'Female customers in California who visited in the last 30 days'",
                "current_step": "retry_smart_list_creation"
            }
        
        await send_message({
            "type": "error",
            "message": "Missing location ID or FredQL query. Cannot create smart list.",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": False
        })
        return {
            "current_step": "end_for_now"
        }
    
    await send_message({
        "type": "assistant_thinking",
        "message": "Creating smart list...",
        "timestamp": asyncio.get_event_loop().time(),
        "disable_input": True
    })
    
    try:
        from contacts_mcp import create_smart_list
        import json
        from datetime import datetime
        
        # Use the smart list name from state if available (generated during clarifications)
        # Otherwise, generate a short name from audience description
        display_name = state.get("smart_list_name", "")
        
        if not display_name:
            # Fallback: Take first few words from audience description
            words = audience_description.split()[:4]
            short_desc = " ".join(words).capitalize()
            display_name = f"AI - {short_desc}"
        
        # Ensure fredql_query is a list (not a string)
        if isinstance(fredql_query, str):
            try:
                fredql_query = json.loads(fredql_query)
            except json.JSONDecodeError:
                await send_message({
                    "type": "error",
                    "message": "Invalid FredQL query format. Cannot create smart list.",
                    "timestamp": asyncio.get_event_loop().time(),
                    "disable_input": False
                })
                return {
                    "current_step": "end_for_now"
                }
        
        # Get credentials
        credentials = credentials or {}
        
        # Create the smart list
        result = await create_smart_list(
            location_id=location_id,
            display_name=display_name,
            filters=fredql_query,
            api_key=credentials.get("api_key"),
            bearer_token=credentials.get("bearer_token"),
            api_url=credentials.get("api_url")
        )
        
        if "error" in result:
            error_message = result.get('message', 'Unknown error')
            status_code = result.get('status_code', 0)
            
            # Check if it's a 422 validation error
            if status_code == 422:
                creation_attempts = state.get("creation_attempts", 0) + 1
                
                # Format the FredQL for display
                import json
                tried_fredql_str = json.dumps(fredql_query, indent=2)
                
                # If we've tried 3 times, ask for manual creation
                if creation_attempts >= 3:
                    return {
                        "creation_attempts": creation_attempts,
                        "last_error": error_message,
                        "fredql_query": fredql_query,
                        "current_step": "awaiting_manual_list_name"
                    }
                
                # Otherwise, ask for more details to retry
                return {
                    "creation_attempts": creation_attempts,
                    "last_error": error_message,
                    "fredql_query": fredql_query,
                    "error_details_message": f"⚠️ The backend rejected the smart list filters (attempt {creation_attempts}/3).\n\n**Error:** {error_message}\n\n**Filters I tried:**\n```json\n{tried_fredql_str}\n```",
                    "current_step": "retry_smart_list_creation"
                }
            else:
                # Other errors - just fail
                await send_message({
                    "type": "error",
                    "message": f"Failed to create smart list: {error_message}",
                    "timestamp": asyncio.get_event_loop().time(),
                    "disable_input": False
                })
                return {
                    "current_step": "end_for_now"
                }
        
        # Extract smart list details
        smart_list_data = result.get("data", {})
        smart_list_id = smart_list_data.get("id", "")
        # Use display_name from attributes, fallback to the one we sent
        smart_list_name = smart_list_data.get("attributes", {}).get("display_name", display_name)
        
        await send_message({
            "type": "assistant",
            "message": f"✓ Smart list created successfully!\n\n**Name:** {smart_list_name}",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": False
        })
        
        # Fetch contact lists and select the newly created one
        await send_message({
            "type": "ui_action",
            "action": "fetch_and_select_list",
            "payload": {
                "listId": smart_list_id,
                "openEditPanel": True
            },
            "timestamp": asyncio.get_event_loop().time()
        })
        
        return {
            "smart_list_id": smart_list_id,
            "smart_list_name": smart_list_name,
            "create_new_list": True,
            "creation_attempts": 0,  # Reset counter on success
            "current_step": "review_smart_list"
        }
        
    except ImportError:
        await send_message({
            "type": "error",
            "message": "MCP tools not available. Cannot create smart list.",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": False
        })
        return {
            "current_step": "end_for_now"
        }
    except Exception as e:
        await send_message({
            "type": "error",
            "message": f"Error creating smart list: {str(e)}",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": False
        })
        return {
            "current_step": "end_for_now"
        }

