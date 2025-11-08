"""
Nodes for smart list review and update workflow
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


async def ask_for_review_ws(state: CampaignState, send_message: Callable) -> dict:
    """
    Ask user to review the smart list and provide feedback or confirm.
    """
    smart_list_name = state.get("smart_list_name", "Unknown List")
    smart_list_display = state.get("smart_list_display", smart_list_name)
    smart_list_id = state.get("smart_list_id", "")
    creation_attempts = state.get("creation_attempts", 0)
    
    # Use display_name for showing to user, fallback to name if not available
    display_text = smart_list_display if smart_list_display and smart_list_display != smart_list_id else "your smart list"
    
    # First time or after update
    if creation_attempts == 0:
        message = f"I've created the smart list **{display_text}**.\n\nPlease review it and let me know:\n• Type any changes you'd like to make\n• Or reply with **\"yes\"**, **\"good\"**, or **\"go ahead\"** to continue"
    else:
        message = f"Smart list **{display_text}** has been updated.\n\nPlease review the changes:\n• Type any additional changes\n• Or reply with **\"yes\"**, **\"good\"**, or **\"go ahead\"** to continue"
    
    # Wait for user response with a unique question ID
    question_id = f"review_smart_list_{asyncio.get_event_loop().time()}"
    
    await send_message({
        "type": "question",
        "message": message,
        "question_id": question_id,
        "timestamp": asyncio.get_event_loop().time(),
        "disable_input": False
    })
    
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    pending_responses[question_id] = future
    
    response = await future
    response_lower = response.lower().strip()
    
    # Check if user wants to proceed or make changes
    if response_lower in ["yes", "good", "go ahead", "looks good", "perfect", "done", "ok", "okay"]:
        # Close the edit smart list panel before proceeding to campaign creation
        await send_message({
            "type": "ui_action",
            "action": "close_action_panel",
            "payload": {},
            "timestamp": asyncio.get_event_loop().time()
        })
        
        return {
            "current_step": "create_campaign"
        }
    else:
        # User wants to make changes
        return {
            "user_feedback": response,
            "current_step": "process_smart_list_changes"
        }


async def process_smart_list_changes_ws(state: CampaignState, llm, send_message: Callable, location: dict = None, credentials: dict = None) -> dict:
    """
    Process user's requested changes to the smart list and update it.
    """
    user_feedback = state.get("user_feedback", "")
    smart_list_id = state.get("smart_list_id", "")
    location_id = state.get("location_id", "")
    current_display_name = state.get("smart_list_name", "")
    current_fredql = state.get("fredql_query", [])
    audience_description = state.get("audience", "")
    
    await send_message({
        "type": "assistant_thinking",
        "message": "Updating the smart list based on your feedback...",
        "timestamp": asyncio.get_event_loop().time(),
        "disable_input": True
    })
    
    try:
        from ..prompts import FREDQL_GENERATION_TEMPLATE
        from ..utils.location_utils import format_location_context
        from .websocket_nodes import fetch_contact_properties_for_validation, validate_contact_properties_in_fredql
        from ..constants.interaction_types import VALID_INTERACTION_TYPES, validate_interaction_types
        import json
        
        # Fetch contact properties for validation
        success, valid_properties, formatted_properties = await fetch_contact_properties_for_validation(
            location_id, credentials
        )
        
        # Format location context
        location_context = format_location_context(location)
        
        # Prepare contact properties text
        contact_properties_text = formatted_properties if formatted_properties else "Contact properties not available"
        
        # Escape the current FredQL JSON for use in ChatPromptTemplate
        # Replace { with {{ and } with }} to escape them
        current_fredql_str = json.dumps(current_fredql, indent=2)
        escaped_fredql = current_fredql_str.replace('{', '{{').replace('}', '}}')
        
        # Create an enhanced prompt that includes current state and requested changes
        # Note: Double curly braces {{{{ }}}} escape to single braces in f-strings
        # Convert all interaction types to strings to avoid join errors
        valid_types_str = ', '.join(str(t) for t in VALID_INTERACTION_TYPES)
        
        update_prompt = f"""You are updating an existing smart list based on user feedback.

Current Smart List:
- Name: {current_display_name}
- Audience: {audience_description}
- Current FredQL: {escaped_fredql}

User's Requested Changes:
{user_feedback}

Update the smart list according to the user's feedback. Generate the updated FredQL query.

CRITICAL RULES:
- If removing a filter, COMPLETELY REMOVE IT from the array - do not leave empty objects
- If adding a filter, include ALL required fields (filter_type, operator, etc.)
- For interaction filters: MUST have filter_type="interaction", operator="has_interaction" or "has_no_interaction", and interaction_type
- For contact_property filters: MUST have filter_type="contact_property", property_name, operator, and value
- Use ONLY valid interaction types from this list: {valid_types_str}
- Use ONLY valid contact properties from the provided list
- Return a complete, valid FredQL array with NO empty or incomplete filters

EXAMPLES:
- To remove a filter: Remove it entirely from the array
- Original: [[{{{{"filter_type":"contact_property",...}}}}, {{{{"filter_type":"interaction",...}}}}]]
- After removing interaction: [[{{{{"filter_type":"contact_property",...}}}}]]

Return ONLY valid JSON in this format:
{{{{
    "fredql_query": [[{{{{...}}}}]],
    "display_name": "updated name if changed, otherwise keep the same",
    "explanation": "brief explanation of changes made"
}}}}

If the requested changes are not possible, return:
{{{{
    "error": "Cannot make requested changes",
    "reason": "explanation why"
}}}}"""
        
        # Generate updated FredQL using LLM
        from langchain_core.prompts import ChatPromptTemplate
        update_template = ChatPromptTemplate.from_messages([
            ("system", update_prompt),
            ("human", "Update the smart list based on the user's feedback. Return ONLY valid JSON, no other text.")
        ])
        
        chain = update_template | llm
        response = chain.invoke({
            "location_context": location_context,
            "contact_properties": contact_properties_text
        })
        
        # Parse the LLM response
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # Clean response (remove markdown code blocks if present)
        response_text = response_text.strip()
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            # Find first line that's not a language tag
            start_idx = 1
            if lines[1].lower() in ['json', 'javascript', 'js']:
                start_idx = 2
            response_text = '\n'.join(lines[start_idx:-1])  # Remove markdown wrapper
            response_text = response_text.strip()
        
        if not response_text:
            await send_message({
                "type": "assistant",
                "message": "⚠️ I couldn't generate a valid update. Please try rephrasing your change request more specifically.",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            return {
                "current_step": "review_smart_list"
            }
        
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            await send_message({
                "type": "assistant",
                "message": f"⚠️ I had trouble understanding how to apply your changes. Please try rephrasing your request more clearly.\n\nFor example:\n• 'Change gender filter to female'\n• 'Remove the visited filter'\n• 'Add a filter for customers in California'",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            return {
                "current_step": "review_smart_list"
            }
        
        result = result
        
        # Check for errors
        if "error" in result:
            await send_message({
                "type": "assistant",
                "message": f"⚠️ {result['reason']}\n\nPlease try rephrasing your request or make a different change.",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            return {
                "current_step": "review_smart_list"
            }
        
        # Validate the updated FredQL
        updated_fredql = result.get("fredql_query", [])
        updated_name = result.get("display_name", current_display_name)
        updated_display = updated_name  # Initialize with the same value
        explanation = result.get("explanation", "Smart list updated")
        
        # Clean the FredQL - remove any empty or incomplete filters
        cleaned_fredql = []
        for or_group in updated_fredql:
            if isinstance(or_group, list):
                cleaned_group = []
                for filter_obj in or_group:
                    # Only keep complete filters
                    if isinstance(filter_obj, dict) and filter_obj.get("filter_type"):
                        # Validate interaction filters
                        if filter_obj.get("filter_type") == "interaction":
                            if filter_obj.get("operator") and filter_obj.get("interaction_type"):
                                cleaned_group.append(filter_obj)
                        # Validate contact_property filters
                        elif filter_obj.get("filter_type") == "contact_property":
                            if filter_obj.get("property_name") and filter_obj.get("operator"):
                                cleaned_group.append(filter_obj)
                        # Keep other filter types if they look valid
                        elif len(filter_obj) > 1:
                            cleaned_group.append(filter_obj)
                
                if cleaned_group:  # Only add non-empty groups
                    cleaned_fredql.append(cleaned_group)
        
        # If cleaning resulted in empty query, show error
        if not cleaned_fredql:
            await send_message({
                "type": "assistant",
                "message": "⚠️ The updated query would result in an empty filter list. Please provide different criteria.",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            return {
                "current_step": "review_smart_list"
            }
        
        # Use cleaned FredQL
        updated_fredql = cleaned_fredql
        
        # Validate interaction types
        is_valid, invalid_types = validate_interaction_types(updated_fredql)
        if not is_valid and invalid_types:
            # Convert all invalid types to strings
            invalid_types_str = ', '.join(str(t) for t in invalid_types)
            await send_message({
                "type": "assistant",
                "message": f"⚠️ The updated query uses invalid interaction types: {invalid_types_str}\n\nPlease try different criteria.",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            return {
                "current_step": "review_smart_list"
            }
        
        # Validate contact properties
        if success and valid_properties:
            props_valid, invalid_props = validate_contact_properties_in_fredql(updated_fredql, valid_properties)
            if not props_valid and invalid_props:
                # Convert all invalid properties to strings
                invalid_props_str = ', '.join(str(p) for p in invalid_props)
                await send_message({
                    "type": "assistant",
                    "message": f"⚠️ The updated query uses invalid contact properties: {invalid_props_str}\n\nPlease try different criteria.",
                    "timestamp": asyncio.get_event_loop().time(),
                    "disable_input": False
                })
                return {
                    "current_step": "review_smart_list"
                }
        
        # Update the smart list via MCP
        try:
            from src.mcp.contacts_mcp import update_smart_list
        except ImportError:
            await send_message({
                "type": "error",
                "message": "MCP tools not available. Cannot update smart list.",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            return {
                "current_step": "review_smart_list"
            }
        
        credentials = credentials or {}
        update_result = await update_smart_list(
            location_id=location_id,
            list_id=smart_list_id,
            display_name=updated_name,
            filters=updated_fredql,
            api_key=credentials.get("api_key"),
            bearer_token=credentials.get("bearer_token"),
            api_url=credentials.get("api_url")
        )
        
        if "error" in update_result:
            await send_message({
                "type": "error",
                "message": f"Failed to update smart list: {update_result.get('message', 'Unknown error')}",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            return {
                "current_step": "review_smart_list"
            }
        
        # Extract the updated name from the API response
        # Use 'name' attribute (not 'display_name') as it's required for campaign scheduling API
        updated_data = update_result.get("data", {})
        if isinstance(updated_data, dict):
            attrs = updated_data.get("attributes", {})
            response_name = attrs.get("name", updated_name)
            response_display = attrs.get("display_name") or response_name
            if response_name:
                updated_name = response_name
                updated_display = response_display
        
        # Success! Refresh the UI to show updated list
        await send_message({
            "type": "assistant",
            "message": f"✓ {explanation}",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": False
        })
        
        # Close the panel first, then fetch and reopen to force refresh
        await send_message({
            "type": "ui_action",
            "action": "close_action_panel",
            "payload": {},
            "timestamp": asyncio.get_event_loop().time()
        })
        
        # Small delay to ensure panel closes
        await asyncio.sleep(0.2)
        
        # Trigger UI refresh to show updated filters
        await send_message({
            "type": "ui_action",
            "action": "fetch_and_select_list",
            "payload": {
                "listId": smart_list_id,
                "openEditPanel": True
            },
            "timestamp": asyncio.get_event_loop().time()
        })
        
        # Update state and go back to review
        return {
            "smart_list_name": updated_name,
            "smart_list_display": updated_display,
            "fredql_query": updated_fredql,
            "current_step": "review_smart_list"
        }
        
    except Exception as e:
        await send_message({
            "type": "error",
            "message": f"Error processing changes: {str(e)}\n\nPlease try a different change or reply with **\"yes\"** to continue.",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": False
        })
        return {
            "current_step": "review_smart_list"
        }

