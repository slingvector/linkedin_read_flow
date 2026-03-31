"""
Unhappy Path Execution Script

Demonstrates structural safety. When the 3rd party underlying package throws
fatal GraphQL parsing errors (which happens frequently checking secure profiles), 
read_flow guarantees your application catches the crash gracefully.
"""
import logging
from read_flow import ReadFlow

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def main():
    print("Initiating Unhappy Path: Scraping locked public profile...")
    
    try:
        flow = ReadFlow()
    except SystemExit as exc:
        print(f"Authentication Setup Failed: {exc}")
        return

    # Attempting to fetch a massive VIP network typically triggers 'message' 
    # KeyErrors in linkedin_api parsing layouts on raw accounts
    result = flow.fetch_profile_posts(["williamhgates"], limit_per_profile=3)
    
    print("\n--- Pipeline Evaluation ---")
    print(f"Interaction Blocked Correctly: {not result['success']}")
    print(f"Captured System Errors: {result['errors']}")

if __name__ == "__main__":
    main()
