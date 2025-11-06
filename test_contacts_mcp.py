"""
Test script for contacts MCP server

Usage:
    python test_contacts_mcp.py
"""

import asyncio
import os
from dotenv import load_dotenv

# Import the tools from MCP server
from src.mcp.contacts_mcp import get_existing_smart_lists

load_dotenv()


async def test_get_existing_smart_lists():
    """Test fetching all smart lists"""
    location_id = os.getenv("FREDERICK_LOCATION_ID")
    
    if not location_id:
        print("❌ FREDERICK_LOCATION_ID not set in .env file")
        return
    
    print(f"\n{'='*80}")
    print(f"Testing: Get Smart Lists for Location {location_id}")
    print(f"{'='*80}")
    
    result = await get_existing_smart_lists(location_id)
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        print(f"   Message: {result['message']}")
    else:
        data = result.get("data", [])
        total_smart = result.get("total_smart_lists", 0)
        total_all = result.get("total_all_lists", 0)
        
        print(f"✓ Found {total_smart} smart lists (out of {total_all} total lists)")
        
        # Display first 5 lists
        for i, item in enumerate(data[:5], 1):
            attrs = item.get("attributes", {})
            print(f"\n  {i}. {attrs.get('display_name') or attrs.get('name', 'N/A')}")
            print(f"     ID: {item.get('id')}")
            print(f"     Name: {attrs.get('name', 'N/A')}")
            filters = attrs.get('filters', [])
            if filters:
                print(f"     Filters ({len(filters)} filter(s)):")
                for j, f in enumerate(filters[:3], 1):  # Show first 3 filters
                    print(f"       {j}. {f}")
                if len(filters) > 3:
                    print(f"       ... and {len(filters) - 3} more")


async def main():
    """Run all tests"""
    print("="*80)
    print("Frederick Contacts MCP Server - Test Suite")
    print("="*80)
    
    # Test 1: Get all smart lists
    await test_get_existing_smart_lists()
    
    print("\n" + "="*80)
    print("Tests Complete!")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())

