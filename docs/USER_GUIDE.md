# 📘 `linkedin-read-flow` User Guide

`linkedin-read-flow` is a standalone Python data extraction pipeline designed to continuously scrape activity from LinkedIn networks. By leveraging an internal SQLite deduplication engine and asynchronous parallel processing, this application guarantees datasets are parsed safely and resiliently.

---

## 🚀 Quickstart Installation

```bash
# Clone the repository and establish a local environment
python3 -m venv venv
source venv/bin/activate

# Install strictly resolving native dependencies
pip install -e .
```

## 🔐 Authentication

Your application **must** be supplied with a dummy account or a dedicated LinkedIn account to operate. Create an `.env` file at the root of the project:

```properties
# 1. Primary Authentication (Highly Recommended)
LINKEDIN_LI_AT=AQEDATd2...

# 2. Fallback Authentication
LINKEDIN_EMAIL=dummy_account@email.com
LINKEDIN_PASSWORD=dummy_secret
```

## ⚙️ Usage & Implementation

Access the scraping facade using either the synchronous engine (`ReadFlow`) or asynchronous engine (`AsyncReadFlow`). Both frameworks spin up bounded `SQLite` integrations natively to enforce local deduplication.

To view complete deployment patterns immediately, we provide two functional executables in the `examples/` directory:
- `python examples/run_happy_path.py` (Tests successful feed parsing architectures natively).
- `python examples/run_unhappy_path.py` (Tests API crash/exception trapping mechanics gracefully).

```python
import logging
from read_flow import ReadFlow

logging.basicConfig(level=logging.INFO)

# Instantiates scraper; exits program safely if .env is missing/unauthorized
flow = ReadFlow()

# 1. Scrape Your Own Feed Iteratively
feed_results = flow.fetch_feed(max_posts=20)
print(feed_results)

# 2. Extract Specific Profile Timelines 
profile_results = flow.fetch_profile_posts(["1382974558", "williamhgates"], limit_per_profile=5)
print(profile_results)

# 3. Filter specific hashtags natively from your active timeline
search_results = flow.search(keyword="#AI", limit=10)
```

The database pipeline will seamlessly update stale rows or capture missing entries via native SQLite `UPSERT` overrides across local executions in `./linkedin_read_flow.db`.

---

## 🧪 Testing and Verification

The system validates strictly against Python's native `unittest` framework without requiring any third-party framework (like `pytest`). 

Trigger the entire 14-test suite automatically via the executable script globally:
```bash
./run_tests.sh
```

## 📊 Live Testing Benchmark Status 

- ✅ **Scraping Custom Feeds (`fetch_feed`)**: Flawlessly retrieves batches, extracts JSON payloads, strips code blocks/URLs, filters isolated hashtags recursively, and writes into SQLite.
- ✅ **SQLite Deduplication Engine**: Guaranteed isolation mechanics effectively testing `UPSERT` overrides enforcing strict update refreshes seamlessly. 
- ⚠️ **Target Profile Extraction (`fetch_profile_posts`)**: Degraded on generic proxy accounts. Safely intercepts downstream LinkedIn GraphQL schema collapses (`KeyError: 'message'`) returning `{success: False}` mappings cleanly without crashing environments.
- ⚠️ **Native Searching (`search`)**: Degraded actively upstream. The wrapper architecture natively cannot execute generic structural hashtag searches. The engine proxies hashtag definitions logically performing complex local Regex filters natively across internal feeds instead.
- ⚠️ **Engagement Analytics (`fetch_engagement`)**: Degraded upstream. Actively wraps downstream `HTTP 500` server timeouts executing explicitly evaluated empty payload dictionaries directly.
