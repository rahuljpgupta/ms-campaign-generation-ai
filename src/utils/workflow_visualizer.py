"""
Workflow visualization utility
"""

import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()


def draw_workflow_graph(output_path: str = "workflow_graph.png") -> str:
    """
    Generate and save workflow graph visualization
    
    Args:
        output_path: Path where the graph image will be saved
        
    Returns:
        Path to saved graph or None if failed
    """
    try:
        from ..workflows.websocket_workflow import build_websocket_workflow
        
        # Initialize LLM
        llm = ChatGroq(
            temperature=0.7,
            model_name="openai/gpt-oss-120b",
            groq_api_key=os.getenv("GROQ_API_KEY")
        )
        
        # Dummy send message function
        async def dummy_send(msg):
            pass
        
        # Build workflow
        workflow = build_websocket_workflow(llm, dummy_send)
        
        # Generate and save graph
        graph_image = workflow.get_graph().draw_mermaid_png()
        
        with open(output_path, "wb") as f:
            f.write(graph_image)
        
        return output_path
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure graphviz is installed:")
        print("  macOS: brew install graphviz")
        print("  Ubuntu: sudo apt-get install graphviz")
        return None

