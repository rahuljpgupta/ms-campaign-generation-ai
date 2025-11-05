"""
Data models and state definitions for campaign generation workflow
"""

from typing import TypedDict
from pydantic import BaseModel, Field


class ParsedPrompt(BaseModel):
    """Structured output for parsed campaign prompt"""
    audience: str = Field(description="Target audience criteria (e.g., contacts in New York who visited studio)")
    template: str = Field(description="Campaign content details (e.g., 30% discount on Black Friday promotion)")
    datetime: str = Field(description="Scheduled date and time (e.g., 30th November 9AM)")
    smart_list_name: str = Field(default="", description="Short name for the smart list (e.g., 'AI - NYC Studio Members')")
    missing_info: list[str] = Field(description="List of missing or ambiguous information that needs clarification")


class CampaignState(TypedDict):
    """State for campaign generation workflow"""
    user_prompt: str
    audience: str
    template: str
    datetime: str
    location_id: str  # Frederick location ID
    smart_list_id: str
    smart_list_name: str
    create_new_list: bool  # Whether to create new list or use existing
    matched_lists: list[dict]  # Top matched smart lists from API
    fredql_query: str | list  # Generated FredQL query for new smart list
    email_template: str
    schedule_confirmed: bool
    clarifications_needed: list[str]
    clarification_responses: dict[str, str]  # Store user's clarification answers
    creation_attempts: int  # Number of times we've tried to create the smart list
    last_error: str  # Last error message from smart list creation
    current_step: str

