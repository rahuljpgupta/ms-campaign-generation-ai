"""
Workflow executor for running campaign generation workflows
"""

import os
import asyncio
from typing import Dict, Any
from dotenv import load_dotenv

from .websocket_workflow import build_websocket_workflow
from . import websocket_nodes
from ..nodes import parse_prompt, process_clarifications
from ..utils.llm_utils import get_llm

# Load environment variables
load_dotenv()


class WorkflowExecutor:
    """
    Executes campaign generation workflows with state management
    """
    
    def __init__(self):
        # Initialize LLM instance based on environment configuration
        self.llm = get_llm(temperature=0.7)
        
        # Client session storage - stores workflow states
        self.client_sessions: Dict[str, Dict[str, Any]] = {}
        self.client_workflows: Dict[str, Any] = {}  # Store compiled workflow per client
    
    async def process_campaign(self, client_id: str, message: str, connection_manager):
        """
        Process user message through LangGraph workflow with checkpointing
        
        Args:
            client_id: Unique client identifier
            message: User's campaign request message
            connection_manager: ConnectionManager instance for sending messages
        """
        # Send processing indicator
        await connection_manager.send_message(client_id, {
            "type": "assistant_thinking",
            "message": "Analyzing your campaign request...",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": True
        })
        
        try:
            # Get location data and credentials for this client
            location = connection_manager.get_location(client_id)
            credentials = connection_manager.get_credentials(client_id)
            
            # Helper function to send messages
            async def send_msg(msg):
                await connection_manager.send_message(client_id, msg)
            
            # Build workflow with WebSocket support (if not already built for this client)
            if client_id not in self.client_workflows:
                workflow = build_websocket_workflow(self.llm, send_msg)
                self.client_workflows[client_id] = workflow
            else:
                workflow = self.client_workflows[client_id]
            
            # Initialize state for new conversation
            initial_state = self._create_initial_state(message, location)
            
            # Configuration with thread_id for checkpointing
            config = {"configurable": {"thread_id": client_id}}
            
            # Store initial state, location, and credentials
            self.client_sessions[client_id] = {
                "state": initial_state.copy(),
                "location": location,
                "credentials": credentials
            }
            
            # Execute workflow with checkpointing
            await self._run_workflow(initial_state, config, client_id, send_msg, location, credentials)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            await connection_manager.send_message(client_id, {
                "type": "error",
                "message": f"Error processing request: {str(e)}",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
    
    def _create_initial_state(self, user_prompt: str, location: dict = None) -> dict:
        """
        Create initial workflow state
        
        Args:
            user_prompt: User's campaign request
            location: Location data from client
            
        Returns:
            Initial state dictionary
        """
        # Use location ID from handshake if available, otherwise fallback to env var
        location_id = ""
        if location and location.get("id"):
            location_id = location["id"]
        else:
            location_id = os.getenv("FREDERICK_LOCATION_ID", "")
        
        return {
            "user_prompt": user_prompt,
            "audience": "",
            "template": "",
            "datetime": "",
            "image_search_queries": [],
            "location_id": location_id,
            "location": location or {},  # Store full location object for timezone and other data
            "smart_list_id": "",
            "smart_list_name": "",
            "smart_list_display": "",
            "create_new_list": False,
            "matched_lists": [],
            "fredql_query": "",
            "merge_tags": [],
            "email_template": "",
            "schedule_confirmed": False,
            "clarifications_needed": [],
            "clarification_responses": {},
            "current_step": "parse_prompt"
        }
    
    def reset_client_state(self, client_id: str):
        """
        Reset all stored state for a client
        
        Args:
            client_id: Client identifier
        """
        # Clear stored session state
        if client_id in self.client_sessions:
            del self.client_sessions[client_id]
        
        # Clear stored workflow (will be rebuilt on next request)
        if client_id in self.client_workflows:
            del self.client_workflows[client_id]
        
        print(f"Reset state for client {client_id}")
    
    async def _run_workflow(self, state, config, client_id, send_msg, location: dict = None, credentials: dict = None):
        """
        Execute workflow with proper async handling
        
        Args:
            state: Initial workflow state
            config: LangGraph configuration
            client_id: Client identifier
            send_msg: Async function to send messages
            location: Location data from client
            credentials: API credentials from client
        """
        # Since LangGraph doesn't fully support async nodes in invoke(),
        # we'll manually execute with checkpointing logic
        current_state = state.copy()
        self.client_sessions[client_id] = {
            "state": current_state,
            "location": location,
            "credentials": credentials
        }
        
        # Step 1: Parse prompt
        await self._parse_prompt_step(current_state, send_msg, location)
        
        # Step 2: Handle clarifications (loop until all resolved)
        await self._clarification_loop(current_state, send_msg, location)
        
        # Check if audience is "all_customers" - if so, skip smart list workflow
        audience = current_state.get("audience", "").lower()
        if audience == "all_customers":
            # Skip smart list workflow - set empty values
            current_state["smart_list_id"] = ""
            current_state["smart_list_name"] = ""
            current_state["smart_list_display"] = ""
            current_state["create_new_list"] = False
            current_state["current_step"] = "create_campaign"
            
            # Inform user
            await send_msg({
                "type": "assistant",
                "message": "✓ Understood! This campaign will be sent to **all customers**.",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
        else:
            # Step 3: Check smart lists
            await self._check_smart_lists_step(current_state, send_msg, credentials)
            
            # Step 4: Handle smart list selection
            await self._handle_smart_list_selection(current_state, send_msg, location, credentials)
        
        # Step 5: Create campaign and generate email template
        await self._create_campaign_step(current_state, send_msg, location, credentials)
        
        # Step 6: Review and refine email template
        if current_state["current_step"] == "review_email_template":
            await self._review_email_template(current_state, send_msg, location, credentials)
        
        # Step 7: Confirm and schedule campaign
        if current_state["current_step"] == "confirm_schedule":
            await self._confirm_schedule(current_state, send_msg, credentials)
        
        # Workflow complete - cleanup
        self._cleanup_client(client_id)
    
    async def _parse_prompt_step(self, state, send_msg, location: dict = None):
        """Parse the user's campaign prompt"""
        await send_msg({
            "type": "assistant",
            "message": "Let me parse your campaign requirements...",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": True
        })
        
        parse_result = parse_prompt(state, self.llm, location)
        state.update(parse_result)
        
        await send_msg({
            "type": "assistant",
            "message": f"✓ Understood:\n• **Audience:** {state['audience']}\n• **Email template:** {state['template']}\n• **Schedule:** {state['datetime']}",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": True
        })
    
    async def _clarification_loop(self, state, send_msg, location: dict = None):
        """Handle clarification questions in a loop"""
        while state.get("clarifications_needed") and len(state["clarifications_needed"]) > 0:
            clarification_result = await websocket_nodes.ask_clarifications_ws(state, send_msg)
            state.update(clarification_result)
            
            process_result = process_clarifications(state, self.llm, location)
            state.update(process_result)
    
    async def _check_smart_lists_step(self, state, send_msg, credentials: dict = None):
        """Check for existing smart lists"""
        if state["current_step"] in ["check_clarifications", "clarify_ambiguity"]:
            await send_msg({
                "type": "assistant_thinking",
                "message": "Checking for existing smart lists...",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": True
            })
            
            # Navigate to contact lists page (without refresh)
            location_id = state.get("location_id")
            if location_id:
                await send_msg({
                    "type": "ui_action",
                    "action": "navigate",
                    "payload": {
                        "path": f"/locations/{location_id}"
                    },
                    "timestamp": asyncio.get_event_loop().time()
                })
            
            check_result = await websocket_nodes.fetch_and_match_smart_lists_wrapper(state, self.llm, credentials)
            state.update(check_result)
    
    async def _handle_smart_list_selection(self, state, send_msg, location: dict = None, credentials: dict = None):
        """Handle smart list selection or new list creation"""
        if state["current_step"] == "confirm_smart_list_selection":
            result = await websocket_nodes.confirm_smart_list_selection_ws(state, send_msg)
            state.update(result)
        elif state["current_step"] == "confirm_new_list":
            result = await websocket_nodes.confirm_new_list_ws(state, send_msg)
            state.update(result)
        
        # After selection/confirmation, check what to do next
        if state["current_step"] == "generate_fredql":
            await self._generate_fredql(state, send_msg, location, credentials)
            
            # After generating FredQL, try creating in a loop (with retry logic)
            print("\n" + "=" * 80)
            print("[EXECUTOR] Entering creation loop")
            print(f"[EXECUTOR] Initial current_step: {state['current_step']}")
            print(f"[EXECUTOR] Initial creation_attempts: {state.get('creation_attempts', 0)}")
            print("=" * 80 + "\n")
            
            loop_iteration = 0
            while state["current_step"] == "create_smart_list":
                loop_iteration += 1
                print(f"\n[EXECUTOR] ===== CREATION LOOP ITERATION {loop_iteration} =====")
                print(f"[EXECUTOR] Before create_smart_list call - current_step: {state['current_step']}")
                print(f"[EXECUTOR] Before create_smart_list call - creation_attempts: {state.get('creation_attempts', 0)}")
                
                await self._create_smart_list(state, send_msg, credentials)
                
                print(f"[EXECUTOR] After create_smart_list call - current_step: {state['current_step']}")
                print(f"[EXECUTOR] After create_smart_list call - creation_attempts: {state.get('creation_attempts', 0)}")
                
                # Check next step after creation attempt
                if state["current_step"] == "review_smart_list":
                    print("[EXECUTOR] Success! Moving to review loop")
                    # Successfully created, review it in a loop
                    while state["current_step"] == "review_smart_list":
                        await self._review_smart_list(state, send_msg, location, credentials)
                        
                        # Break if we're done or if there's an error
                        if state["current_step"] not in ["review_smart_list", "process_smart_list_changes"]:
                            break
                    break  # Exit creation loop
                
                elif state["current_step"] == "retry_smart_list_creation":
                    # Creation failed (422 error), ask user for better description
                    print(f"\n[EXECUTOR] ===== ENTERING RETRY FLOW =====")
                    print(f"[EXECUTOR] Current creation_attempts: {state.get('creation_attempts', 0)}")
                    print(f"[EXECUTOR] Current audience: {state.get('audience', '')[:80]}...")
                    
                    from .retry_smart_list_nodes import retry_smart_list_creation_ws
                    print(f"[EXECUTOR] Calling retry_smart_list_creation_ws...")
                    retry_result = await retry_smart_list_creation_ws(state, send_msg)
                    print(f"[EXECUTOR] Got retry_result: {retry_result}")
                    state.update(retry_result)
                    print(f"[EXECUTOR] After state update, current_step: {state['current_step']}")
                    print(f"[EXECUTOR] After state update, new audience: {state.get('audience', '')[:80]}...")
                    
                    # After getting better description, regenerate FredQL
                    if state["current_step"] == "regenerate_fredql_after_retry":
                        print(f"[EXECUTOR] Setting current_step to 'generate_fredql'")
                        state["current_step"] = "generate_fredql"
                        print(f"[EXECUTOR] Calling _generate_fredql...")
                        await self._generate_fredql(state, send_msg, location, credentials)
                        print(f"[EXECUTOR] After FredQL generation, current_step: {state['current_step']}")
                        print(f"[EXECUTOR] Should loop continue? {state['current_step'] == 'create_smart_list'}")
                        # Loop will continue and try creating again if current_step is "create_smart_list"
                    else:
                        print(f"[EXECUTOR] Not regenerating, breaking loop. current_step: {state['current_step']}")
                        break  # Exit if user cancelled or error
                
                elif state["current_step"] == "awaiting_manual_list_name":
                    # After 3 failed attempts, get manual list name
                    print(f"[EXECUTOR] Max attempts reached, awaiting manual list name")
                    result = await websocket_nodes.handle_manual_list_name_ws(state, send_msg, credentials)
                    state.update(result)
                    break  # Exit creation loop
                
                else:
                    # Any other state, exit loop
                    print(f"[EXECUTOR] Unexpected state '{state['current_step']}', exiting loop")
                    break
            
            print(f"\n[EXECUTOR] Exited creation loop. Final current_step: {state['current_step']}")
            print("=" * 80 + "\n")
        elif state["current_step"] == "complete_selection":
            # Existing smart list selected, proceed to create campaign
            state["current_step"] = "create_campaign"
    
    async def _generate_fredql(self, state, send_msg, location: dict = None, credentials: dict = None):
        """Generate FredQL query for new smart list"""
        result = await websocket_nodes.generate_smart_list_fredql_ws(state, self.llm, send_msg, location, credentials)
        state.update(result)
    
    async def _create_smart_list(self, state, send_msg, credentials: dict = None):
        """Create smart list using generated FredQL"""
        result = await websocket_nodes.create_smart_list_ws(state, send_msg, credentials)
        state.update(result)
    
    async def _review_smart_list(self, state, send_msg, location: dict = None, credentials: dict = None):
        """Handle smart list review - ask for user feedback"""
        from .review_smart_list_nodes import ask_for_review_ws, process_smart_list_changes_ws
        
        # Ask for review
        print(f"[Review Loop] Asking for initial review...")
        review_result = await ask_for_review_ws(state, send_msg)
        state.update(review_result)
        print(f"[Review Loop] User response resulted in current_step: {state['current_step']}")
        
        # Keep looping while user wants changes
        while state["current_step"] == "process_smart_list_changes":
            print(f"[Review Loop] Processing changes...")
            change_result = await process_smart_list_changes_ws(state, self.llm, send_msg, location, credentials)
            state.update(change_result)
            print(f"[Review Loop] After processing changes, current_step: {state['current_step']}")
            
            # After processing changes, it goes back to review_smart_list
            # Ask for review again
            if state["current_step"] == "review_smart_list":
                print(f"[Review Loop] Asking for review again after changes...")
                review_result = await ask_for_review_ws(state, send_msg)
                state.update(review_result)
                print(f"[Review Loop] User response resulted in current_step: {state['current_step']}")
                # Loop continues if user wants more changes
            else:
                print(f"[Review Loop] Breaking loop, current_step is: {state['current_step']}")
                break
        
        print(f"[Review Loop] Exiting review loop with current_step: {state['current_step']}")
    
    async def _create_campaign_step(self, state, send_msg, location: dict = None, credentials: dict = None):
        """Create campaign and generate email template"""
        if state["current_step"] == "create_campaign":
            result = await websocket_nodes.create_campaign_ws(state, self.llm, send_msg, location, credentials)
            state.update(result)
    
    async def _review_email_template(self, state, send_msg, location: dict = None, credentials: dict = None):
        """Handle email template review - ask for user feedback"""
        from .review_email_template_nodes import ask_for_email_review_ws, process_email_changes_ws
        
        # Ask for review
        print(f"[Email Review Loop] Asking for initial review...")
        review_result = await ask_for_email_review_ws(state, send_msg)
        state.update(review_result)
        print(f"[Email Review Loop] User response resulted in current_step: {state['current_step']}")
        
        # Keep looping while user wants changes
        while state["current_step"] == "process_email_changes":
            print(f"[Email Review Loop] Processing changes...")
            change_result = await process_email_changes_ws(state, self.llm, send_msg, location, credentials)
            state.update(change_result)
            print(f"[Email Review Loop] After processing changes, current_step: {state['current_step']}")
            
            # After processing changes, it goes back to review_email_template
            # Ask for review again
            if state["current_step"] == "review_email_template":
                print(f"[Email Review Loop] Asking for review again after changes...")
                review_result = await ask_for_email_review_ws(state, send_msg)
                state.update(review_result)
                print(f"[Email Review Loop] User response resulted in current_step: {state['current_step']}")
                # Loop continues if user wants more changes
            else:
                print(f"[Email Review Loop] Breaking loop, current_step is: {state['current_step']}")
                break
        
        print(f"[Email Review Loop] Exiting review loop with current_step: {state['current_step']}")
    
    async def _confirm_schedule(self, state, send_msg, credentials: dict = None):
        """Handle schedule confirmation - ask for user confirmation or changes"""
        from .schedule_confirmation_nodes import confirm_schedule_ws, process_schedule_changes_ws, schedule_campaign_ws
        
        # Ask for confirmation
        confirm_result = await confirm_schedule_ws(state, send_msg)
        state.update(confirm_result)
        
        # Keep looping while user wants changes
        while state["current_step"] == "process_schedule_changes":
            change_result = await process_schedule_changes_ws(state, self.llm, send_msg)
            state.update(change_result)
            
            # After processing changes, it goes back to confirm_schedule
            # Ask for confirmation again
            if state["current_step"] == "confirm_schedule":
                confirm_result = await confirm_schedule_ws(state, send_msg)
                state.update(confirm_result)
                # Loop continues if user wants more changes
            else:
                break
        
        # If user confirmed, schedule the campaign
        if state["current_step"] == "schedule_campaign":
            schedule_result = await schedule_campaign_ws(state, send_msg, credentials)
            state.update(schedule_result)
    
    def _cleanup_client(self, client_id: str):
        """Clean up client session and workflow"""
        if client_id in self.client_sessions:
            del self.client_sessions[client_id]
        if client_id in self.client_workflows:
            del self.client_workflows[client_id]

