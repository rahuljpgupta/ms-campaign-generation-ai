"""
Utility functions for fetching images for email templates via Pexels API
"""

import os
import httpx
from typing import Optional


async def get_pexels_images(query: str, count: int = 3, api_key: Optional[str] = None) -> dict:
    """
    Fetch images from Pexels API based on search query.
    
    Args:
        query: Search query describing the desired images (e.g., "christmas", "fitness", "yoga")
        count: Number of images to return (1-15, default: 3)
        api_key: Pexels API key (optional, uses env var if not provided)
    
    Returns:
        Dictionary with list of images or error information.
        On success: {
            "success": True, 
            "images": [
                {
                    "url": "https://...",
                    "alt_description": "...",
                    "photographer": "...",
                    "photographer_url": "...",
                    "width": 1920,
                    "height": 1280
                },
                ...
            ],
            "message": "..."
        }
        On error: {"error": "...", "message": "..."}
    """
    _api_key = api_key or os.getenv("PEXELS_API_KEY", "")
    
    if not _api_key:
        return {
            "error": "PEXELS_API_KEY not configured",
            "message": "Please provide api_key parameter or set PEXELS_API_KEY in .env file"
        }
    
    # Validate count (Pexels allows 1-80 per_page, we'll limit to 15 for our use case)
    count = max(1, min(15, count))
    
    # Pexels API endpoint
    url = "https://api.pexels.com/v1/search"
    
    headers = {
        "Authorization": _api_key
    }
    
    params = {
        "query": query,
        "per_page": count,
        "orientation": "landscape"  # Best for email templates
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            
            images = []
            for photo in data.get("photos", [])[:count]:
                images.append({
                    "url": photo["src"]["large"],  # High quality, suitable for email
                    "alt_description": photo.get("alt") or query,
                    "photographer": photo["photographer"],
                    "photographer_url": photo["photographer_url"],
                    "width": photo["width"],
                    "height": photo["height"]
                })
            
            return {
                "success": True,
                "images": images,
                "message": f"Found {len(images)} images for '{query}' from Pexels"
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

