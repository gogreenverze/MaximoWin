#!/usr/bin/env python3
"""
Permission Request Script

This script asks for permission before making major changes to the codebase.
It provides yes/no/other options for the user to choose from.

Author: Augment Agent
Date: 2025-01-27
"""

import sys

def ask_permission(change_description, details=None, options=None):
    """
    Ask for permission to make changes.
    
    Args:
        change_description (str): Brief description of the change
        details (list): List of detailed changes
        options (list): Custom options (default: ['yes', 'no', 'modify'])
    
    Returns:
        str: User's choice
    """
    if options is None:
        options = ['yes', 'no', 'modify']
    
    print("🔧 PERMISSION REQUEST")
    print("=" * 50)
    print(f"📋 Change: {change_description}")
    
    if details:
        print("\n📝 Details:")
        for i, detail in enumerate(details, 1):
            print(f"   {i}. {detail}")
    
    print(f"\n❓ Options:")
    for i, option in enumerate(options, 1):
        print(f"   {i}. {option}")
    
    while True:
        try:
            print(f"\n🤔 Your choice (1-{len(options)} or option name): ", end="")
            user_input = input().strip().lower()
            
            # Check if it's a number
            if user_input.isdigit():
                choice_num = int(user_input)
                if 1 <= choice_num <= len(options):
                    return options[choice_num - 1]
                else:
                    print(f"❌ Please enter a number between 1 and {len(options)}")
                    continue
            
            # Check if it's an option name
            if user_input in [opt.lower() for opt in options]:
                return user_input
            
            print(f"❌ Invalid choice. Please enter one of: {', '.join(options)}")
            
        except KeyboardInterrupt:
            print("\n\n⏹️  Cancelled by user")
            return "no"
        except EOFError:
            print("\n\n⏹️  Input ended")
            return "no"

def main():
    """Main function for testing the permission system."""
    
    # Example usage
    change_description = "Fix inventory search to use correct OSLC endpoints"
    
    details = [
        "Revert to single OSLC endpoint: /oslc/os/mxapiinventory",
        "Follow exact same pattern as task_planned_materials_service.py", 
        "Use both MXAPIINVENTORY and MXAPIITEM for complete descriptions",
        "Add better error handling for 'no items found' responses",
        "Test with real item numbers from the system"
    ]
    
    options = ['yes', 'no', 'modify', 'test-first']
    
    choice = ask_permission(change_description, details, options)
    
    print(f"\n✅ User chose: {choice}")
    
    if choice == 'yes':
        print("🚀 Proceeding with changes...")
    elif choice == 'no':
        print("⏹️  Changes cancelled")
    elif choice == 'modify':
        print("✏️  Please specify modifications needed")
    elif choice == 'test-first':
        print("🧪 Running tests first...")
    
    return choice

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result == 'yes' else 1)
