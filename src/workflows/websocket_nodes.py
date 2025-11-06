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
        from src.mcp.contacts_mcp import get_contact_properties
        
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


async def fetch_and_merge_interaction_types(location_id: str, credentials: dict = None) -> tuple[bool, list[str], str]:
    """
    Fetch interaction types from API and merge with hardcoded defaults.
    
    Args:
        location_id: Location ID
        credentials: API credentials
    
    Returns:
        Tuple of (success, interaction_types_list, formatted_types_string)
    """
    from ..constants.interaction_types import VALID_INTERACTION_TYPES
    
    # Start with hardcoded defaults
    all_types = set(VALID_INTERACTION_TYPES)
    
    try:
        from src.mcp.contacts_mcp import get_interaction_types
        
        credentials = credentials or {}
        result = await get_interaction_types(
            location_id,
            api_key=credentials.get("api_key"),
            bearer_token=credentials.get("bearer_token"),
            api_url=credentials.get("api_url")
        )
        
        # If API call succeeds, merge with defaults
        if "error" not in result:
            # Extract interaction type names from API response
            for type_name in result.get("interaction_types", []):
                if type_name:
                    all_types.add(type_name)
        
        # Convert to sorted list
        merged_types = sorted(list(all_types))
        
        # Format for prompt (bullet list like contact properties)
        formatted = "\n".join([f"- {type_name}" for type_name in merged_types])
        
        return True, merged_types, formatted
    except Exception as e:
        # If fetch fails, use hardcoded defaults
        merged_types = sorted(list(all_types))
        formatted = "\n".join([f"- {type_name}" for type_name in merged_types])
        return True, merged_types, formatted


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
    
    # Fetch and merge interaction types
    _, merged_interaction_types, formatted_interaction_types = await fetch_and_merge_interaction_types(location_id, credentials)
    
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
            "contact_properties": contact_properties_text,
            "interaction_types": formatted_interaction_types
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
            
            # Check if the generated filter is empty [] (all customers/subscribers)
            # Empty filters are valid but cannot be displayed in edit panel
            if isinstance(fredql_query, list) and len(fredql_query) == 0:
                await send_message({
                    "type": "assistant",
                    "message": "Your audience description matches **all customers** (no filters needed).\n\nSince this doesn't require any specific filtering, you can select your entire contact list when setting up the campaign.",
                    "timestamp": asyncio.get_event_loop().time(),
                    "disable_input": False
                })
                
                return {
                    "current_step": "end_for_now"
                }
            
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


async def handle_manual_list_name_ws(state: CampaignState, send_message: Callable, credentials: dict = None) -> dict:
    """
    Handle user providing a manually created smart list name
    
    Args:
        state: Current campaign state
        send_message: Function to send messages via WebSocket
        credentials: API credentials from client
    
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
    
    loop = asyncio.get_running_loop()
    location_id = state.get("location_id")
    credentials = credentials or {}
    
    # Keep asking for the name until we find a match
    while True:
        # Wait for list name
        future = loop.create_future()
        pending_responses[question_id] = future
        list_name = await future
        # Fetch latest contact lists to validate the provided name
        await send_message({
            "type": "assistant_thinking",
            "message": "Searching for the smart list you created...",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": True
        })
        
        try:
            from src.mcp.contacts_mcp import get_existing_smart_lists
            
            result = await get_existing_smart_lists(
                location_id,
                api_key=credentials.get("api_key"),
                bearer_token=credentials.get("bearer_token"),
                api_url=credentials.get("api_url")
            )
            
            if "error" in result:
                await send_message({
                    "type": "error",
                    "message": f"Failed to fetch contact lists: {result.get('message', 'Unknown error')}",
                    "timestamp": asyncio.get_event_loop().time(),
                    "disable_input": False
                })
                return {
                    "current_step": "cancelled"
                }
            
            # Search for matches (case-insensitive)
            search_name = list_name.strip().lower()
            matches = []
            
            for smart_list in result.get("data", []):
                list_id = smart_list.get("id")
                attrs = smart_list.get("attributes", {})
                display_name = attrs.get("display_name", "")
                
                if display_name and search_name in display_name.lower():
                    matches.append({
                        "id": list_id,
                        "name": display_name
                    })
            
            # Handle different scenarios
            if len(matches) == 0:
                # No match found - ask for the name again
                question_id = f"retry_manual_list_name_{asyncio.get_event_loop().time()}"
                
                await send_message({
                    "type": "question",
                    "message": f"❌ I couldn't find any smart list matching **\"{list_name.strip()}\"**.\n\nPlease make sure:\n• The smart list was created successfully\n• The name is spelled correctly\n• You have access to this list\n\nPlease provide the correct smart list name:",
                    "question_id": question_id,
                    "timestamp": asyncio.get_event_loop().time(),
                    "disable_input": False
                })
                # Loop continues to ask again
                continue
            
            elif len(matches) == 1:
                # Exactly one match - auto-select
                selected = matches[0]
                await send_message({
                    "type": "assistant",
                    "message": f"✓ Found your smart list: **{selected['name']}**",
                    "timestamp": asyncio.get_event_loop().time(),
                    "disable_input": False
                })
                return {
                    "smart_list_id": selected["id"],
                    "smart_list_name": selected["name"],
                    "create_new_list": False,
                    "manual_list": True,
                    "current_step": "create_campaign"
                }
            
            else:
                # Multiple matches - ask user to select
                selection_question_id = f"select_manual_list_{asyncio.get_event_loop().time()}"
                
                options = []
                for idx, match in enumerate(matches, 1):
                    options.append({
                        "text": match["name"],
                        "value": match["id"]
                    })
                
                await send_message({
                    "type": "question",
                    "message": "Which one would you like to use?",
                    "question_id": selection_question_id,
                    "options": options,
                    "timestamp": asyncio.get_event_loop().time(),
                    "disable_input": False
                })
                
                # Wait for selection
                selection_future = loop.create_future()
                pending_responses[selection_question_id] = selection_future
                selected_id = await selection_future
                
                # Find the selected smart list
                selected_list = next((m for m in matches if m["id"] == selected_id), None)
                
                if selected_list:
                    await send_message({
                        "type": "assistant",
                        "message": f"✓ Using smart list: **{selected_list['name']}**",
                        "timestamp": asyncio.get_event_loop().time(),
                        "disable_input": False
                    })
                    return {
                        "smart_list_id": selected_list["id"],
                        "smart_list_name": selected_list["name"],
                        "create_new_list": False,
                        "manual_list": True,
                        "current_step": "create_campaign"
                    }
                else:
                    await send_message({
                        "type": "error",
                        "message": "Invalid selection. Campaign creation cancelled.",
                        "timestamp": asyncio.get_event_loop().time(),
                        "disable_input": False
                    })
                    return {
                        "current_step": "cancelled"
                    }
        
        except Exception as e:
            await send_message({
                "type": "error",
                "message": f"Error validating smart list: {str(e)}",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
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
        from src.mcp.contacts_mcp import create_smart_list
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


async def create_campaign_ws(state: CampaignState, llm, send_message: Callable, location: dict = None, credentials: dict = None) -> dict:
    """
    Create campaign and generate email template
    
    Args:
        state: Current campaign state
        llm: Language model instance from workflow
        send_message: Function to send messages via WebSocket
        location: Location context with source platform information
        credentials: API credentials from client
    
    Returns:
        Updated state with campaign ID and email template
    """
    try:
        location_id = state.get("location_id")
        location = location or state.get("location", {})
        campaign_description = state.get("template", "")
        smart_list_name = state.get("smart_list_name", "")
        
        credentials = credentials or {}
        
        # Notify user we're starting campaign creation
        await send_message({
            "type": "assistant_thinking",
            "message": "Creating your campaign and generating email template...",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": True
        })
        
        # Step 1: Fetch social profile links
        from src.mcp.campaigns_mcp import get_social_profile_links
        
        # Extract source platform information from location
        source_platform = location.get("source_platform", "")
        source_location_id = location.get("source_location_id", "")
        source_customer_id = location.get("source_customer_id", "")
        
        social_links_result = await get_social_profile_links(
            source_platform=source_platform,
            source_location_id=source_location_id,
            source_customer_id=source_customer_id,
            api_key=credentials.get("api_key"),
            bearer_token=credentials.get("bearer_token"),
            api_url=credentials.get("api_url")
        )
        
        if "error" in social_links_result:
            await send_message({
                "type": "system",
                "message": "⚠️ Couldn't fetch social profile links, continuing without them.",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            social_links_data = []
        else:
            social_links_data = social_links_result.get("data", [])
        
        # Format social links (only include valid URLs)
        social_links_formatted = []
        for link in social_links_data:
            attrs = link.get("attributes", {})
            platform = attrs.get("platform", "")
            url = attrs.get("url", "")
            if url:
                social_links_formatted.append(f"- {platform}: {url}")
        
        social_links_text = "\n".join(social_links_formatted) if social_links_formatted else "No social profile links available"
        
        # Step 2: Fetch latest 5 campaign emails
        from src.mcp.campaigns_mcp import get_latest_campaign_emails
        
        emails_result = await get_latest_campaign_emails(
            location_id,
            api_key=credentials.get("api_key"),
            bearer_token=credentials.get("bearer_token"),
            api_url=credentials.get("api_url")
        )
        
        if "error" in emails_result:
            await send_message({
                "type": "system",
                "message": "⚠️ Couldn't fetch reference email templates, will create a basic template.",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            reference_templates = "No reference templates available. Create a clean, professional email template."
        else:
            htmls_data = emails_result.get("htmls", [])
            
            # Format reference templates
            template_texts = []
            for idx, email in enumerate(htmls_data, 1):
                html = email.get("html", "")
                campaign_name = email.get("campaign_name", f"Template {idx}")
                subject_line = email.get("subject_line", "")
                
                if html:
                    template_section = f"### Template {idx}: {campaign_name}\n"
                    if subject_line:
                        template_section += f"**Subject Line:** {subject_line}\n"
                    template_section += f"```html\n{html}\n```\n"
                    template_texts.append(template_section)
            
            reference_templates = "\n\n".join(template_texts) if template_texts else "No reference templates available. Create a clean, professional email template."
        
        # Step 3: Generate email template using LLM
        await send_message({
            "type": "assistant_thinking",
            "message": "Generating your email template based on your existing campaigns...",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": True
        })
        
        from src.prompts import EMAIL_TEMPLATE_GENERATION_PROMPT
        from src.utils.location_utils import format_location_context
        
        location_context = format_location_context(location)
        business_name = location.get("name", "Our Business")
        
        # Prepare prompt
        email_prompt = EMAIL_TEMPLATE_GENERATION_PROMPT.format_messages(
            business_name=business_name,
            location_context=location_context,
            social_links=social_links_text,
            campaign_description=campaign_description,
            reference_templates=reference_templates
        )
        
        # Generate email template, subject line, and campaign name
        response = await llm.ainvoke(email_prompt)
        response_text = response.content.strip()
        
        # Clean up markdown if LLM added it
        if response_text.startswith("```json"):
            response_text = response_text[7:]  # Remove ```json
        if response_text.startswith("```"):
            response_text = response_text[3:]  # Remove ```
        if response_text.endswith("```"):
            response_text = response_text[:-3]  # Remove closing ```
        response_text = response_text.strip()
        
        # Parse JSON response
        import json
        try:
            email_data = json.loads(response_text)
            campaign_name = email_data.get("campaign_name", "")
            subject_line = email_data.get("subject_line", "")
            email_html = email_data.get("html", "")
            
            # Fallback to defaults if any field is missing
            if not campaign_name:
                from datetime import datetime
                campaign_name = f"AI - {smart_list_name.replace('AI - ', '')} - {datetime.now().strftime('%b %d, %Y at %I:%M %p')}"
            if not subject_line:
                subject_line = f"News from {business_name}"
            if not email_html:
                await send_message({
                    "type": "error",
                    "message": "Failed to generate email template. Please try again.",
                    "timestamp": asyncio.get_event_loop().time(),
                    "disable_input": False
                })
                return {
                    "current_step": "end_for_now"
                }
        except json.JSONDecodeError as e:
            await send_message({
                "type": "error",
                "message": "Failed to parse email template response. Please try again.",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            return {
                "current_step": "end_for_now"
            }
        
        # Step 4: Create campaign
        from src.mcp.campaigns_mcp import create_campaign
        
        campaign_result = await create_campaign(
            location_id,
            campaign_name,
            subject_line,
            custom_html_template=True,
            api_key=credentials.get("api_key"),
            bearer_token=credentials.get("bearer_token"),
            api_url=credentials.get("api_url")
        )
        
        if "error" in campaign_result:
            await send_message({
                "type": "error",
                "message": f"Failed to create campaign: {campaign_result.get('message', 'Unknown error')}",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            return {
                "current_step": "end_for_now"
            }
        
        campaign_data = campaign_result.get("data", {})
        campaign_id = campaign_data.get("id")
        
        if not campaign_id:
            await send_message({
                "type": "error",
                "message": "Campaign created but couldn't retrieve campaign ID",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            return {
                "current_step": "end_for_now"
            }
        
        # Step 5: Create email document
        from src.mcp.campaigns_mcp import create_email_document
        
        email_doc_result = await create_email_document(
            location_id,
            campaign_id,
            email_html,
            document="{}",
            api_key=credentials.get("api_key"),
            bearer_token=credentials.get("bearer_token"),
            api_url=credentials.get("api_url")
        )
        
        if "error" in email_doc_result:
            await send_message({
                "type": "error",
                "message": f"Campaign created but failed to save email template: {email_doc_result.get('message', 'Unknown error')}",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            return {
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "current_step": "end_for_now"
            }
        
        # Extract email document ID
        email_doc_data = email_doc_result.get("data", {})
        email_document_id = email_doc_data.get("id")
        
        if not email_document_id:
            await send_message({
                "type": "error",
                "message": "Email template saved but couldn't retrieve document ID",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            return {
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "current_step": "end_for_now"
            }
        
        # Success! Navigate to HTML editor
        await send_message({
            "type": "assistant",
            "message": f"✅ Campaign created successfully!\n\n**Campaign:** {campaign_name}\n**Subject Line:** {subject_line}\n**Email template:** Generated and saved\n\nOpening the HTML editor for you to review and customize...",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": False
        })
        
        # Navigate to HTML editor
        await send_message({
            "type": "ui_action",
            "action": "navigate",
            "payload": {
                "path": f"/locations/{location_id}/email_documents/{email_document_id}/html-editor"
            },
            "timestamp": asyncio.get_event_loop().time()
        })
        
        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "subject_line": subject_line,
            "email_document_id": email_document_id,
            "email_html": email_html,
            "current_step": "end_for_now"
        }
        
    except Exception as e:
        await send_message({
            "type": "error",
            "message": f"Error creating campaign: {str(e)}",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": False
        })
        return {
            "current_step": "end_for_now"
        }

