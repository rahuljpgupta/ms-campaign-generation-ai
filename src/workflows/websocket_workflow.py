"""
WebSocket-compatible LangGraph workflow with checkpointing for campaign generation
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from ..models import CampaignState
from ..nodes import parse_prompt, process_clarifications, route_after_clarification_check
from . import websocket_nodes


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
    
    workflow.add_edge("confirm_smart_list_selection", "end_for_now")
    workflow.add_edge("confirm_new_list", "end_for_now")
    workflow.add_edge("end_for_now", END)
    
    # Compile with checkpointing for pause/resume
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)

