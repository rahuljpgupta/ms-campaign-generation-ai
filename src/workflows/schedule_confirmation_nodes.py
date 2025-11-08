"""
Nodes for schedule confirmation and campaign scheduling workflow
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


async def confirm_schedule_ws(state: CampaignState, send_message: Callable) -> dict:
    """
    Ask user to confirm the schedule date/time or request modifications.
    """
    schedule = state.get("datetime", "")
    campaign_name = state.get("campaign_name", "your campaign")
    smart_list_name = state.get("smart_list_name", "")
    smart_list_display = state.get("smart_list_display", smart_list_name)
    
    # Build audience description (use display_name for UI)
    if smart_list_display:
        audience_text = f"**Audience:** {smart_list_display}"
    else:
        audience_text = "**Audience:** All customers"
    
    message = f"**Campaign:** {campaign_name}\n\n{audience_text}\n\n**Scheduled for:** {schedule}\n\nPlease confirm:\n• Type any changes to the schedule\n• Or reply with **\"yes\"**, **\"confirm\"**, or **\"schedule it\"** to proceed"
    
    # Wait for user response with a unique question ID
    question_id = f"confirm_schedule_{asyncio.get_event_loop().time()}"
    
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
    if response_lower in ["yes", "confirm", "schedule it", "schedule", "looks good", "perfect", "done", "ok", "okay", "go ahead", "good"]:
        return {
            "current_step": "schedule_campaign"
        }
    else:
        # User wants to modify schedule
        return {
            "schedule_feedback": response,
            "current_step": "process_schedule_changes"
        }


async def process_schedule_changes_ws(state: CampaignState, llm, send_message: Callable) -> dict:
    """
    Process user's requested changes to the schedule.
    """
    schedule_feedback = state.get("schedule_feedback", "")
    current_schedule = state.get("datetime", "")
    location = state.get("location", {})
    location_timezone = location.get("timezone", "Asia/Kolkata")
    
    await send_message({
        "type": "assistant_thinking",
        "message": "Updating the schedule based on your feedback...",
        "timestamp": asyncio.get_event_loop().time(),
        "disable_input": True
    })
    
    try:
        from langchain_core.prompts import ChatPromptTemplate
        
        # Create a prompt to parse the new schedule
        schedule_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a schedule parsing assistant. 

CURRENT SCHEDULE: {current_schedule}

LOCATION TIMEZONE: {location_timezone}

USER'S CHANGE REQUEST: {schedule_feedback}

Parse the user's request and provide the updated schedule datetime.
Return ONLY the new datetime in ISO 8601 format with timezone offset.

FORMAT: YYYY-MM-DDTHH:MM:SS+TZ:TZ
EXAMPLE: 2025-11-28T14:15:00+05:30

Use the location's timezone offset from the LOCATION TIMEZONE field above.
Return ONLY the datetime string in this exact format, no explanations or additional text."""),
            ("human", "Parse the schedule change now.")
        ])
        
        # Get updated schedule from LLM
        messages = schedule_prompt.format_messages(
            current_schedule=current_schedule,
            schedule_feedback=schedule_feedback,
            location_timezone=location_timezone
        )
        response = await llm.ainvoke(messages)
        updated_schedule = response.content.strip()
        
        if not updated_schedule:
            await send_message({
                "type": "error",
                "message": "Failed to parse new schedule. Please try rephrasing your request.",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            return {
                "current_step": "confirm_schedule"
            }
        
        # Success - update state and go back to confirmation
        await send_message({
            "type": "assistant",
            "message": f"✓ Schedule updated to: **{updated_schedule}**",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": False
        })
        
        return {
            "datetime": updated_schedule,
            "current_step": "confirm_schedule"
        }
        
    except Exception as e:
        await send_message({
            "type": "error",
            "message": f"Error processing schedule changes: {str(e)}",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": False
        })
        return {
            "current_step": "confirm_schedule"
        }


async def schedule_campaign_ws(state: CampaignState, send_message: Callable, credentials: dict = None) -> dict:
    """
    Schedule the campaign by calling the API.
    """
    campaign_id = state.get("campaign_id", "")
    location_id = state.get("location_id", "")
    schedule = state.get("datetime", "")
    smart_list_name = state.get("smart_list_name", "")
    campaign_name = state.get("campaign_name", "")
    subject_line = state.get("subject_line", "")
    
    await send_message({
        "type": "assistant_thinking",
        "message": "Scheduling your campaign...",
        "timestamp": asyncio.get_event_loop().time(),
        "disable_input": True
    })
    
    try:
        from src.mcp.campaigns_mcp import schedule_campaign
        from dateutil import parser
        
        # Parse the datetime string to ISO 8601 format
        try:
            dt = parser.parse(schedule)
            send_at_iso = dt.isoformat()
        except Exception as e:
            await send_message({
                "type": "error",
                "message": f"Invalid date/time format: {schedule}. Please provide a valid date and time.",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            return {
                "current_step": "confirm_schedule"
            }
        
        # Schedule the campaign
        # Note: API expects contact list display names (not IDs) and status='scheduled'
        # If smart_list_name is empty, use empty array [] to target all customers
        credentials = credentials or {}
        contact_list_names = [smart_list_name] if smart_list_name else []
        
        schedule_result = await schedule_campaign(
            location_id,
            campaign_id,
            campaign_name,
            subject_line,
            send_at_iso,
            contact_list_names,  # contact_list_names as array of display names (empty for all customers)
            api_key=credentials.get("api_key"),
            bearer_token=credentials.get("bearer_token"),
            api_url=credentials.get("api_url")
        )
        
        if "error" in schedule_result:
            error_message = schedule_result.get("message", "Unknown error")
            await send_message({
                "type": "error",
                "message": f"Failed to schedule campaign: {error_message}",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            return {
                "current_step": "confirm_schedule"
            }
        
        # Success!
        await send_message({
            "type": "assistant",
            "message": f"🎉 Success! **{campaign_name}** has been scheduled for **{schedule}**.\n\nYour campaign is ready to go!",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": False
        })
        
        # Navigate to campaigns page
        await send_message({
            "type": "ui_action",
            "action": "navigate",
            "payload": {
                "path": f"/locations/{location_id}/campaigns"
            },
            "timestamp": asyncio.get_event_loop().time()
        })
        
        return {
            "schedule_confirmed": True,
            "send_at": send_at_iso,
            "current_step": "completed"
        }
        
    except Exception as e:
        await send_message({
            "type": "error",
            "message": f"Error scheduling campaign: {str(e)}",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": False
        })
        return {
            "current_step": "confirm_schedule"
        }

