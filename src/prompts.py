"""
Prompt templates for campaign generation workflow
"""

from langchain_core.prompts import ChatPromptTemplate


# Prompt for parsing user input into campaign components
PARSE_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", """You are an expert at parsing marketing emails campaign requests.
Extract the following information from the user's campaign prompt:
1. AUDIENCE: Who should receive this campaign (location, demographics, behavior, past interactions, etc.)
2. TEMPLATE: What content/offer should be in the email (discounts, promotions, products)
3. DATETIME: When should the campaign be sent (date and time)
4. MISSING_INFO: What critical information is missing or ambiguous. Do not ask low level details of the email template. We'll handle that later.

IMPORTANT: 
- Only identify the MOST CRITICAL missing information (maximum 5 questions)
- Make reasonable assumptions for less critical details
- Prioritize: audience criteria > offer/discount details > datetime specifics
- If any component is not clearly specified, note it in missing_info

Return the result in JSON format matching this structure:
{{
    "audience": "description of target audience",
    "template": "description of campaign content and offer",
    "datetime": "scheduled date and time",
    "missing_info": ["list of up to 5 most critical missing items"]
}}"""),
    ("human", "{prompt}")
])


# Prompt for processing clarifications and updating campaign details
UPDATE_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", """You are updating a marketing campaign based on user clarifications.
    
Original campaign details:
- Audience: {audience}
- Template: {template}
- DateTime: {datetime}

User has provided the following clarifications:
{clarifications}

Based on these clarifications, update the campaign details and identify if any information is still missing.

IMPORTANT:
- Only ask for CRITICAL missing information (maximum 5 total questions across all rounds)
- Make reasonable assumptions for minor details
- If sufficient information is available, proceed even if some details could be more specific

Return the result in JSON format:
{{
    "audience": "updated audience description",
    "template": "updated template/content description",
    "datetime": "updated or confirmed datetime",
    "missing_info": ["up to 5 most critical remaining items, empty list if sufficient info"]
}}"""),
    ("human", "Update the campaign based on the clarifications provided.")
])

