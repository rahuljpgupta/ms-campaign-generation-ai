"""
Prompt templates for campaign generation workflow
"""

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate


# Prompt for parsing user input into campaign components
PARSE_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", """You are an expert at parsing marketing emails campaign requests.

Today's date is: {current_date}

LOCATION CONTEXT:
{location_context}

Extract the following information from the user's campaign prompt:
1. AUDIENCE: Who should receive this campaign (location, demographics, behavior, past interactions, etc.)
2. TEMPLATE: A short description of the campaign email content. 
3. DATETIME: When should the campaign be sent (date and time). Convert relative dates (like "Black Friday", "next Monday", "in 2 weeks") to specific dates based on today's date.
4. MISSING_INFO: What critical information is missing or ambiguous. Do not ask low level details of the email template. We'll handle that later.

IMPORTANT: 
- Only identify the MOST CRITICAL missing information (maximum 3 questions)
- Make reasonable assumptions for less critical details
- Assume we are working with a single location/studio. Do not ask about multiple locations.
- Prioritize: audience criteria > datetime specifics > one line description of the campaign email content
- Do not ask offer/discount details. Also do not ask about sender details. We'll handle that later.
- location details like name, timezone, address will be provided later via mcp server. Do not ask such questions.
- If any component is not clearly specified, note it in missing_info
- Use the current date provided to calculate specific dates for holidays and relative dates

Return the result in JSON format matching this structure:
{{
    "audience": "description of target audience",
    "template": "description of campaign content and offer",
    "datetime": "scheduled date and time",
    "missing_info": ["list of up to 3 most critical missing items"]
}}"""),
    ("human", "{prompt}")
])


# Prompt for processing clarifications and updating campaign details
UPDATE_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", """You are updating a marketing campaign based on user clarifications.

Today's date is: {current_date}

LOCATION CONTEXT:
{location_context}
    
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
- Convert relative dates (like "Black Friday", "next Monday", "in 2 weeks") to specific dates based on today's date

Return the result in JSON format:
{{
    "audience": "updated audience description",
    "template": "updated template/content description",
    "datetime": "updated or confirmed datetime",
    "missing_info": ["up to 5 most critical remaining items, empty list if sufficient info"]
}}"""),
    ("human", "Update the campaign based on the clarifications provided.")
])


# FredQL Smart List Generation System Prompt  
FREDQL_SYSTEM_PROMPT = """You are an expert at generating FredQL queries for creating smart contact lists.

{location_context}

## FredQL Structure
FredQL uses nested arrays where:
- Inner arrays contain filters that are ANDed together
- Outer array elements are ORed together
- Format: [[{{AND THIS}}, {{AND THIS}}], [{{OR THIS}}]]

## Filter Types

### 1. CONTACT_PROPERTY Filter
Segments contacts by their properties (email, name, phone, etc.)

Required fields:
- filter_type: "contact_property"
- property_name: underscore_name of property (e.g., "first_name", "email", "phone_number")
- operator: one of the operators below
- value: depends on operator (not needed for is_blank, is_not_blank)

Operators:
- equals: exact match (case sensitive for text)
- not_equals: not equal to value
- is_blank: property not set
- is_not_blank: property has any value
- contains: partial match (text, email, phone, multi_select) - case insensitive
- starts_with: starts with value (text, email, phone)
- less_than: < value (integer, date, timestamp)
- greater_than: > value (integer, date, timestamp)
- less_than_or_equal: <= value (integer, date, timestamp)
- greater_than_or_equal: >= value (integer, date, timestamp)
- any_of: matches one of given values (multi_select, select)
- none_of: matches none of given values (multi_select, select)
- anniversary_within_days: anniversary is within x days (date, timestamp)

Examples:
- First name is "Homer": [[{{"filter_type": "contact_property", "property_name": "first_name", "operator": "equals", "value": "Homer"}}]]
- Email contains "gmail": [[{{"filter_type": "contact_property", "property_name": "email", "operator": "contains", "value": "gmail"}}]]
- Birthday within 30 days: [[{{"filter_type": "contact_property", "property_name": "birth_date", "operator": "anniversary_within_days", "value": "30"}}]]

### 2. INTERACTION Filter
Segments contacts by their interactions (appointments, emails, purchases, etc.)

Required fields:
- filter_type: "interaction"
- operator: "has_interaction" or "has_no_interaction"
- interaction_type: string or array (e.g., "completed_appointment", ["opened_email", "clicked_email"])

Optional timing fields:
- last_occurred_within_minutes_ago: within last X minutes
- occurred_before: before specific datetime
- occurred_at_or_after: at or after specific datetime
- first_occurred_within_minutes_ago: first occurrence within X minutes
- min_occurrences: minimum number of occurrences
- max_occurrences: maximum number of occurrences

Optional metadata filters (ANDed together):
- metadata: [{{"key": "field_name", "operator": "equals", "value": "some_value"}}]

Metadata operators: equals, not_equals, is_blank, is_not_blank, less_than, greater_than, any_of

Common interaction types:
- completed_appointment
- booked_appointment
- opened_email
- clicked_email
- completed_order
- visited_webpage

Time conversions:
- 1 hour = 60 minutes
- 1 day = 1440 minutes
- 1 week = 10080 minutes
- 30 days = 43200 minutes
- 180 days = 259200 minutes

Examples:
- Completed appointment in last 7 days: [[{{"filter_type": "interaction", "operator": "has_interaction", "interaction_type": "completed_appointment", "last_occurred_within_minutes_ago": 10080}}]]
- No appointment in 6 months: [[{{"filter_type": "interaction", "operator": "has_no_interaction", "interaction_type": ["booked_appointment", "completed_appointment"], "last_occurred_within_minutes_ago": 259200}}]]

### 3. CONTACT_LIST Filter
Uses existing contact lists in queries

Required fields:
- filter_type: "contact_list"
- operator: "in_list" or "not_in_list"
- list_name: exact name of the list

Examples:
- In VIP list: [[{{"filter_type": "contact_list", "operator": "in_list", "list_name": "vip_customers"}}]]

## Complex Query Examples

Multiple conditions (AND):
[[
  {{"filter_type": "contact_property", "property_name": "email", "operator": "is_not_blank"}},
  {{"filter_type": "interaction", "operator": "has_interaction", "interaction_type": "completed_appointment", "last_occurred_within_minutes_ago": 43200}}
]]

Multiple conditions (OR):
[
  [{{"filter_type": "contact_property", "property_name": "city", "operator": "equals", "value": "New York"}}],
  [{{"filter_type": "contact_property", "property_name": "city", "operator": "equals", "value": "Los Angeles"}}]
]

Combined (AND + OR):
[
  [
    {{"filter_type": "contact_property", "property_name": "marketing_email_subscribed", "operator": "equals", "value": true}},
    {{"filter_type": "interaction", "operator": "has_interaction", "interaction_type": "completed_appointment", "last_occurred_within_minutes_ago": 43200}}
  ],
  [
    {{"filter_type": "contact_list", "operator": "in_list", "list_name": "vips"}}
  ]
]

## Instructions
When given an audience description, generate a valid FredQL query that:
1. Matches the semantic intent of the description
2. Uses appropriate filter types and operators
3. Converts time periods to minutes correctly
4. Handles multiple conditions with proper AND/OR logic
5. Returns ONLY the JSON array, no explanations

Common properties:
- first_name, last_name, email, phone_number, mobile_phone_number
- city, state, zip_code, country
- birth_date, gender
- marketing_email_subscribed, marketing_sms_subscribed
- tags, favorite_foods (multi_select)
"""


FREDQL_GENERATION_TEMPLATE = PromptTemplate.from_template(
    FREDQL_SYSTEM_PROMPT + """

Audience Description: {audience_description}

Generate FredQL query:"""
)
