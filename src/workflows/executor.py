"""
Workflow executor for running campaign generation workflows
"""

import os
import asyncio
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_groq import ChatGroq

from .websocket_workflow import build_websocket_workflow
from . import websocket_nodes
from ..nodes import parse_prompt, process_clarifications

# Load environment variables
load_dotenv()


class WorkflowExecutor:
    """
    Executes campaign generation workflows with state management
    """
    
    def __init__(self):
        # Initialize LLM instance
        self.llm = ChatGroq(
            temperature=0.7,
            model_name="openai/gpt-oss-120b",
            groq_api_key=os.getenv("GROQ_API_KEY")
        )
        
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
            initial_state = self._create_initial_state(message)
            
            # Configuration with thread_id for checkpointing
            config = {"configurable": {"thread_id": client_id}}
            
            # Store initial state
            self.client_sessions[client_id] = initial_state.copy()
            
            # Execute workflow with checkpointing
            await self._run_workflow(initial_state, config, client_id, send_msg)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            await connection_manager.send_message(client_id, {
                "type": "error",
                "message": f"Error processing request: {str(e)}",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
    
    def _create_initial_state(self, user_prompt: str) -> dict:
        """
        Create initial workflow state
        
        Args:
            user_prompt: User's campaign request
            
        Returns:
            Initial state dictionary
        """
        return {
            "user_prompt": user_prompt,
            "audience": "",
            "template": "",
            "datetime": "",
            "location_id": os.getenv("FREDERICK_LOCATION_ID", ""),
            "smart_list_id": "",
            "smart_list_name": "",
            "create_new_list": False,
            "matched_lists": [],
            "fredql_query": "",
            "email_template": "",
            "schedule_confirmed": False,
            "clarifications_needed": [],
            "clarification_responses": {},
            "current_step": "parse_prompt"
        }
    
    async def _run_workflow(self, state, config, client_id, send_msg):
        """
        Execute workflow with proper async handling
        
        Args:
            state: Initial workflow state
            config: LangGraph configuration
            client_id: Client identifier
            send_msg: Async function to send messages
        """
        # Since LangGraph doesn't fully support async nodes in invoke(),
        # we'll manually execute with checkpointing logic
        current_state = state.copy()
        self.client_sessions[client_id] = current_state
        
        # Step 1: Parse prompt
        await self._parse_prompt_step(current_state, send_msg)
        
        # Step 2: Handle clarifications (loop until all resolved)
        await self._clarification_loop(current_state, send_msg)
        
        # Step 3: Check smart lists
        await self._check_smart_lists_step(current_state, send_msg)
        
        # Step 4: Handle smart list selection
        await self._handle_smart_list_selection(current_state, send_msg)
        
        # Step 5: Show final summary or cancellation
        await self._show_final_result(current_state, send_msg, client_id)
    
    async def _parse_prompt_step(self, state, send_msg):
        """Parse the user's campaign prompt"""
        await send_msg({
            "type": "assistant",
            "message": "Let me parse your campaign requirements...",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": True
        })
        
        parse_result = parse_prompt(state, self.llm)
        state.update(parse_result)
        
        await send_msg({
            "type": "assistant",
            "message": f"✓ Understood:\n• Audience: {state['audience']}\n• Campaign: {state['template']}\n• Schedule: {state['datetime']}",
            "timestamp": asyncio.get_event_loop().time(),
            "disable_input": True
        })
    
    async def _clarification_loop(self, state, send_msg):
        """Handle clarification questions in a loop"""
        while state.get("clarifications_needed") and len(state["clarifications_needed"]) > 0:
            clarification_result = await websocket_nodes.ask_clarifications_ws(state, send_msg)
            state.update(clarification_result)
            
            process_result = process_clarifications(state, self.llm)
            state.update(process_result)
    
    async def _check_smart_lists_step(self, state, send_msg):
        """Check for existing smart lists"""
        if state["current_step"] in ["check_clarifications", "clarify_ambiguity"]:
            await send_msg({
                "type": "assistant_thinking",
                "message": "Checking for existing smart lists...",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": True
            })
            
            check_result = await websocket_nodes.fetch_and_match_smart_lists_wrapper(state, self.llm)
            state.update(check_result)
    
    async def _handle_smart_list_selection(self, state, send_msg):
        """Handle smart list selection or new list creation"""
        if state["current_step"] == "confirm_smart_list_selection":
            result = await websocket_nodes.confirm_smart_list_selection_ws(state, send_msg)
            state.update(result)
        elif state["current_step"] == "confirm_new_list":
            result = await websocket_nodes.confirm_new_list_ws(state, send_msg)
            state.update(result)
        
        # After selection/confirmation, check what to do next
        if state["current_step"] == "generate_fredql":
            await self._generate_fredql(state, send_msg)
        elif state["current_step"] == "complete_selection":
            # Just mark as complete, ready for final summary
            state["current_step"] = "end_for_now"
    
    async def _generate_fredql(self, state, send_msg):
        """Generate FredQL query for new smart list"""
        result = await websocket_nodes.generate_smart_list_fredql_ws(state, self.llm, send_msg)
        state.update(result)
    
    async def _show_final_result(self, state, send_msg, client_id):
        """Show final summary or cancellation message"""
        if state["current_step"] == "end_for_now":
            summary = self._build_campaign_summary(state)
            
            await send_msg({
                "type": "assistant",
                "message": summary,
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            
            self._cleanup_client(client_id)
        
        elif state["current_step"] == "cancelled":
            await send_msg({
                "type": "system",
                "message": "Campaign creation cancelled. Start a new conversation to create another campaign.",
                "timestamp": asyncio.get_event_loop().time(),
                "disable_input": False
            })
            
            self._cleanup_client(client_id)
    
    def _build_campaign_summary(self, state: dict) -> str:
        """Build final campaign summary message"""
        summary = "✅ Campaign setup complete!\n\n"
        summary += f"📊 **Audience:** {state['audience']}\n"
        summary += f"📧 **Campaign:** {state['template']}\n"
        summary += f"📅 **Schedule:** {state['datetime']}\n"
        
        if state.get('create_new_list'):
            summary += f"📋 **Smart List:** New list will be created\n"
            if state.get('fredql_query'):
                summary += f"   FredQL query generated ✓\n"
        elif state.get('smart_list_id'):
            summary += f"📋 **Smart List:** {state.get('smart_list_name', 'Selected')}\n"
        
        return summary
    
    def _cleanup_client(self, client_id: str):
        """Clean up client session and workflow"""
        if client_id in self.client_sessions:
            del self.client_sessions[client_id]
        if client_id in self.client_workflows:
            del self.client_workflows[client_id]

