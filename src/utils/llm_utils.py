"""
Utility functions for LLM initialization
"""

import os
from dotenv import load_dotenv

load_dotenv()


def get_llm(temperature: float = 0.7):
    """
    Initialize and return the appropriate LLM based on environment configuration.
    
    Args:
        temperature: Temperature setting for the LLM (default: 0.7)
    
    Returns:
        LLM instance (either ChatOpenAI or ChatGroq)
    
    Environment Variables:
        USE_OPEN_AI_MODEL: "true" to use OpenAI, "false" to use Groq
        OPEN_AI_KEY: OpenAI API key (required if USE_OPEN_AI_MODEL=true)
        OPEN_AI_MODEL: OpenAI model name (e.g., "gpt-4", "gpt-3.5-turbo")
        GROQ_API_KEY: Groq API key (required if USE_OPEN_AI_MODEL=false)
        GROQ_MODEL: Groq model name (e.g., "openai/gpt-oss-120b", "llama-3.1-70b-versatile")
    """
    use_openai = os.getenv("USE_OPEN_AI_MODEL", "false").lower() == "true"
    
    if use_openai:
        # Use OpenAI
        from langchain_openai import ChatOpenAI
        
        api_key = os.getenv("OPEN_AI_KEY")
        model_name = os.getenv("OPEN_AI_MODEL", "gpt-4")
        
        if not api_key:
            raise ValueError("OPEN_AI_KEY environment variable is required when USE_OPEN_AI_MODEL=true")
        
        return ChatOpenAI(
            temperature=temperature,
            model_name=model_name,
            openai_api_key=api_key
        )
    else:
        # Use Groq
        from langchain_groq import ChatGroq
        
        api_key = os.getenv("GROQ_API_KEY")
        model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is required when USE_OPEN_AI_MODEL=false")
        
        return ChatGroq(
            temperature=temperature,
            model_name=model_name,
            groq_api_key=api_key
        )

