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


def check_smart_lists(state: CampaignState, llm) -> dict:
    """
    Check for existing smart lists and match with audience.
    This is a sync wrapper for the async function.
    """
    return asyncio.run(fetch_and_match_smart_lists(state, llm))


def confirm_smart_list_selection(state: CampaignState) -> dict:
    """
    Display matched smart lists and ask user to select one or create new.
    """
    matched_lists = state.get("matched_lists", [])
    
    print("\n" + "=" * 80)
    print("EXISTING SMART LISTS FOUND")
    print("=" * 80)
    print(f"\nFound {len(matched_lists)} relevant smart list(s) for your audience:")
    print(f"Target Audience: {state.get('audience', 'N/A')}")
    print("\nMatches:")
    
    for i, lst in enumerate(matched_lists, 1):
        print(f"\n{i}. {lst.get('display_name') or lst.get('name')}")
        print(f"   Name: {lst.get('name')}")
        print(f"   Relevance: {int(lst.get('relevance_score', 0) * 100)}%")
        print(f"   Reason: {lst.get('reason', 'N/A')}")
        filters = lst.get('filters', [])
        if filters:
            print(f"   Filters ({len(filters)}): {filters}")
    
    print("\n" + "=" * 80)
    print("Options:")
    for i in range(len(matched_lists)):
        print(f"  {i+1} - Use list #{i+1}")
    print(f"  0 - Create new smart list instead")
    print("=" * 80)
    
    choice = input("\nYour choice: ").strip()
    
    try:
        choice_num = int(choice)
        
        if choice_num == 0:
            print("\n✓ Will create a new smart list")
            return {
                "create_new_list": True,
                "smart_list_id": "",
                "smart_list_name": "",
                "current_step": "end_for_now"
            }
        elif 1 <= choice_num <= len(matched_lists):
            selected = matched_lists[choice_num - 1]
            print(f"\n✓ Selected: {selected.get('name')}")
            return {
                "create_new_list": False,
                "smart_list_id": selected.get("id"),
                "smart_list_name": selected.get("name"),
                "current_step": "end_for_now"
            }
        else:
            print("\n✗ Invalid choice, creating new smart list")
            return {
                "create_new_list": True,
                "smart_list_id": "",
                "smart_list_name": "",
                "current_step": "end_for_now"
            }
    except ValueError:
        print("\n✗ Invalid input, creating new smart list")
        return {
            "create_new_list": True,
            "smart_list_id": "",
            "smart_list_name": "",
            "current_step": "end_for_now"
        }


def confirm_new_list(state: CampaignState) -> dict:
    """
    Confirm with user that a new smart list will be created.
    """
    print("\n" + "=" * 80)
    print("NO MATCHING SMART LISTS FOUND")
    print("=" * 80)
    print(f"\nNo existing smart lists match your audience criteria:")
    print(f"Target Audience: {state.get('audience', 'N/A')}")
    print("\n" + "=" * 80)
    
    confirm = input("\nProceed with creating a new smart list? (Y/n): ").strip().lower()
    
    if confirm in ['', 'y', 'yes']:
        print("\n✓ Will create a new smart list")
        return {
            "create_new_list": True,
            "smart_list_id": "",
            "smart_list_name": "",
            "current_step": "end_for_now"
        }
    else:
        print("\n✗ Campaign creation cancelled")
        return {
            "current_step": "cancelled"
        }

