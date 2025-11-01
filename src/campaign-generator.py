"""
Marketing Campaign Generator using LangChain and LangGraph

Main orchestration flow:
1. Parse user prompt (audience, template, datetime)
2. Clarify ambiguous/missing information
3. Create/verify smart list for audience
4. Generate email template with existing assets
5. Allow template editing
6. Confirm and schedule campaign
"""

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
import chromadb
from dotenv import load_dotenv
import os
import json
from PIL import Image
from io import BytesIO

# Load environment variables
load_dotenv()


# Pydantic model for parsed prompt output
class ParsedPrompt(BaseModel):
    """Structured output for parsed campaign prompt"""
    audience: str = Field(description="Target audience criteria (e.g., contacts in New York who visited studio)")
    template: str = Field(description="Campaign content details (e.g., 30% discount on Black Friday promotion)")
    datetime: str = Field(description="Scheduled date and time (e.g., 30th November 9AM)")
    missing_info: list[str] = Field(description="List of missing or ambiguous information that needs clarification")


# Define the state structure for the workflow
class CampaignState(TypedDict):
    """State for campaign generation workflow"""
    user_prompt: str
    audience: str
    template: str
    datetime: str
    smart_list_id: str
    email_template: str
    schedule_confirmed: bool
    clarifications_needed: list[str]
    clarification_responses: dict[str, str]  # Store user's clarification answers
    current_step: str


class CampaignGenerator:
    """Main campaign generator orchestrator"""
    
    def __init__(self):
        # Initialize LLM (Groq)
        self.llm = ChatGroq(
            temperature=0.7,
            model_name="openai/gpt-oss-120b",
            groq_api_key=os.getenv("GROQ_API_KEY")
        )
        
        # Initialize embeddings (HuggingFace)
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        
        # Initialize vector store (ChromaDB)
        self.chroma_client = chromadb.Client()
        
        # Initialize the workflow graph
        self.workflow = self._build_workflow()
    
    def parse_prompt(self, state: CampaignState) -> dict:
        """Parse user prompt into audience, template, and datetime components"""
        print(f"\n[STEP 1] Parsing prompt: {state['user_prompt']}")
        
        # Create prompt template for parsing
        parse_prompt = ChatPromptTemplate.from_messages([
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
        
        # Create parser
        parser = JsonOutputParser(pydantic_object=ParsedPrompt)
        
        # Create chain
        chain = parse_prompt | self.llm | parser
        
        # Execute parsing
        try:
            result = chain.invoke({"prompt": state["user_prompt"]})
            
            print(f"\nParsed Results:")
            print(f"  Audience: {result['audience']}")
            print(f"  Template: {result['template']}")
            print(f"  DateTime: {result['datetime']}")
            if result['missing_info']:
                print(f"  Missing Info: {', '.join(result['missing_info'])}")
            
            return {
                "audience": result["audience"],
                "template": result["template"],
                "datetime": result["datetime"],
                "clarifications_needed": result["missing_info"],
                "current_step": "clarify_ambiguity"
            }
        except Exception as e:
            print(f"Error parsing prompt: {e}")
            return {
                "clarifications_needed": [f"Failed to parse prompt: {str(e)}"],
                "current_step": "parse_prompt"
            }
    
    def check_clarifications(self, state: CampaignState) -> dict:
        """
        Check if there are any clarifications needed.
        Returns routing decision for conditional edge.
        """
        if state.get("clarifications_needed") and len(state["clarifications_needed"]) > 0:
            print(f"\n[STEP 2] Found {len(state['clarifications_needed'])} clarification(s) needed")
            return {"current_step": "ask_clarifications"}
        else:
            print(f"\n[STEP 2] All clarifications resolved, proceeding to next step")
            return {"current_step": "check_smart_list"}
    
    def ask_clarifications(self, state: CampaignState) -> dict:
        """
        Ask user for clarifications on missing or ambiguous information.
        This is an interactive step that collects user input.
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
    
    def process_clarifications(self, state: CampaignState) -> dict:
        """
        Process user's clarification responses and update the campaign state.
        Re-parse or refine the audience, template, and datetime based on clarifications.
        """
        print(f"\n[STEP 3] Processing clarification responses...")
        
        # Build a context from clarifications
        clarification_context = "\n".join([
            f"Q: {q}\nA: {a}" 
            for q, a in state["clarification_responses"].items()
        ])
        
        # Create prompt to update the campaign details with clarifications
        update_prompt = ChatPromptTemplate.from_messages([
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
        
        # Create parser
        parser = JsonOutputParser(pydantic_object=ParsedPrompt)
        
        # Create chain
        chain = update_prompt | self.llm | parser
        
        try:
            result = chain.invoke({
                "audience": state.get("audience", ""),
                "template": state.get("template", ""),
                "datetime": state.get("datetime", ""),
                "clarifications": clarification_context
            })
            
            print(f"\nUpdated Campaign Details:")
            print(f"  Audience: {result['audience']}")
            print(f"  Template: {result['template']}")
            print(f"  DateTime: {result['datetime']}")
            
            if result['missing_info']:
                print(f"  Still Missing: {', '.join(result['missing_info'])}")
            else:
                print(f"  ✓ All information is now complete!")
            
            return {
                "audience": result["audience"],
                "template": result["template"],
                "datetime": result["datetime"],
                "clarifications_needed": result["missing_info"],
                "current_step": "check_clarifications"
            }
        except Exception as e:
            print(f"Error processing clarifications: {e}")
            return {
                "clarifications_needed": [f"Failed to process clarifications: {str(e)}"],
                "current_step": "ask_clarifications"
            }
    
    def route_after_clarification_check(self, state: CampaignState) -> str:
        """
        Routing function to decide next step after checking clarifications.
        Returns the name of the next node.
        """
        if state.get("clarifications_needed") and len(state["clarifications_needed"]) > 0:
            return "ask_clarifications"
        else:
            # All clarifications resolved, move to next major step
            return "end_for_now"
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(CampaignState)
        
        # Add nodes for the workflow
        workflow.add_node("parse_prompt", self.parse_prompt)
        workflow.add_node("ask_clarifications", self.ask_clarifications)
        workflow.add_node("process_clarifications", self.process_clarifications)
        workflow.add_node("end_for_now", lambda state: {"current_step": "completed"})
        
        # TODO: Add more nodes for future steps
        # - check_smart_list
        # - create_smart_list
        # - generate_template
        # - confirm_schedule
        
        # Set entry point
        workflow.set_entry_point("parse_prompt")
        
        # Add edges
        # After parsing, check if clarifications are needed
        workflow.add_conditional_edges(
            "parse_prompt",
            self.route_after_clarification_check,
            {
                "ask_clarifications": "ask_clarifications",
                "end_for_now": "end_for_now"
            }
        )
        
        # After asking clarifications, process them
        workflow.add_edge("ask_clarifications", "process_clarifications")
        
        # After processing clarifications, check again if more clarifications needed (loop)
        workflow.add_conditional_edges(
            "process_clarifications",
            self.route_after_clarification_check,
            {
                "ask_clarifications": "ask_clarifications",  # Loop back if still need clarifications
                "end_for_now": "end_for_now"  # Continue if all clear
            }
        )
        
        # End node
        workflow.add_edge("end_for_now", END)
        
        return workflow.compile()
    
    def run(self, user_prompt: str) -> dict:
        """Run the campaign generation workflow"""
        initial_state = {
            "user_prompt": user_prompt,
            "audience": "",
            "template": "",
            "datetime": "",
            "smart_list_id": "",
            "email_template": "",
            "schedule_confirmed": False,
            "clarifications_needed": [],
            "clarification_responses": {},
            "current_step": "parse_prompt"
        }
        
        # Execute workflow
        final_state = self.workflow.invoke(initial_state)
        return final_state
    
    def draw_workflow(self, output_path: str = "workflow_graph.png"):
        """
        Draw and save the workflow graph visualization
        
        Args:
            output_path: Path where the graph image will be saved
        """
        try:
            # Get the graph as PNG bytes
            graph_image = self.workflow.get_graph().draw_mermaid_png()
            
            # Save to file
            with open(output_path, "wb") as f:
                f.write(graph_image)
            
            print(f"\n✓ Workflow graph saved to: {output_path}")
            return output_path
        except Exception as e:
            print(f"\n✗ Failed to draw workflow graph: {e}")
            print("  Note: You may need to install graphviz system package:")
            print("  - macOS: brew install graphviz")
            print("  - Ubuntu: sudo apt-get install graphviz")
            return None


if __name__ == "__main__":
    # Test the parse_prompt and clarification steps
    print("=" * 80)
    print("Campaign Generator - Interactive Workflow Test")
    print("=" * 80)
    
    generator = CampaignGenerator()
    
    # Draw the workflow graph
    print("\n[Drawing Workflow Graph]")
    generator.draw_workflow("campaign_workflow.png")
    
    # Test with a prompt that might need clarifications
    print("\n" + "=" * 80)
    print("Enter your campaign prompt (or press Enter for default example):")
    print("=" * 80)
    user_input = input("Prompt: ").strip()
    
    if not user_input:
        # Use example prompt with some ambiguity
        test_prompt = """Create a Black Friday sale campaign for contacts in New York 
        offering a discount and send it on Black Friday"""
        print(f"\nUsing example prompt: {test_prompt}")
    else:
        test_prompt = user_input
    
    result = generator.run(test_prompt)
    
    print("\n" + "=" * 80)
    print("WORKFLOW COMPLETED - Final Campaign State:")
    print("=" * 80)
    print(f"\nAudience: {result.get('audience', 'N/A')}")
    print(f"Template: {result.get('template', 'N/A')}")
    print(f"DateTime: {result.get('datetime', 'N/A')}")
    print(f"\nStatus: {result.get('current_step', 'Unknown')}")
    
    if result.get('clarification_responses'):
        print(f"\nClarifications Provided:")
        for q, a in result['clarification_responses'].items():
            print(f"  Q: {q}")
            print(f"  A: {a}")

