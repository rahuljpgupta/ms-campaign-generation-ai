"""
Entry point for campaign generation application
"""

from src.campaign_generator import CampaignGenerator


def main():
    """Main CLI entry point"""
    print("=" * 80)
    print("Campaign Generator - Interactive Workflow")
    print("=" * 80)
    
    generator = CampaignGenerator()
    
    # Draw the workflow graph
    print("\n[Drawing Workflow Graph]")
    generator.draw_workflow("campaign_workflow.png")
    
    # Get user input
    print("\n" + "=" * 80)
    print("Enter your campaign prompt (or press Enter for default example):")
    print("=" * 80)
    user_input = input("Prompt: ").strip()
    
    if not user_input:
        # Use example prompt with some ambiguity
        test_prompt = """Create a Black Friday sale campaign for contacts in New York 
        offering a discount and send it on Black Friday"""
        print(f"\nUsing example prompt: {test_prompt}")
    else:
        test_prompt = user_input
    
    # Run workflow
    result = generator.run(test_prompt)
    
    # Display results
    print("\n" + "=" * 80)
    print("WORKFLOW COMPLETED - Final Campaign State:")
    print("=" * 80)
    print(f"\nAudience: {result.get('audience', 'N/A')}")
    print(f"Template: {result.get('template', 'N/A')}")
    print(f"DateTime: {result.get('datetime', 'N/A')}")
    
    # Smart list info
    if result.get('create_new_list'):
        print(f"\nSmart List: Will create new list")
    elif result.get('smart_list_id'):
        print(f"\nSmart List: {result.get('smart_list_name', 'N/A')}")
        print(f"List ID: {result.get('smart_list_id')}")
    
    print(f"\nStatus: {result.get('current_step', 'Unknown')}")
    
    if result.get('clarification_responses'):
        print(f"\nClarifications Provided:")
        for q, a in result['clarification_responses'].items():
            print(f"  Q: {q}")
            print(f"  A: {a}")


if __name__ == "__main__":
    main()
