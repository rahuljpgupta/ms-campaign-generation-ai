"""
MCP Server for Frederick Contacts API

Provides tools to interact with Frederick's contact lists and smart lists.
"""

import os
from typing import Optional
import httpx
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize MCP server
mcp = FastMCP("Frederick Contacts")

# Configuration
FREDERICK_API_BASE = os.getenv("FREDERICK_API_BASE", "https://api.staging.hirefrederick.com/v2")
FREDERICK_API_KEY = os.getenv("FREDERICK_API_KEY")
FREDERICK_BEARER_TOKEN = os.getenv("FREDERICK_BEARER_TOKEN")


@mcp.tool()
async def get_existing_smart_lists(location_id: str, page_size: int = 1000) -> dict:
    """
    Fetch all smart lists (contact lists with list_type='smart') for a specific location.
    Returns only smart lists with filtered fields: name, display_name, filters
    
    Args:
        location_id: The Frederick location ID to fetch smart lists for
        page_size: Number of results per page (default: 1000)
    
    Returns:
        Dictionary containing smart lists data with structure:
        {
            "data": [
                {
                    "id": "list_id",
                    "attributes": {
                        "name": "List Name",
                        "display_name": "Display Name",
                        "filters": [...]  // Array of filter objects
                    }
                }
            ],
            "total_smart_lists": 5,
            "total_all_lists": 10
        }
    """
    if not FREDERICK_API_KEY:
        return {
            "error": "FREDERICK_API_KEY not configured",
            "message": "Please set FREDERICK_API_KEY in .env file"
        }
    
    if not FREDERICK_BEARER_TOKEN:
        return {
            "error": "FREDERICK_BEARER_TOKEN not configured",
            "message": "Please set FREDERICK_BEARER_TOKEN in .env file"
        }
    
    url = f"{FREDERICK_API_BASE}/locations/{location_id}/contact_lists"
    
    headers = {
        "accept": "application/vnd.api+json",
        "authorization": f"Bearer {FREDERICK_BEARER_TOKEN}",
        "x-api-key": FREDERICK_API_KEY,
        "user-agent": "Frederick-Campaign-Generator/1.0"
    }
    
    params = {
        "page.size": page_size
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            
            # Filter for smart lists only and extract specified fields
            all_lists = data.get("data", [])
            smart_lists = []
            
            for item in all_lists:
                attrs = item.get("attributes", {})
                
                # Only include smart lists
                if attrs.get("list_type") == "smart":
                    smart_lists.append({
                        "id": item.get("id"),
                        "attributes": {
                            "name": attrs.get("name"),
                            "display_name": attrs.get("display_name"),
                            "filters": attrs.get("filters")
                        }
                    })
            
            return {
                "data": smart_lists,
                "total_smart_lists": len(smart_lists),
                "total_all_lists": len(all_lists)
            }
            
    except httpx.HTTPStatusError as e:
        return {
            "error": "HTTP error",
            "status_code": e.response.status_code,
            "message": str(e),
            "response": e.response.text
        }
    except httpx.RequestError as e:
        return {
            "error": "Request error",
            "message": str(e)
        }
    except Exception as e:
        return {
            "error": "Unexpected error",
            "message": str(e)
        }

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()

