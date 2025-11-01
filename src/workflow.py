"""
LangGraph workflow builder for campaign generation
"""

from langgraph.graph import StateGraph, END
from .models import CampaignState
from .nodes import (
    parse_prompt,
    ask_clarifications,
    process_clarifications,
    route_after_clarification_check
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
            "end_for_now": "end_for_now"
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
            "end_for_now": "end_for_now"  # Continue if all clear
        }
    )
    
    # End node
    workflow.add_edge("end_for_now", END)
    
    return workflow.compile()

