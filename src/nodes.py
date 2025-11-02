"""
Workflow nodes for campaign generation
"""

import os
import asyncio
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
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
        # All clarifications resolved, move to checking smart lists
        return "check_smart_lists"


async def fetch_and_match_smart_lists(state: CampaignState, llm) -> dict:
    """
    Fetch existing smart lists and find matches with the audience description.
    Returns top 3 matches using LLM to assess relevance.
    """
    print(f"\n[Checking existing smart lists...]")
    
    location_id = state.get("location_id") or os.getenv("FREDERICK_LOCATION_ID")
    
    if not location_id:
        print("✗ No location ID provided, skipping smart list check")
        return {
            "create_new_list": True,
            "current_step": "confirm_new_list"
        }
    
    # Import MCP tool
    try:
        from contacts_mcp import get_existing_smart_lists
    except ImportError:
        print("✗ MCP tools not available, skipping smart list check")
        return {
            "create_new_list": True,
            "current_step": "confirm_new_list"
        }
    
    # Fetch existing smart lists
    result = await get_existing_smart_lists(location_id)
    
    if "error" in result:
        print(f"✗ Error fetching smart lists: {result.get('message', 'Unknown error')}")
        return {
            "create_new_list": True,
            "current_step": "confirm_new_list"
        }
    
    lists_data = result.get("data", [])
    
    if not lists_data:
        print("✓ No existing smart lists found")
        return {
            "create_new_list": True,
            "current_step": "confirm_new_list"
        }
    
    print(f"✓ Found {len(lists_data)} existing smart lists")
    
    # Prepare list info for LLM matching
    list_descriptions = []
    for item in lists_data:
        attrs = item.get("attributes", {})
        list_descriptions.append({
            "id": item.get("id"),
            "name": attrs.get("name", ""),
            "display_name": attrs.get("display_name", ""),
            "filters": attrs.get("filters", [])
        })
    
    # Use LLM to find best matches
    audience_desc = state.get("audience", "")
    
    matching_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are helping match a campaign audience description with existing contact lists.

Audience Description: {audience}

Available Contact Lists:
{lists}

Find up to 3 best matching lists based on how well they align with the audience description.
Consider list name, display name and filters to find a match.

Return the result in JSON format:
{{
    "matches": [
        {{
            "id": "list_id",
            "relevance_score": 0.95,
            "reason": "why this list matches"
        }}
    ],
    "has_matches": true or false
}}

Only include lists with relevance_score > 0.5. Return empty matches array if no good matches found."""),
        ("human", "Find the best matching lists for this audience.")
    ])
    
    # Format lists for prompt
    lists_text = "\n".join([
        f"- ID: {l['id']}, Name: {l['name']}, Display Name: {l.get('display_name', 'N/A')}, Filters: {l.get('filters', [])}"
        for l in list_descriptions[:50]  # Limit to first 50 lists
    ])
    
    try:
        parser = JsonOutputParser()
        chain = matching_prompt | llm | parser
        
        match_result = chain.invoke({
            "audience": audience_desc,
            "lists": lists_text
        })
        
        matches = match_result.get("matches", [])
        
        if not matches or not match_result.get("has_matches", False):
            print("✓ No relevant matches found")
            return {
                "create_new_list": True,
                "current_step": "confirm_new_list"
            }
        
        # Get full details for matched lists
        matched_lists = []
        for match in matches[:3]:  # Top 3 matches
            list_id = match.get("id")
            full_list = next((l for l in list_descriptions if l["id"] == list_id), None)
            if full_list:
                matched_lists.append({
                    **full_list,
                    "relevance_score": match.get("relevance_score"),
                    "reason": match.get("reason")
                })
        
        print(f"✓ Found {len(matched_lists)} relevant match(es)")
     
        return {
            "matched_lists": matched_lists,
            "current_step": "confirm_smart_list_selection"
        }
        
    except Exception as e:
        print(f"✗ Error matching lists: {e}")
        return {
            "create_new_list": True,
            "current_step": "confirm_new_list"
        }


