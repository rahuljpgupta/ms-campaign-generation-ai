"""
LangGraph workflow builder for campaign generation
"""

from langgraph.graph import StateGraph, END
from .models import CampaignState
from .nodes import (
    parse_prompt,
    ask_clarifications,
    process_clarifications,
    route_after_clarification_check,
    check_smart_lists,
    confirm_smart_list_selection,
    confirm_new_list
)


def build_workflow(llm):
    """
    Build and compile the campaign generation workflow
    
    Args:
        llm: Language model instance for processing
        
    Returns:
        Compiled workflow graph
    """
    workflow = StateGraph(CampaignState)
    
    # Add nodes for the workflow
    workflow.add_node("parse_prompt", lambda state: parse_prompt(state, llm))
    workflow.add_node("ask_clarifications", ask_clarifications)
    workflow.add_node("process_clarifications", lambda state: process_clarifications(state, llm))
    workflow.add_node("check_smart_lists", lambda state: check_smart_lists(state, llm))
    workflow.add_node("confirm_smart_list_selection", confirm_smart_list_selection)
    workflow.add_node("confirm_new_list", confirm_new_list)
    workflow.add_node("end_for_now", lambda state: {"current_step": "completed"})
    
    # Set entry point
    workflow.set_entry_point("parse_prompt")
    
    # Add edges
    # After parsing, check if clarifications are needed
    workflow.add_conditional_edges(
        "parse_prompt",
        route_after_clarification_check,
        {
            "ask_clarifications": "ask_clarifications",
            "check_smart_lists": "check_smart_lists"
        }
    )
    
    # After asking clarifications, process them
    workflow.add_edge("ask_clarifications", "process_clarifications")
    
    # After processing clarifications, check again if more clarifications needed (loop)
    workflow.add_conditional_edges(
        "process_clarifications",
        route_after_clarification_check,
        {
            "ask_clarifications": "ask_clarifications",  # Loop back if still need clarifications
            "check_smart_lists": "check_smart_lists"  # Check smart lists when clarifications done
        }
    )
    
    # After checking smart lists, route based on results
    workflow.add_conditional_edges(
        "check_smart_lists",
        lambda state: state.get("current_step", "end_for_now"),
        {
            "confirm_smart_list_selection": "confirm_smart_list_selection",
            "confirm_new_list": "confirm_new_list",
            "end_for_now": "end_for_now"
        }
    )
    
    # After confirming selection or new list, end
    workflow.add_edge("confirm_smart_list_selection", "end_for_now")
    workflow.add_edge("confirm_new_list", "end_for_now")
    
    # End node
    workflow.add_edge("end_for_now", END)
    
    return workflow.compile()

