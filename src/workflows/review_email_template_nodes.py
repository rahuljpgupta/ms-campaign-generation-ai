"""
Nodes for email template review and update workflow
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


async def ask_for_email_review_ws(state: CampaignState, send_message: Callable) -> dict:
    """
    Ask user to review the email template and provide feedback or confirm.
    """
    campaign_name = state.get("campaign_name", "your campaign")
    update_count = state.get("email_update_count", 0)
    
    # First time or after update
    if update_count == 0:
        message = f"✅ Email template created for **{campaign_name}**!\n\nThe HTML editor is now open for you to review the template.\n\nPlease review it and let me know:\n• Type any changes you'd like to make to the content\n• Or reply with **\"yes\"**, **\"good\"**, or **\"go ahead\"** to finish"
    else:
        message = f"Email template has been updated.\n\nPlease review the changes in the HTML editor:\n• Type any additional changes\n• Or reply with **\"yes\"**, **\"good\"**, or **\"go ahead\"** to finish"
    
    # Wait for user response with a unique question ID
    question_id = f"review_email_{asyncio.get_event_loop().time()}"
    
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
        return {
            "current_step": "confirm_schedule"
        }
    else:
        # User wants to make changes
        return {
            "user_feedback": response,
            "current_step": "process_email_changes"
        }


async def process_email_changes_ws(state: CampaignState, llm, send_message: Callable, location: dict = None, credentials: dict = None) -> dict:
    """
    Process user's requested changes to the email template and update it.
    """
    user_feedback = state.get("user_feedback", "")
    email_document_id = state.get("email_document_id", "")
    location_id = state.get("location_id", "")
    current_html = state.get("email_html", "")
    campaign_name = state.get("campaign_name", "")
    subject_line = state.get("subject_line", "")
    update_count = state.get("email_update_count", 0)
    
    await send_message({
        "type": "assistant_thinking",
        "message": "Updating the email template based on your feedback...",
        "timestamp": asyncio.get_event_loop().time(),
        "disable_input": True
    })
    
    try:
        from ..prompts import EMAIL_UPDATE_PROMPT
        from ..utils.location_utils import format_location_context
        import json
        
        # Format location context
        location = location or state.get("location", {})
        location_context = format_location_context(location)
        business_name = location.get("name", "Our Business")
        
        # Format merge tags for prompt
        merge_tags_list = state.get("merge_tags", [])
        print(f"[Email Update] Merge tags in state: {len(merge_tags_list)} tags")
        
        merge_tag_items = []
        for tag in merge_tags_list:
            attrs = tag.get("attributes", {})
            tag_value = attrs.get("merge_tag_value", "")
            display_name = attrs.get("display_name", tag_value)
            preview_value = attrs.get("preview_value", "")
            hidden = attrs.get("hidden", False)
            
            # Skip hidden tags
            if hidden:
                continue
            
            if tag_value:
                tag_item = f"- **{{{{{tag_value}}}}}** ({display_name})"
                if preview_value:
                    tag_item += f" - Example: {preview_value}"
                merge_tag_items.append(tag_item)
        
        merge_tags_text = "\n".join(merge_tag_items) if merge_tag_items else "No merge tags available."
        print(f"[Email Update] Formatted {len(merge_tag_items)} tags for LLM prompt")
        if merge_tag_items:
            print(f"[Email Update] First 3 merge tags:\n{chr(10).join(merge_tag_items[:3])}")
        print(f"[Email Update] User feedback: {user_feedback}")
        
        # Prepare prompt for LLM
        update_prompt = EMAIL_UPDATE_PROMPT.format_messages(
            business_name=business_name,
            location_context=location_context,
            merge_tags=merge_tags_text,
            current_html=current_html,
            user_feedback=user_feedback
        )
        
        # Get updated HTML from LLM
        response = await llm.ainvoke(update_prompt)
        response_text = response.content.strip()
        
        # Clean up markdown if LLM added it
        if response_text.startswith("```html"):
            response_text = response_text[7:]  # Remove ```html
        if response_text.startswith("```"):
            response_text = response_text[3:]  # Remove ```
        if response_text.endswith("```"):
            response_text = response_text[:-3]  # Remove closing ```
        response_text = response_text.strip()
        
        updated_html = response_text
        
        if not updated_html:
            await send_message({
                "type": "error",
                "message": "Failed to generate updated template. Please try rephrasing your request.",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            return {
                "email_update_count": update_count,
                "current_step": "review_email_template"
            }
        
        # Update the email document via API
        from src.mcp.campaigns_mcp import update_email_document
        
        credentials = credentials or {}
        update_result = await update_email_document(
            location_id,
            email_document_id,
            updated_html,
            document="{}",
            api_key=credentials.get("api_key"),
            bearer_token=credentials.get("bearer_token"),
            api_url=credentials.get("api_url")
        )
        
        if "error" in update_result:
            error_message = update_result.get("message", "Unknown error")
            await send_message({
                "type": "error",
                "message": f"Failed to update email template: {error_message}",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            return {
                "email_update_count": update_count,
                "current_step": "review_email_template"
            }
        
        # Success - update state and refresh the email editor
        await send_message({
            "type": "assistant",
            "message": "✓ Email template updated successfully!",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": False
        })
        
        # Refresh the email editor to show updated content (without full page reload)
        await send_message({
            "type": "ui_action",
            "action": "refresh_email_document",
            "payload": {
                "emailDocumentId": email_document_id
            },
            "timestamp": asyncio.get_event_loop().time()
        })
        
        return {
            "email_html": updated_html,
            "email_update_count": update_count + 1,
            "current_step": "review_email_template"
        }
        
    except Exception as e:
        await send_message({
            "type": "error",
            "message": f"Error processing changes: {str(e)}",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": False
        })
        return {
            "email_update_count": update_count,
            "current_step": "review_email_template"
        }

