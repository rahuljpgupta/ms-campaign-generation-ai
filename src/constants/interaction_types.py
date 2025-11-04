"""
Valid interaction types for smart list filters
Synced with platatouille/client/app/bundles/Platatouille/constants/filterInteractionTypeDefaults.ts
"""

VALID_INTERACTION_TYPES = [
    "browsed_availability",
    "scheduled_future_reminder",
    "viewed_package_or_membership",
    "viewed_my_appointments",
    "submitted_lead_capture",
    "unsubscribed_transactional_text_messages",
    "clicked_link",
    "unsubscribed_marketing_text_messages",
    "unsubscribed_all_text_messages",
    "referred_customer",
    "dismissed_recommendation",
    "qualified_for_automation",
    "subscribed_marketing_emails",
    "delivered_email",
    "unsubscribed_transactional_emails",
    "subscribed_transactional_text_messages",
    "added_to_cart",
    "undeliverable_email",
    "viewed_map",
    "subscribed_transactional_emails",
    "contact_created",
    "confirmed_appointment",
    "unsubscribed_all_emails",
    "requested_appointment",
    "unsubscribed_from_this_offer",
    "opened_email",
    "visited",
    "unsubscribed_marketing_emails",
    "unexcluded_from_automation",
    "claimed_referral_offer",
    "contact_updated",
    "booked_appointment",
    "shared_referral_link",
    "viewed_website_after_booking",
    "removed_from_cart",
    "viewed_referral_program",
    "called_business",
    "submitted_feedback",
    "spam_report",
    "deactivated_vehicle",
    "visited_website",
    "delivered_text_message",
    "expressed_future_interest",
    "excluded_from_automation",
    "visited_profile_link",
    "viewed_referral_claim_form",
    "subscribed_marketing_text_messages",
    "updated_preference",
    "disqualified_for_automation",
    "purchased",
]

# Human-readable descriptions for common interaction types
INTERACTION_TYPE_DESCRIPTIONS = {
    "booked_appointment": "Contact booked an appointment",
    "confirmed_appointment": "Contact confirmed an appointment",
    "requested_appointment": "Contact requested an appointment",
    "purchased": "Contact made a purchase",
    "visited_website": "Contact visited the website",
    "opened_email": "Contact opened an email",
    "clicked_link": "Contact clicked a link",
    "submitted_lead_capture": "Contact submitted a lead form",
    "subscribed_marketing_emails": "Contact subscribed to marketing emails",
    "unsubscribed_marketing_emails": "Contact unsubscribed from marketing emails",
    "subscribed_marketing_text_messages": "Contact subscribed to marketing text messages",
    "unsubscribed_marketing_text_messages": "Contact unsubscribed from marketing text messages",
    "contact_created": "Contact was created",
    "contact_updated": "Contact information was updated",
    "delivered_email": "Email was delivered to contact",
    "delivered_text_message": "Text message was delivered to contact",
    "added_to_cart": "Contact added item to cart",
    "removed_from_cart": "Contact removed item from cart",
    "browsed_availability": "Contact browsed availability",
    "called_business": "Contact called the business",
    "submitted_feedback": "Contact submitted feedback",
    "referred_customer": "Contact referred another customer",
    "claimed_referral_offer": "Contact claimed a referral offer",
}


def validate_interaction_types(fredql_query: dict) -> tuple[bool, list[str]]:
    """
    Validate that all interaction types in FredQL query are valid
    
    Args:
        fredql_query: The FredQL query dictionary
    
    Returns:
        Tuple of (is_valid, list_of_invalid_types)
    """
    invalid_types = []
    
    def check_filters(filters):
        """Recursively check filters for interaction types"""
        if not filters:
            return
        
        for filter_item in filters:
            # Check if this is an interaction filter
            if isinstance(filter_item, dict):
                if filter_item.get("type") == "interaction":
                    interaction_type = filter_item.get("interaction_type")
                    if interaction_type and interaction_type not in VALID_INTERACTION_TYPES:
                        invalid_types.append(interaction_type)
                
                # Check nested filters (AND/OR groups)
                if "filters" in filter_item:
                    check_filters(filter_item["filters"])
    
    # Check top-level filters
    if "filters" in fredql_query:
        check_filters(fredql_query["filters"])
    
    return len(invalid_types) == 0, invalid_types


def get_interaction_types_list() -> str:
    """
    Get a formatted string of valid interaction types for prompt injection
    
    Returns:
        Formatted string with all valid interaction types
    """
    return "\n".join([f"  - {it}" for it in VALID_INTERACTION_TYPES])

