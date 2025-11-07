"""
WebSocket-compatible LangGraph workflow with checkpointing for campaign generation
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from ..models import CampaignState
from ..nodes import parse_prompt, process_clarifications, route_after_clarification_check
from . import websocket_nodes
from . import review_smart_list_nodes
from . import retry_smart_list_nodes
from . import review_email_template_nodes
from . import schedule_confirmation_nodes


def build_websocket_workflow(llm, send_message):
    """
    Build and compile the campaign generation workflow for WebSocket communication
    with checkpointing support for pause/resume functionality.
    
    Args:
        llm: Language model instance for processing
        send_message: Async function to send messages via WebSocket
        
    Returns:
        Compiled workflow graph with checkpointing
    """
    workflow = StateGraph(CampaignState)
    
    # Add nodes - mix of sync LLM nodes and async WebSocket nodes
    workflow.add_node("parse_prompt", lambda state: parse_prompt(state, llm))
    workflow.add_node(
        "ask_clarifications", 
        lambda state: websocket_nodes.ask_clarifications_ws(state, send_message)
    )
    workflow.add_node("process_clarifications", lambda state: process_clarifications(state, llm))
    workflow.add_node(
        "check_smart_lists", 
        lambda state: websocket_nodes.fetch_and_match_smart_lists_wrapper(state, llm)
    )
    workflow.add_node(
        "confirm_smart_list_selection",
        lambda state: websocket_nodes.confirm_smart_list_selection_ws(state, send_message)
    )
    workflow.add_node(
        "confirm_new_list",
        lambda state: websocket_nodes.confirm_new_list_ws(state, send_message)
    )
    workflow.add_node(
        "generate_fredql",
        lambda state: websocket_nodes.generate_smart_list_fredql_ws(state, llm, send_message)
    )
    workflow.add_node(
        "create_smart_list",
        lambda state: websocket_nodes.create_smart_list_ws(state, send_message)
    )
    workflow.add_node(
        "retry_smart_list_creation",
        lambda state: retry_smart_list_nodes.retry_smart_list_creation_ws(state, send_message)
    )
    workflow.add_node(
        "handle_manual_list_name",
        lambda state: websocket_nodes.handle_manual_list_name_ws(state, send_message)
    )
    workflow.add_node(
        "review_smart_list",
        lambda state: review_smart_list_nodes.ask_for_review_ws(state, send_message)
    )
    workflow.add_node(
        "process_smart_list_changes",
        lambda state: review_smart_list_nodes.process_smart_list_changes_ws(state, llm, send_message)
    )
    workflow.add_node(
        "create_campaign",
        lambda state: websocket_nodes.create_campaign_ws(
            state, llm, send_message, 
            location=state.get("location", {}),
            credentials=None  # Credentials not stored in state, passed separately by executor
        )
    )
    workflow.add_node(
        "review_email_template",
        lambda state: review_email_template_nodes.ask_for_email_review_ws(state, send_message)
    )
    workflow.add_node(
        "process_email_changes",
        lambda state: review_email_template_nodes.process_email_changes_ws(state, llm, send_message)
    )
    workflow.add_node(
        "confirm_schedule",
        lambda state: schedule_confirmation_nodes.confirm_schedule_ws(state, send_message)
    )
    workflow.add_node(
        "process_schedule_changes",
        lambda state: schedule_confirmation_nodes.process_schedule_changes_ws(state, llm, send_message)
    )
    workflow.add_node(
        "schedule_campaign",
        lambda state: schedule_confirmation_nodes.schedule_campaign_ws(state, send_message)
    )
    workflow.add_node("end_for_now", lambda state: {"current_step": "completed"})
    
    # Set entry point
    workflow.set_entry_point("parse_prompt")
    
    # Add edges
    workflow.add_conditional_edges(
        "parse_prompt",
        route_after_clarification_check,
        {
            "ask_clarifications": "ask_clarifications",
            "check_smart_lists": "check_smart_lists"
        }
    )
    
    workflow.add_edge("ask_clarifications", "process_clarifications")
    
    workflow.add_conditional_edges(
        "process_clarifications",
        route_after_clarification_check,
        {
            "ask_clarifications": "ask_clarifications",
            "check_smart_lists": "check_smart_lists"
        }
    )
    
    workflow.add_conditional_edges(
        "check_smart_lists",
        lambda state: state.get("current_step", "end_for_now"),
        {
            "confirm_smart_list_selection": "confirm_smart_list_selection",
            "confirm_new_list": "confirm_new_list",
            "end_for_now": "end_for_now"
        }
    )
    
    # After smart list selection/confirmation, route to create campaign
    workflow.add_conditional_edges(
        "confirm_smart_list_selection",
        lambda state: state.get("current_step", "end_for_now"),
        {
            "generate_fredql": "generate_fredql",
            "create_campaign": "create_campaign",
            "end_for_now": "end_for_now"
        }
    )
    
    workflow.add_conditional_edges(
        "confirm_new_list",
        lambda state: state.get("current_step", "end_for_now"),
        {
            "generate_fredql": "generate_fredql",
            "end_for_now": "end_for_now"
        }
    )
    
    # After FredQL generation, create the list
    workflow.add_conditional_edges(
        "generate_fredql",
        lambda state: state.get("current_step", "end_for_now"),
        {
            "create_smart_list": "create_smart_list",
            "end_for_now": "end_for_now"
        }
    )
    
    # After creating smart list, check next step
    workflow.add_conditional_edges(
        "create_smart_list",
        lambda state: state.get("current_step", "end_for_now"),
        {
            "review_smart_list": "review_smart_list",
            "retry_smart_list_creation": "retry_smart_list_creation",
            "awaiting_manual_list_name": "handle_manual_list_name",
            "end_for_now": "end_for_now"
        }
    )
    
    # After retry, regenerate FredQL with new description
    workflow.add_edge("retry_smart_list_creation", "generate_fredql")
    
    # After manual list name, create campaign
    workflow.add_conditional_edges(
        "handle_manual_list_name",
        lambda state: state.get("current_step", "end_for_now"),
        {
            "create_campaign": "create_campaign",
            "end_for_now": "end_for_now"
        }
    )
    
    # After review, either process changes or create campaign
    workflow.add_conditional_edges(
        "review_smart_list",
        lambda state: state.get("current_step", "end_for_now"),
        {
            "process_smart_list_changes": "process_smart_list_changes",
            "create_campaign": "create_campaign",
            "end_for_now": "end_for_now"
        }
    )
    
    # After processing changes, go back to review
    workflow.add_edge("process_smart_list_changes", "review_smart_list")
    
    # After creating campaign, go to email review
    workflow.add_edge("create_campaign", "review_email_template")
    
    # After email review, either process changes or confirm schedule
    workflow.add_conditional_edges(
        "review_email_template",
        lambda state: state.get("current_step", "end_for_now"),
        {
            "process_email_changes": "process_email_changes",
            "confirm_schedule": "confirm_schedule",
            "end_for_now": "end_for_now"
        }
    )
    
    # After processing email changes, go back to review
    workflow.add_edge("process_email_changes", "review_email_template")
    
    # After schedule confirmation, either process changes or schedule campaign
    workflow.add_conditional_edges(
        "confirm_schedule",
        lambda state: state.get("current_step", "end_for_now"),
        {
            "process_schedule_changes": "process_schedule_changes",
            "schedule_campaign": "schedule_campaign",
            "end_for_now": "end_for_now"
        }
    )
    
    # After processing schedule changes, go back to confirmation
    workflow.add_edge("process_schedule_changes", "confirm_schedule")
    
    # After scheduling campaign, end
    workflow.add_edge("schedule_campaign", "end_for_now")
    
    workflow.add_edge("end_for_now", END)
    
    # Compile with checkpointing for pause/resume
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)

