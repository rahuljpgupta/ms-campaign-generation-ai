"""
Workflow nodes for campaign generation
"""

from langchain_core.output_parsers import JsonOutputParser
from .models import CampaignState, ParsedPrompt
from .prompts import PARSE_PROMPT_TEMPLATE, UPDATE_PROMPT_TEMPLATE


def parse_prompt(state: CampaignState, llm) -> dict:
    """Parse user prompt into audience, template, and datetime components"""
    print(f"\n[Parsing prompt...]")
    
    # Create parser and chain
    parser = JsonOutputParser(pydantic_object=ParsedPrompt)
    chain = PARSE_PROMPT_TEMPLATE | llm | parser
    
    try:
        result = chain.invoke({"prompt": state["user_prompt"]})
        
        print(f"✓ Extracted: Audience, Template, DateTime")
        if result['missing_info']:
            print(f"  {len(result['missing_info'])} clarification(s) needed")
        
        return {
            "audience": result["audience"],
            "template": result["template"],
            "datetime": result["datetime"],
            "clarifications_needed": result["missing_info"],
            "current_step": "clarify_ambiguity"
        }
    except Exception as e:
        print(f"✗ Error parsing prompt: {e}")
        return {
            "clarifications_needed": [f"Failed to parse prompt: {str(e)}"],
            "current_step": "parse_prompt"
        }


def ask_clarifications(state: CampaignState) -> dict:
    """
    Ask user for clarifications on missing or ambiguous information.
    Limited to maximum 5 questions.
    """
    print("\n" + "=" * 80)
    print("CLARIFICATIONS NEEDED")
    print("=" * 80)
    
    clarification_responses = state.get("clarification_responses", {})
    
    # Limit to 5 questions maximum
    questions_to_ask = state["clarifications_needed"][:5]
    
    if len(state["clarifications_needed"]) > 5:
        print(f"\nNote: Limiting to 5 most critical questions (out of {len(state['clarifications_needed'])} identified)")
    
    # Ask each clarification question
    for i, question in enumerate(questions_to_ask, 1):
        print(f"\n{i}. {question}")
        response = input("   Your answer: ").strip()
        
        # Allow user to skip a question
        if not response:
            response = "Not specified - please use best judgment"
        
        clarification_responses[question] = response
    
    print("\n" + "=" * 80)
    
    return {
        "clarification_responses": clarification_responses,
        "current_step": "process_clarifications"
    }


def process_clarifications(state: CampaignState, llm) -> dict:
    """
    Process user's clarification responses and update the campaign state.
    Re-parse or refine the audience, template, and datetime based on clarifications.
    """
    print(f"\n[Processing clarifications...]")
    
    # Build a context from clarifications
    clarification_context = "\n".join([
        f"Q: {q}\nA: {a}" 
        for q, a in state["clarification_responses"].items()
    ])
    
    # Create parser and chain
    parser = JsonOutputParser(pydantic_object=ParsedPrompt)
    chain = UPDATE_PROMPT_TEMPLATE | llm | parser
    
    try:
        result = chain.invoke({
            "audience": state.get("audience", ""),
            "template": state.get("template", ""),
            "datetime": state.get("datetime", ""),
            "clarifications": clarification_context
        })
        
        print(f"✓ Campaign details updated")
        
        if result['missing_info']:
            print(f"  Still need {len(result['missing_info'])} clarification(s)")
        else:
            print(f"  All information complete!")
        
        return {
            "audience": result["audience"],
            "template": result["template"],
            "datetime": result["datetime"],
            "clarifications_needed": result["missing_info"],
            "current_step": "check_clarifications"
        }
    except Exception as e:
        print(f"✗ Error processing clarifications: {e}")
        return {
            "clarifications_needed": [f"Failed to process clarifications: {str(e)}"],
            "current_step": "ask_clarifications"
        }


def route_after_clarification_check(state: CampaignState) -> str:
    """
    Routing function to decide next step after checking clarifications.
    Returns the name of the next node.
    """
    if state.get("clarifications_needed") and len(state["clarifications_needed"]) > 0:
        return "ask_clarifications"
    else:
        # All clarifications resolved, move to next major step
        return "end_for_now"

