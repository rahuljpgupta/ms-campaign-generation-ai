# Testing the Campaign Generator UI Integration

## Quick Start

1. **Start the servers:**
```bash
./start-dev.sh
```

Or manually:
```bash
# Terminal 1 - Backend
python server.py

# Terminal 2 - Frontend  
cd client && npm run dev
```

2. **Open the UI:**
   - Navigate to `http://localhost:5173`
   - You should see "Campaign Generator" with a chat panel on the right

3. **Check connection:**
   - Look for "● Connected" in the chat header
   - If disconnected, check that both servers are running

## Test Scenarios

### Test 1: Simple Campaign (No Clarifications Needed)

**Input:**
```
Create a Black Friday campaign for contacts in New York location who visited my studio in the last 30 days. Offer them 30% discount. Send it on November 29th at 9 AM.
```

**Expected Behavior:**
1. ✅ System parses the prompt
2. ✅ Shows parsed information (Audience, Campaign, Schedule)
3. ✅ Input field shows "Processing..." (disabled)
4. ✅ System checks for existing smart lists
5. ✅ Shows matched smart lists as clickable options
6. ✅ User can click an option or type a number
7. ✅ Shows final campaign summary
8. ✅ Input field re-enabled for next campaign

---

### Test 2: Campaign with Clarifications

**Input:**
```
Create a campaign for gym members offering a discount next week
```

**Expected Behavior:**
1. ✅ System identifies missing information
2. ✅ Asks clarification questions (e.g., "Which location?", "What discount percentage?", "What specific day and time?")
3. ✅ Shows question counter (Question 1/3, Question 2/3, etc.)
4. ✅ Input field enabled for each question
5. ✅ After answering all questions, proceeds to smart list matching
6. ✅ Shows final summary

**Example Clarification Responses:**
- Q: "Which location should this campaign target?" → A: "New York"
- Q: "What discount percentage would you like to offer?" → A: "20%"
- Q: "What specific date and time should the campaign be sent?" → A: "December 1st at 10 AM"

---

### Test 3: No Matching Smart Lists

**Input:**
```
Create a campaign for contacts who purchased product X in the last 2 hours and live in Antarctica. Send tomorrow at 3 PM.
```

**Expected Behavior:**
1. ✅ System parses the prompt
2. ✅ Checks for smart lists
3. ✅ No matches found
4. ✅ Shows: "No existing smart lists match your audience criteria"
5. ✅ Asks: "Would you like me to create a new smart list?"
6. ✅ User responds "yes" or "no"
7. ✅ Shows appropriate result

---

### Test 4: Input State Management

**Watch the input field placeholder text:**
- When connected: "Describe your campaign..."
- When processing: "Processing..."
- When asking question: "Type your answer..."
- When showing options: "Click an option above or type your choice..."
- When disconnected: "Connecting to server..."

**Verify input is disabled when:**
- Backend is processing
- Workflow is checking smart lists
- Between workflow steps

---

### Test 5: Smart List Options UI

**Check visual elements:**
1. ✅ Each option shows:
   - List name (bold)
   - Relevance score (e.g., "Relevance: 85%")
   - Reason for match
2. ✅ Options have hover effect (border changes color, slight animation)
3. ✅ Clicking an option sends selection immediately
4. ✅ Can also type the option number (e.g., "1", "2", or "0" for new list)

---

## Debugging Tips

### Backend Logs
Watch the terminal running `server.py` for:
- WebSocket connection messages
- Workflow step progress
- LLM invocations
- Any errors with stack traces

### Frontend Console
Open browser DevTools (F12) and check Console for:
- "WebSocket connected"
- Message send/receive logs
- Any JavaScript errors

### Common Issues

**Issue: "Connecting to server..." stuck**
- Check backend is running on port 8000
- Check for CORS errors in browser console
- Verify `.env` file has required API keys

**Issue: Questions not appearing**
- Check backend logs for errors
- Verify GROQ_API_KEY is set
- Check if prompt parsing is working

**Issue: Smart lists not loading**
- Verify FREDERICK_API_KEY and FREDERICK_LOCATION_ID in `.env`
- Check backend logs for API errors
- Test MCP server separately: `python test_contacts_mcp.py`

**Issue: Input field stuck disabled**
- Refresh the page
- Check backend for errors
- Verify workflow completes (check `current_step` in backend logs)

---

## Environment Variables Checklist

Ensure `.env` file exists with:
```
GROQ_API_KEY=your_groq_api_key
FREDERICK_API_KEY=your_frederick_api_key
FREDERICK_LOCATION_ID=your_location_id
```

---

## Next Steps After Testing

Once basic integration works, you can proceed to implement:
1. Smart list creation API integration
2. Email template generation
3. Template editing (visual editor or prompt-based)
4. Schedule confirmation and API integration
5. Campaign deployment

