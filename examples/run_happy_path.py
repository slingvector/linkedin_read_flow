"""
Happy Path Execution Script

Demonstrates structurally safe fetching where the internal crawler grabs
posts from your authorized feed, sanitizes hashtags, and silently drops 
data into the SQLite store.
"""
import logging
from read_flow import ReadFlow

# Track inner loops globally across services and storage limits
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def main():
    print("Initiating Happy Path: Scraping native authorized timeline...")
    
    try:
        flow = ReadFlow()
    except SystemExit as exc:
        print(f"Authentication Setup Failed: {exc}")
        return

    # Attempt to gracefully extract 5 posts dynamically
    result = flow.fetch_feed(max_posts=5)
    
    print("\n--- Pipeline Evaluation ---")
    print(f"Interaction Successful: {result['success']}")
    print(f"Extracted Nodes: {result['fetched']}")
    print(f"Database Persists: {result['saved']}")

if __name__ == "__main__":
    main()
