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
async def get_contact_properties(
    location_id: str,
    page_size: int = 1000,
    page_number: int = 1,
    api_key: Optional[str] = None,
    bearer_token: Optional[str] = None,
    api_url: Optional[str] = None
) -> dict:
    """
    Fetch all contact properties for a specific location.
    Returns property definitions including name, display_name, property_type, etc.
    
    Args:
        location_id: The Frederick location ID to fetch contact properties for
        page_size: Number of results per page (default: 1000)
        page_number: Page number to fetch (default: 1)
        api_key: Optional API key (falls back to env var)
        bearer_token: Optional bearer token (falls back to env var)
        api_url: Optional API base URL (falls back to env var)
    
    Returns:
        Dictionary containing contact properties data with structure:
        {
            "data": [
                {
                    "id": "property_id",
                    "attributes": {
                        "name": "property_name",
                        "display_name": "Display Name",
                        "property_type": "string|number|date|boolean|multi_select",
                        "options": [...],  // For multi_select types
                        "required": true|false,
                        "system_property": true|false
                    }
                }
            ],
            "total": 42
        }
    """
    # Use provided credentials or fall back to environment variables
    _api_key = api_key or FREDERICK_API_KEY
    _bearer_token = bearer_token or FREDERICK_BEARER_TOKEN
    _api_base = api_url or FREDERICK_API_BASE
    
    if not _api_key:
        return {
            "error": "FREDERICK_API_KEY not configured",
            "message": "Please provide api_key parameter or set FREDERICK_API_KEY in .env file"
        }
    
    if not _bearer_token:
        return {
            "error": "FREDERICK_BEARER_TOKEN not configured",
            "message": "Please provide bearer_token parameter or set FREDERICK_BEARER_TOKEN in .env file"
        }
    
    # Ensure URL has /v2 path if not already present
    if not _api_base.endswith('/v2'):
        _api_base = f"{_api_base}/v2"
    
    url = f"{_api_base}/locations/{location_id}/contact_properties"
    
    headers = {
        "accept": "application/vnd.api+json",
        "authorization": f"Bearer {_bearer_token}",
        "x-api-key": _api_key,
        "user-agent": "Frederick-Campaign-Generator/1.0"
    }
    
    params = {
        "page.size": page_size,
        "page.number": page_number
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "data": data.get("data", []),
                    "total": len(data.get("data", [])),
                    "meta": data.get("meta", {})
                }
            else:
                return {
                    "error": f"HTTP {response.status_code}",
                    "message": response.text,
                    "status_code": response.status_code
                }
    except httpx.TimeoutException:
        return {
            "error": "Request timeout",
            "message": "The request to Frederick API timed out after 30 seconds"
        }
    except Exception as e:
        return {
            "error": "Request failed",
            "message": str(e)
        }


@mcp.tool()
async def get_existing_smart_lists(
    location_id: str, 
    page_size: int = 1000,
    api_key: Optional[str] = None,
    bearer_token: Optional[str] = None,
    api_url: Optional[str] = None
) -> dict:
    """
    Fetch all smart lists (contact lists with list_type='smart') for a specific location.
    Returns only smart lists with filtered fields: name, display_name, filters
    
    Args:
        location_id: The Frederick location ID to fetch smart lists for
        page_size: Number of results per page (default: 1000)
        api_key: Optional API key (falls back to env var)
        bearer_token: Optional bearer token (falls back to env var)
        api_url: Optional API base URL (falls back to env var)
    
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
    # Use provided credentials or fall back to environment variables
    _api_key = api_key or FREDERICK_API_KEY
    _bearer_token = bearer_token or FREDERICK_BEARER_TOKEN
    _api_base = api_url or FREDERICK_API_BASE
    
    if not _api_key:
        return {
            "error": "FREDERICK_API_KEY not configured",
            "message": "Please provide api_key parameter or set FREDERICK_API_KEY in .env file"
        }
    
    if not _bearer_token:
        return {
            "error": "FREDERICK_BEARER_TOKEN not configured",
            "message": "Please provide bearer_token parameter or set FREDERICK_BEARER_TOKEN in .env file"
        }
    
    # Ensure URL has /v2 path if not already present
    if not _api_base.endswith('/v2'):
        _api_base = f"{_api_base}/v2"
    
    url = f"{_api_base}/locations/{location_id}/contact_lists"
    
    headers = {
        "accept": "application/vnd.api+json",
        "authorization": f"Bearer {_bearer_token}",
        "x-api-key": _api_key,
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

@mcp.tool()
async def create_smart_list(
    location_id: str,
    display_name: str,
    filters: list,
    api_key: Optional[str] = None,
    bearer_token: Optional[str] = None,
    api_url: Optional[str] = None
) -> dict:
    """
    Create a new smart list (contact list with list_type='smart') for a specific location.
    
    Args:
        location_id: The Frederick location ID to create the smart list for
        display_name: The display name for the smart list
        filters: Array of filter arrays (nested array structure for AND/OR logic)
        api_key: Optional API key (falls back to env var)
        bearer_token: Optional bearer token (falls back to env var)
        api_url: Optional API base URL (falls back to env var)
    
    Returns:
        Dictionary containing created smart list data or error information
    
    Example filters structure:
        [[{"filter_type": "interaction", "interaction_type": "booked_appointment", 
           "operator": "has_interaction", "communication_type": "Email"}]]
    """
    # Use provided credentials or fall back to environment variables
    _api_key = api_key or FREDERICK_API_KEY
    _bearer_token = bearer_token or FREDERICK_BEARER_TOKEN
    _api_base = api_url or FREDERICK_API_BASE
    
    if not _api_key:
        return {
            "error": "FREDERICK_API_KEY not configured",
            "message": "Please provide api_key parameter or set FREDERICK_API_KEY in .env file"
        }
    
    if not _bearer_token:
        return {
            "error": "FREDERICK_BEARER_TOKEN not configured",
            "message": "Please provide bearer_token parameter or set FREDERICK_BEARER_TOKEN in .env file"
        }
    
    # Ensure URL has /v2 path if not already present
    if not _api_base.endswith('/v2'):
        _api_base = f"{_api_base}/v2"
    
    url = f"{_api_base}/locations/{location_id}/contact_lists"
    
    headers = {
        "accept": "application/vnd.api+json",
        "content-type": "application/vnd.api+json",
        "authorization": f"Bearer {_bearer_token}",
        "x-api-key": _api_key,
        "user-agent": "Frederick-Campaign-Generator/1.0"
    }
    
    # Construct request body following JSON:API specification
    payload = {
        "data": {
            "type": "contact_lists",
            "attributes": {
                "display_name": display_name,
                "list_type": "smart",
                "filters": filters
            }
        },
        "meta": None
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            
            return {
                "success": True,
                "data": data.get("data", {}),
                "message": f"Smart list '{display_name}' created successfully"
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

