"""
Marketing Campaign Generator using LangChain and LangGraph

Main orchestration class for campaign generation workflow.
"""

import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
import chromadb

from .workflow import build_workflow

# Load environment variables
load_dotenv()


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
        
        # Build the workflow graph
        self.workflow = build_workflow(self.llm)
    
    def run(self, user_prompt: str, location_id: str = None) -> dict:
        """
        Run the campaign generation workflow
        
        Args:
            user_prompt: Campaign description from user
            location_id: Frederick location ID (optional, defaults to env variable)
        """
        initial_state = {
            "user_prompt": user_prompt,
            "audience": "",
            "template": "",
            "datetime": "",
            "location_id": location_id or os.getenv("FREDERICK_LOCATION_ID", ""),
            "smart_list_id": "",
            "smart_list_name": "",
            "create_new_list": False,
            "email_template": "",
            "schedule_confirmed": False,
            "clarifications_needed": [],
            "clarification_responses": {},
            "matched_lists": [],
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

