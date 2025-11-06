"""
MCP Server for Frederick Campaigns API

Provides tools to interact with Frederick's campaigns.
"""

import os
import json
from typing import Optional, Dict, Any
import httpx
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize MCP server
mcp = FastMCP("Frederick Campaigns")

# Configuration
FREDERICK_API_BASE = os.getenv("FREDERICK_API_BASE", "https://api.staging.hirefrederick.com/v2")
FREDERICK_API_KEY = os.getenv("FREDERICK_API_KEY")
FREDERICK_BEARER_TOKEN = os.getenv("FREDERICK_BEARER_TOKEN")


@mcp.tool()
async def create_campaign(
    location_id: str,
    name: str,
    subject_line: str,
    custom_html_template: bool = True,
    api_key: Optional[str] = None,
    bearer_token: Optional[str] = None,
    api_url: Optional[str] = None
) -> dict:
    """
    Create a new campaign for a specific location.
    
    Args:
        location_id: Frederick location ID
        name: Campaign name (e.g., "Custom HTML - Nov 5, 2025 at 8:31 AM")
        subject_line: Email subject line (e.g., "News from Ninja Training")
        custom_html_template: Whether to use custom HTML template (default: True)
        api_key: Frederick API key (optional, uses env var if not provided)
        bearer_token: Frederick bearer token (optional, uses env var if not provided)
        api_url: Frederick API base URL (optional, uses env var if not provided)
    
    Returns:
        Dictionary with created campaign data or error information.
        On success: {"success": True, "data": {...}, "message": "..."}
        On error: {"error": "...", "message": "...", "status_code": ...}
    """
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
    
    url = f"{_api_base}/locations/{location_id}/campaigns"
    
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
            "type": "campaigns",
            "attributes": {
                "custom_html_template": custom_html_template,
                "name": f"AI - {name}",
                "subject_line": subject_line
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
                "message": f"Campaign '{name}' created successfully"
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
async def create_email_document(
    location_id: str,
    campaign_id: str,
    html: str,
    document: Optional[str] = "{}",
    api_key: Optional[str] = None,
    bearer_token: Optional[str] = None,
    api_url: Optional[str] = None
) -> dict:
    """
    Create an email document for a specific campaign.
    
    Args:
        location_id: Frederick location ID
        campaign_id: Campaign ID to attach this email document to
        html: HTML content of the email (must include unsubscribe link)
        document: Document structure (default: "{}")
        api_key: Frederick API key (optional, uses env var if not provided)
        bearer_token: Frederick bearer token (optional, uses env var if not provided)
        api_url: Frederick API base URL (optional, uses env var if not provided)
    
    Returns:
        Dictionary with created email document data or error information.
        On success: {"success": True, "data": {...}, "message": "..."}
        On error: {"error": "...", "message": "...", "status_code": ...}
    """
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
    
    url = f"{_api_base}/locations/{location_id}/email_documents"
    
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
            "type": "email_documents",
            "attributes": {
                "campaign_id": campaign_id,
                "document": document,
                "html": html
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
                "message": f"Email document created successfully for campaign {campaign_id}"
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
async def get_social_profile_links(
    source_platform: Optional[str] = None,
    source_location_id: Optional[str] = None,
    source_customer_id: Optional[str] = None,
    api_key: Optional[str] = None,
    bearer_token: Optional[str] = None,
    api_url: Optional[str] = None
) -> dict:
    """
    Fetch social profile links from Frederick API.
    Requires X-Universal-Customer header with source platform information.
    
    Args:
        source_platform: Source platform (e.g., "booker", "mindbody")
        source_location_id: Source location ID
        source_customer_id: Source customer ID
        api_key: Frederick API key
        bearer_token: Frederick bearer token
        api_url: Frederick API base URL (optional, uses env var if not provided)
    
    Returns:
        Dictionary with social profile links data or error information.
        On success: {"success": True, "data": [...]}
        On error: {"error": "...", "message": "...", "status_code": ...}
    """
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
    
    url = f"{_api_base}/social_profile_links"
    
    headers = {
        "accept": "application/vnd.api+json",
        "authorization": f"Bearer {_bearer_token}",
        "x-api-key": _api_key,
        "user-agent": "Frederick-Campaign-Generator/1.0"
    }
    
    # Add X-Universal-Customer header if source information is provided
    if source_platform and source_location_id and source_customer_id:
        import json
        universal_customer = {
            "source_platform": source_platform,
            "source_location_id": source_location_id,
            "source_customer_id": source_customer_id
        }
        headers["X-Universal-Customer"] = json.dumps(universal_customer)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            
            return {
                "success": True,
                "data": data.get("data", [])
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
async def get_latest_campaign_emails(
    location_id: str,
    api_key: Optional[str] = None,
    bearer_token: Optional[str] = None,
    api_url: Optional[str] = None
) -> dict:
    """
    Fetch the latest custom HTML campaign emails for a specific location.
    Returns only the HTML content to save context window tokens.
    
    Args:
        location_id: Frederick location ID
        api_key: Frederick API key (optional, uses env var if not provided)
        bearer_token: Frederick bearer token (optional, uses env var if not provided)
        api_url: Frederick API base URL (optional, uses env var if not provided)
    
    Returns:
        Dictionary with HTML content from latest emails or error information.
        On success: {"success": True, "htmls": [{"campaign_name": "...", "subject_line": "...", "html": "..."}]}
        On error: {"error": "...", "message": "...", "status_code": ...}
    """
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
    
    url = f"{_api_base}/locations/{location_id}/email_documents/latest_custom_html_emails"
    
    headers = {
        "accept": "application/vnd.api+json",
        "authorization": f"Bearer {_bearer_token}",
        "x-api-key": _api_key,
        "user-agent": "Frederick-Campaign-Generator/1.0"
    }
    
    # Set pagination parameters to get only 2 latest emails
    params = {
        "page[size]": 2
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            
            # Extract only essential fields (HTML + minimal context)
            htmls = []
            for email_doc in data.get("data", []):
                attrs = email_doc.get("attributes", {})
                html = attrs.get("html", "")
                if html:  # Only include if HTML exists
                    htmls.append({
                        "campaign_name": attrs.get("campaign_name", "Untitled"),
                        "subject_line": attrs.get("subject_line", ""),
                        "html": html
                    })
            
            return {
                "success": True,
                "htmls": htmls
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
async def get_offerings(
    source: Optional[str] = None,
    source_customer_id: Optional[str] = None,
    source_location_id: Optional[str] = None,
    interaction_filter: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
    bearer_token: Optional[str] = None,
    api_url: Optional[str] = None
) -> dict:
    """
    Fetch offerings from Frederick API with optional filters.
    
    Args:
        source: Source platform (e.g., "mindbody")
        source_customer_id: Source customer ID
        source_location_id: Source location ID
        interaction_filter: Interaction filter as a dictionary (optional)
        api_key: Frederick API key (optional, uses env var if not provided)
        bearer_token: Frederick bearer token (optional, uses env var if not provided)
        api_url: Frederick API base URL (optional, uses env var if not provided)
    
    Returns:
        Dictionary with offerings data or error information.
        On success: {"success": True, "data": [...]}
        On error: {"error": "...", "message": "...", "status_code": ...}
    
    Example interaction_filter:
        {
            "location_id": "uuid",
            "marketing_source": True,
            "source_type": "Automation",
            "communication_type": "Email",
            "metadata": {...}
        }
    """
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
    
    url = f"{_api_base}/offerings"
    
    headers = {
        "accept": "application/vnd.api+json",
        "authorization": f"Bearer {_bearer_token}",
        "x-api-key": _api_key,
        "user-agent": "Frederick-Campaign-Generator/1.0"
    }
    
    # Build query parameters
    params = {}
    if source:
        params["filter.source"] = source
    if source_customer_id:
        params["filter.source_customer_id"] = source_customer_id
    if source_location_id:
        params["filter.source_location_id"] = source_location_id
    if interaction_filter:
        # Convert interaction filter dict to JSON string
        params["filter.interaction"] = json.dumps(interaction_filter)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            
            return {
                "success": True,
                "data": data.get("data", [])
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

