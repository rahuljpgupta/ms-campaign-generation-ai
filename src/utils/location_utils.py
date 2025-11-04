"""
Utility functions for working with location data
"""


def format_location_context(location: dict) -> str:
    """
    Format location data into a readable context string for LLM prompts
    
    Args:
        location: Dictionary containing location information
        
    Returns:
        Formatted string with location context
    """
    if not location:
        return "Location information not available."
    
    context_parts = []
    
    # Business name
    if name := location.get('name'):
        context_parts.append(f"Business Name: {name}")
    
    # Location ID
    if loc_id := location.get('id'):
        context_parts.append(f"Location ID: {loc_id}")
    
    # Timezone
    if timezone := location.get('timezone'):
        context_parts.append(f"Timezone: {timezone}")
    
    # Management system
    if mgmt_system := location.get('management_system'):
        context_parts.append(f"Management System: {mgmt_system}")
    
    # Website
    if website := location.get('website'):
        context_parts.append(f"Website: {website}")
    
    # Booking site
    if booking_site := location.get('booking_site'):
        context_parts.append(f"Booking Site: {booking_site}")
    
    # Phone number
    if phone := location.get('formatted_phone_number'):
        context_parts.append(f"Phone: {phone}")
    
    # Address components
    address_parts = []
    if state := location.get('state'):
        address_parts.append(state)
    if postal := location.get('postal_code'):
        address_parts.append(postal)
    if country := location.get('country'):
        address_parts.append(country)
    elif country_code := location.get('country_code'):
        address_parts.append(country_code)
    
    if address_parts:
        context_parts.append(f"Location: {', '.join(address_parts)}")
    
    # Currency
    if currency := location.get('currency'):
        context_parts.append(f"Currency: {currency}")
    
    if not context_parts:
        return "Location information not available."
    
    return "- " + "\n- ".join(context_parts)

