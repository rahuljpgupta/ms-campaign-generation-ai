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
3. DATETIME: When should the campaign be sent (date and time in ISO 8601 format with timezone offset, e.g., "2025-11-28T14:15:00+05:30"). Convert relative dates (like "Black Friday", "next Monday", "in 2 weeks") to specific dates based on today's date. Use the location's timezone from the context above.
4. MISSING_INFO: What critical information is missing or ambiguous. Do not ask low level details of the email template. We'll handle that later.

IMPORTANT: 
- Only identify the MOST CRITICAL missing information (maximum 3 questions)
- Make reasonable assumptions for less critical details
- We are working with a single location/studio. Do not ask about multiple locations.
- Prioritize: audience criteria > datetime specifics > one line description of the campaign email content
- Do not ask offer/discount details. Also do not ask about sender details. We'll handle that later.
- location/sender details like name, timezone, address are provided via Location context. Do not ask such questions.
- If any component is not clearly specified, note it in missing_info
- Use the current date provided to calculate specific dates for holidays and relative dates
- Assume the system separately handles the recipent's opt-in status. We don't need to ask about it.
- Assume the campaign send timezone is always the location's timezone.
- Do not ask about desired subject line and preheader text. We'll handle that later.
- Do not ask about the existence of smart list filters. We'll handle that later.
- Generate a short smart list name (2-8 words max) that describes the audience. The name should start with "AI - "

Return the result in JSON format matching this structure:
{{
    "audience": "description of target audience",
    "template": "description of campaign content and offer",
    "datetime": "YYYY-MM-DDTHH:MM:SS+TZ:TZ (ISO 8601 format with location's timezone offset)",
    "smart_list_name": "AI - [short 2-8 word description of the audience]",
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
- We are working with a single location/studio. Do not ask about multiple locations.
- If sufficient information is available, proceed even if some details could be more specific
- Assume the system separately handles the recipent's opt-in status. We don't need to ask about it.
- Assume the campaign send timezone is always the location's timezone.
- Do not ask about desired subject line and preheader text. We'll handle that later.
- Do not ask about the existence of smart list filters. We'll handle that later.
- Convert relative dates (like "Black Friday", "next Monday", "in 2 weeks") to specific dates based on today's date
- Generate a short smart list name (2-8 words max) that describes the audience. The name should start with "AI - "
- DateTime must be in ISO 8601 format with timezone offset (e.g., "2025-11-28T14:15:00+05:30"). Use the location's timezone from the context above.

Return the result in JSON format:
{{
    "audience": "updated audience description",
    "template": "updated template/content description",
    "datetime": "YYYY-MM-DDTHH:MM:SS+TZ:TZ (ISO 8601 format with location's timezone offset)",
    "smart_list_name": "AI - [short 2-8 word description of the audience]",
    "missing_info": ["up to 3 most critical remaining items, empty list if sufficient info"]
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

IMPORTANT: ONLY use interaction types from this EXACT list (no variations or custom types):
{{interaction_types}}

If you cannot confidently map the user's request to these exact interaction types, you MUST indicate low confidence.

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
5. Uses ONLY interaction types from the valid list above (exact matches required)
6. Uses ONLY contact properties from the list provided for this location
7. Returns ONLY the JSON array, no explanations

IMPORTANT Guidelines:
- If interaction type is mentioned, use the closest match from the valid list above
- If a contact property is mentioned, use the closest match from the available properties
- If audience can be represented with basic filters (email, interactions, etc.), generate the query
- Be creative and flexible in interpreting user intent with available filters
- We are working with a single location/studio.

ONLY return error if:
- The audience CANNOT be reasonably represented with ANY combination of available properties and interaction types
- For example: if user asks for "customers who completed_service" but only "booked_appointment" exists, 
  you can use "booked_appointment" as a reasonable proxy

Error format (use ONLY when truly impossible):
{{"error": "manual_creation_required", "reason": "Specific reason why this cannot be represented"}}
"""


FREDQL_GENERATION_TEMPLATE = PromptTemplate.from_template(
    FREDQL_SYSTEM_PROMPT + """

Audience Description: {audience_description}

Location Context: {location_context}

Contact Properties available for this location:
{contact_properties}

Interaction Types available:
{interaction_types}

Generate FredQL query:"""
)


# Email Template Generation Prompt
EMAIL_TEMPLATE_GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert email marketing template designer for {business_name}.

LOCATION CONTEXT:
{location_context}

SOCIAL PROFILE LINKS (use ONLY these valid links):
{social_links}

CAMPAIGN BRIEF:
{campaign_description}

PEXELS IMAGES (use 1-3 of these FREE high-quality images in your email):
{pexels_images}

MERGE TAGS (personalization/dynamic tags):
{merge_tags}

MERGE TAG USAGE:
- **Always start emails with a personalized greeting** using {{{{contact.properties.first_name default="there"}}}} when available
- Use other merge tags where appropriate throughout the email
- **Use EXACT merge tag values** from the list above
- **Format**: Wrap in double curly braces like {{{{merge_tag_value}}}}
- Common examples:
  * {{{{contact.properties.first_name default="there"}}}} for customer's first name
  * {{{{location.name}}}} for business name
  * {{{{location.address}}}} for business address
  * {{{{location.online_booking_url}}}} for booking links
  * {{{{location.website}}}} for website link
  * {{{{system.unsubscribe_link}}}} for unsubscribe (required in footer)

REFERENCE TEMPLATES:
Below are some recent email templates from this business. Study them carefully to understand:
- Brand voice and writing style
- Typical structure and layout patterns
- Image usage and placement
- Color schemes and font styling
- Call-to-action patterns
- Footer formatting
- Subject line patterns and tone

{reference_templates}

TASK:
Generate three components for this email campaign:

1. **Campaign Name**: A descriptive internal name for this campaign starting with "AI - " (e.g., "AI - Spring Sale - March 2024", "AI - New Member Welcome")

2. **Subject Line**: An engaging email subject line that:
   - Matches the brand's tone from reference templates
   - Is concise (under 60 characters)
   - Encourages opens
   - Relates to the campaign brief

3. **HTML Email Template**: A complete, valid HTML email that:
   - **Preserves the brand identity**: Match the writing style, tone, and language from reference templates
   - **Follows the structure**: Use similar layout patterns (header, content blocks, CTA, footer) from reference templates
   - **Includes meaningful, engaging content in the email body** - not just structure, but actual relevant content
   - **Start with a greeting** to the customer
   - **Use existing branding elements**: Extract and use logos, brand colors, fonts from reference templates
   - **MUST include 1-3 images from PEXELS IMAGES section** - Use the actual image URLs provided above
   - **Use alt text properly**: Put alt descriptions in the `alt` attribute only (e.g., `<img src="..." alt="description">`) - do NOT display alt text as visible text
   - **Creative Image Layouts**: Use varied, engaging image placements:
     * **Hero image**: Full-width image at the top
     * **Image + Text blocks**: Two-column layouts with image on left (or right) and text on right (or left)
     * **Inline images**: Images integrated within content blocks
     * **Image grid**: Multiple smaller images together
     * **DO NOT put images after the signature/closing** - All images and CTAs must come BEFORE the closing/signature
   - **Email Structure** (MUST follow this order):
     1. Header/Logo (if applicable)
     2. Greeting using merge tags (e.g., "{{{{salutation}}}} {{{{first_name}}}},")
     3. Main content with images and text blocks (use creative layouts)
     4. Call-to-action button (if needed)
     5. Closing/Signature (e.g., "Warm wishes, [Business Name] Team") - **This should be the last meaningful content**
     6. Footer (company address, social links, unsubscribe)
   - **Includes all standard elements**:
     - Unsubscribe link: Must include at the bottom - No longer want these emails? <a href="{{{{unsubscribe_link}}}}" target="_blank">Unsubscribe</a>
     - Company name and address (from location context)
     - Social media links must be used from SOCIAL PROFILE LINKS section and not from the existing email templates
     - Must include all the social media links from the SOCIAL PROFILE LINKS section just before signature
     - If no social media links are provided, do not include the social links block
     - Use the social links icons from the SOCIAL PROFILE LINKS section which are provided as image_url and add respective url.
     - Multiple content blocks in MAIN CONTENT area: Use varied layouts like text blocks, image+text blocks (side-by-side), video+text blocks
     - Create medium size email template which has around 300-500 words of content
   - **Adapts the content**: Tailor the message to match the campaign brief
   - **Must NOT use any template variables** like {{{{customer.first_name}}}}, {{{{offering.name}}}}, etc.
   - **Maintains visual consistency**: Keep logos, brand colors, fonts that appear in reference templates
   - **Is mobile-responsive**: Use standard email-safe HTML and inline CSS

IMPORTANT GUIDELINES:
- Generate ONLY valid HTML email code (no markdown, no explanations)
- Use only inline CSS for all styling to ensure compatibility across email clients
- **MUST use 1-3 images from PEXELS IMAGES section** - Use the actual URLs provided, not placeholders
- **Use alt text ONLY in the alt attribute** - Do NOT display alt text as visible text in the email
- Include photographer credits for Pexels images: <p style="font-size: 10px; color: #999;">Photo by [photographer name]</p>

**CREATIVE IMAGE LAYOUT EXAMPLES**:
  1. **Hero Image**: `<img src="[pexels-url]" alt="..." style="width:100%; max-width:600px; height:auto;">`
  2. **Image + Text (Left/Right)**:
     ```
     <table style="width:100%;">
       <tr>
         <td style="width:50%; padding:10px;"><img src="[pexels-url]" alt="..." style="width:100%;"></td>
         <td style="width:50%; padding:10px; vertical-align:middle;">[Your text content here]</td>
       </tr>
     </table>
     ```
  3. **Text + Image (Right/Left)**: Reverse the columns above
  4. Mix and match these layouts for visual variety

**CRITICAL STRUCTURE RULES**:
- ALL images, CTAs, and content blocks MUST come BEFORE the closing/signature
- Closing/signature (e.g., "Warm wishes, Team") should be the LAST meaningful content
- NEVER place images, buttons, or content blocks after the signature
- Order: Content → CTA → Signature → Footer (address, social links, unsubscribe)

- Include meaningful, engaging content that matches the campaign request
- Make the email responsive and professional using table-based layouts
- Include a clear call-to-action (if appropriate)
- Use professional email styling with proper spacing, colors, and typography
- DO NOT add markdown formatting in HTML
- ALWAYS include the unsubscribe link: <a href="{{{{unsubscribe_link}}}}">Unsubscribe</a>
- Use only the social links provided in SOCIAL PROFILE LINKS section
- **Keep the email sanitised**: Do not include unsafe tags like Script, iframe etc.
- Must NOT add any template variable in the generated HTML
- DO NOT create placeholder images - ONLY use the provided Pexels image URLs

Return your response in the following JSON format:
{{{{
  "campaign_name": "Your campaign name here",
  "subject_line": "Your subject line here",
  "html": "Complete HTML template here"
}}}}

Return ONLY valid JSON, no other text or explanations."""),
    ("human", "Generate the campaign name, subject line, and email template now.")
])

# Email Template Update Prompt
EMAIL_UPDATE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert email template editor for {business_name}.

LOCATION CONTEXT:
{location_context}

AVAILABLE MERGE TAGS (personalization/dynamic tags):
{merge_tags}

MERGE TAG USAGE RULES (CRITICAL):
1. **When user requests personalization**, ADD the appropriate merge tags to the HTML
2. **Use EXACT merge tag values** from the AVAILABLE MERGE TAGS list above
3. **Format**: Wrap merge tags in double curly braces like {{{{merge_tag_value}}}}
4. **Common patterns**:
   - Contact properties: {{{{contact.properties.first_name default="there"}}}}
   - Location properties: {{{{location.name}}}}, {{{{location.website}}}}, {{{{location.address}}}}
   - System tags: {{{{system.unsubscribe_link}}}}
5. **Only use merge tags that exist** in the AVAILABLE MERGE TAGS list above
6. **If user asks for a tag that doesn't exist**, find the closest match from available tags
7. **Examples of valid usage**:
   - {{{{contact.properties.first_name default="there"}}}} for customer's first name
   - {{{{location.online_booking_url}}}} for booking links
   - {{{{location.address}}}} for business address

CURRENT EMAIL HTML:
{current_html}

USER'S CHANGE REQUEST:
{user_feedback}

TASK:
Update the provided existing email HTML based on the user's specific change request.

REQUIREMENTS:
1. **Preserve the overall structure and branding** of the existing email
2. **Make ONLY the changes requested by the user** - do not make unnecessary modifications
3. **Maintain proper HTML structure and inline CSS**
4. **Keep existing styling, colors, fonts, and layout** unless specifically asked to change them
5. **Ensure the updated email remains professional and email-client compatible**
6. **Generate ONLY valid HTML email code** (no markdown, no explanations)
7. **If updating content, make it engaging and relevant**
8. **Preserve any existing images, logos, or branding elements** unless asked to change them
9. **Maintain mobile responsiveness**

CRITICAL REQUIREMENTS:
- ALWAYS include the unsubscribe link: <a href="{{{{unsubscribe_link}}}}" target="_blank">Unsubscribe</a>
- **USE merge tags from AVAILABLE MERGE TAGS section when requested by user** - these are the ONLY template variables allowed
- Do NOT include unsafe tags like Script, iframe
- Use inline CSS only for all styling to ensure compatibility across email clients
- Keep all required elements: unsubscribe link, company info, social links
- **Maintain proper email structure**: All content and images must come BEFORE the closing/signature
- Closing/signature should be the last meaningful content before footer elements (footer = company info, social links, unsubscribe)
- Social media links must be used from SOCIAL PROFILE LINKS section and not from the existing email templates
- Must include all the social media links from the SOCIAL PROFILE LINKS section just before signature
- If no social media links are provided, do not include the social links block
- Use the social links icons from the SOCIAL PROFILE LINKS section which are provided as image_url and add respective url.
- Multiple content blocks: Feel free to add any of text blocks, image+text blocks, video+text blocks in the MAIN CONTENT area (before signature)
- Create medium size email template which has around 300-500 words of content
- Must not add any placeholder images. Only valid images should be added.

EXAMPLE - How to add merge tags when user requests personalization:

User request: "add first name to greeting"
BEFORE: <p>Hi there,</p>
AFTER: <p>Hi {{{{contact.properties.first_name default="there"}}}},</p>

User request: "personalize the greeting with customer name"
BEFORE: <p>Hello valued customer,</p>
AFTER: <p>Hello {{{{contact.properties.first_name default="valued customer"}}}},</p>

User request: "add our website link"
BEFORE: <p>Visit our website for more info.</p>
AFTER: <p>Visit <a href="{{{{location.website}}}}">our website</a> for more info.</p>

Return ONLY the complete updated HTML, no explanations or markdown formatting."""),
    ("human", "Update the email template now based on the user's request.")
])
