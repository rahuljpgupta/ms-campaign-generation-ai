# Campaign Generation Workflow

## Complete Flow

```
1. PARSE PROMPT
   └─> Extract: audience, template, datetime
   └─> Identify missing info (max 5 questions)

2. CLARIFICATIONS (if needed)
   ├─> Ask up to 5 critical questions
   ├─> User answers (can skip with Enter)
   ├─> Process answers with LLM
   └─> Loop back if still missing info

3. CHECK SMART LISTS
   ├─> Fetch existing lists from Frederick API (MCP)
   ├─> Use LLM to match audience with lists
   └─> Route based on results:
       ├─> Matches found → Show matches
       └─> No matches → Confirm new list

4a. CONFIRM SMART LIST SELECTION (if matches found)
    ├─> Display top 3 matches with:
    │   ├─> List name
    │   ├─> Contact count
    │   ├─> Relevance score
    │   └─> Match reason
    ├─> User selects option:
    │   ├─> 1-3: Use selected list
    │   └─> 0: Create new list
    └─> Continue to next step

4b. CONFIRM NEW LIST (if no matches)
    ├─> Show "no matches found" message
    ├─> Confirm to proceed with new list
    └─> Continue to next step

5. [FUTURE] CREATE NEW SMART LIST
   └─> Generate list criteria
   └─> Create via API

6. [FUTURE] GENERATE EMAIL TEMPLATE
   └─> Use MCP to fetch assets
   └─> Generate template with offers

7. [FUTURE] TEMPLATE EDITING
   └─> Allow manual/prompt-based edits

8. [FUTURE] SCHEDULE CAMPAIGN
   └─> Confirm date/time
   └─> Schedule via API
```

## Decision Points

### After Parse Prompt
- **Has clarifications?** → Go to Ask Clarifications
- **All clear?** → Go to Check Smart Lists

### After Process Clarifications
- **Still need info?** → Loop back to Ask Clarifications
- **All clear?** → Go to Check Smart Lists

### After Check Smart Lists
- **Matches found?** → Go to Confirm Smart List Selection
- **No matches?** → Go to Confirm New List
- **Error/No location?** → Go to Confirm New List

### After Confirm Selection/New List
- Continue to next phase (template generation)

## State Tracking

The workflow maintains state including:
- `user_prompt`: Original request
- `audience`: Parsed audience description
- `template`: Campaign content details
- `datetime`: Scheduled time
- `location_id`: Frederick location ID
- `smart_list_id`: Selected or created list ID
- `smart_list_name`: List name
- `create_new_list`: Boolean flag
- `clarifications_needed`: List of questions
- `clarification_responses`: User answers
- `matched_lists`: Top 3 matched lists
- `current_step`: Current workflow position

## Example Execution

```
User Input: "Create Black Friday campaign for New York customers"

1. Parse Prompt
   ✓ Audience: Customers in New York
   ✓ Template: Black Friday campaign
   ✗ DateTime: Not specified
   → Need clarification: When to send?

2. Clarifications
   Q: When should the campaign be sent?
   A: Black Friday morning
   ✓ Updated DateTime: Black Friday 9AM

3. Check Smart Lists
   ✓ Found 15 existing lists
   ✓ Matched 2 relevant lists:
      1. "NYC Customer Base" (95% match)
      2. "New York Region" (78% match)

4. Confirm Selection
   [Display matches]
   User selects: 1
   ✓ Using "NYC Customer Base"

5. Continue to template generation...
```

