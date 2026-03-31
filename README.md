# linkedin-read-flow

A standalone Python library for reading LinkedIn data — feed posts, profile posts, hashtag search, and post engagement. Designed to be installed as a dependency in the `linkedin-automation` main project.

Built to be **resilient to upstream breakage**: the unofficial `linkedin-api` library is fully isolated behind a single file. If it breaks or needs replacing, one file changes — nothing else.

---

## Table of Contents

- [What This Library Does](#what-this-library-does)
- [Why It Exists As a Separate Library](#why-it-exists-as-a-separate-library)
- [Architecture](#architecture)
  - [Folder Structure](#folder-structure)
  - [Layer Responsibilities](#layer-responsibilities)
  - [The Isolation Boundary](#the-isolation-boundary)
  - [The Storage Boundary](#the-storage-boundary)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [User Guide](#user-guide)
  - [Authentication](#authentication)
  - [Fetching Your Own Feed](#fetching-your-own-feed)
  - [Fetching Posts from Specific Profiles](#fetching-posts-from-specific-profiles)
  - [Searching by Keyword or Hashtag](#searching-by-keyword-or-hashtag)
  - [Fetching Post Engagement](#fetching-post-engagement)
  - [Plugging In Your Own Storage](#plugging-in-your-own-storage)
  - [Understanding Result Dicts](#understanding-result-dicts)
  - [Understanding the Post Dict Shape](#understanding-the-post-dict-shape)
- [Known Limitations](#known-limitations)
- [Upgrading the Underlying Client](#upgrading-the-underlying-client)
- [SOLID Principles Applied](#solid-principles-applied)
- [Relationship to linkedin-write-flow](#relationship-to-linkedin-write-flow)

---

## What This Library Does

`linkedin-read-flow` provides four read operations against LinkedIn:

| Operation | Method | Status |
|---|---|---|
| Fetch own feed posts | `flow.fetch_feed()` | ✅ Working |
| Fetch posts from specific profiles | `flow.fetch_profile_posts()` | ✅ Working |
| Search posts by keyword / hashtag | `flow.search()` | ⚠️ Limited (see below) |
| Fetch reactions and comments | `flow.fetch_engagement()` | ⚠️ Limited (see below) |

For each operation the library:
- Authenticates using your LinkedIn session cookie or email/password
- Fetches raw data from LinkedIn's internal Voyager API via `linkedin-api`
- Normalises the response into a stable dict shape your code can rely on
- Deduplicates against existing stored posts
- Persists new posts via a storage adapter (SQLite by default, swappable)
- Returns a structured result dict with counts and any errors

---

## Why It Exists As a Separate Library

The `linkedin-automation` project has two distinct concerns — reading data and writing data. Separating them into independent libraries means:

- **Independent versioning** — read-flow and write-flow can be updated, pinned, and rolled back independently without touching each other or the main project.
- **Clear ownership** — a bug in the read path doesn't risk destabilising the write path.
- **Testability** — the main project can mock either library entirely without running LinkedIn requests.
- **Replaceability** — if the unofficial `linkedin-api` library breaks (which it does, silently, when LinkedIn changes their internal API), only the read-flow library needs updating. The main project's code stays untouched.

---

## Architecture

### Folder Structure

```
linkedin_read_flow/
├── __init__.py                    # public exports: ReadFlow, SQLiteAdapter, StorageProtocol
├── auth.py                        # authentication: cookie → password fallback
├── reader.py                      # ← PUBLIC FACADE — only thing main project imports
│
├── clients/
│   ├── base.py                    # LinkedInReaderProtocol — the isolation boundary
│   └── voyager_client.py          # ← ONLY FILE that imports linkedin-api
│
├── services/
│   ├── feed_service.py            # own feed fetch + store logic
│   ├── profile_service.py         # specific profile fetch + store logic
│   ├── search_service.py          # keyword/hashtag search + store logic
│   └── engagement_service.py     # reactions + comments fetch logic
│
└── storage/
    ├── base.py                    # StorageProtocol — the storage boundary
    └── sqlite_adapter.py          # default SQLite implementation
```

### Layer Responsibilities

```
┌─────────────────────────────────────────────────────────────┐
│  Main Project                                               │
│  from linkedin_read_flow import ReadFlow                    │
└────────────────────────┬────────────────────────────────────┘
                         │ calls
┌────────────────────────▼────────────────────────────────────┐
│  reader.py  (Facade / Controller)                           │
│  ReadFlow — single public entry point                       │
│  Wires auth, services, storage together                     │
└──────┬──────────────────────────────────────┬───────────────┘
       │ delegates to                          │ stores via
┌──────▼──────────────┐              ┌────────▼───────────────┐
│  services/          │              │  storage/              │
│  FeedService        │              │  StorageProtocol       │
│  ProfileService     │              │  (SQLiteAdapter or     │
│  SearchService      │              │   your own adapter)    │
│  EngagementService  │              └────────────────────────┘
└──────┬──────────────┘
       │ calls via
┌──────▼──────────────────────────────────────────────────────┐
│  clients/base.py  (LinkedInReaderProtocol)                  │
│  Protocol interface — services never know what's behind it  │
└──────┬──────────────────────────────────────────────────────┘
       │ implemented by
┌──────▼──────────────────────────────────────────────────────┐
│  clients/voyager_client.py  (VoyagerClient)                 │
│  ← THE ONLY FILE THAT IMPORTS linkedin-api                  │
│  Wraps Linkedin() calls, normalises responses to plain dicts│
└──────┬──────────────────────────────────────────────────────┘
       │ uses
┌──────▼──────────────────────────────────────────────────────┐
│  linkedin-api 2.2.0  (third-party, unofficial)              │
│  Hits LinkedIn's internal Voyager API                       │
└─────────────────────────────────────────────────────────────┘
```

### The Isolation Boundary

`clients/base.py` defines `LinkedInReaderProtocol` — a Python `Protocol` (structural typing, no inheritance needed). Every service class depends on this protocol, not on `VoyagerClient` directly.

```python
# What services see — an abstract contract
class LinkedInReaderProtocol(Protocol):
    def get_feed_posts(self, limit: int) -> list[dict]: ...
    def get_profile_posts(self, public_id: str, limit: int) -> list[dict]: ...
    def search_posts(self, keywords: str, limit: int) -> list[dict]: ...
    def get_post_reactions(self, post_urn: str, limit: int) -> list[dict]: ...
    def get_post_comments(self, post_urn: str, limit: int) -> list[dict]: ...
```

`VoyagerClient` implements this protocol by wrapping `linkedin-api`. A runtime `assert isinstance()` at the bottom of `voyager_client.py` guarantees the implementation never silently drifts from the protocol.

**Result:** if `linkedin-api` breaks, you write a new client class, swap one line in `auth.py`, and nothing else in the codebase changes.

### The Storage Boundary

`storage/base.py` defines `StorageProtocol`:

```python
class StorageProtocol(Protocol):
    def save_post(self, post: dict) -> bool: ...
    def post_exists(self, url: str) -> bool: ...
    def get_all_urls(self) -> set[str]: ...
```

Services write through this interface. The main project can pass any conforming object:

```python
# default — SQLite
flow = ReadFlow()

# custom — Postgres, MongoDB, SQLAlchemy, anything
flow = ReadFlow(storage=MyPostgresAdapter())
```

---

## Installation

```bash
# from the linkedin-read-flow repo root
pip install -e .

# or once published to a private registry
pip install linkedin-read-flow
```

Dependencies:

```
linkedin-api==2.2.0
python-dotenv
```

> Pin `linkedin-api` to `2.2.0` in your `requirements.txt` or `pyproject.toml`. Do not leave it unpinned — the library has no stable release guarantees.

---

## Quick Start

```python
from linkedin_read_flow import ReadFlow

flow = ReadFlow()  # uses .env credentials, SQLite storage by default

# fetch own feed
result = flow.fetch_feed()
print(result)
# {
#   "success": True,
#   "fetched": 45,
#   "saved": 38,
#   "skipped_duplicate": 7,
#   "skipped_filter": 0,
#   "error": None
# }

# fetch posts from specific creators
result = flow.fetch_profile_posts(["john-doe", "jane-smith"])

# search by hashtag
result = flow.search("#ai")

# fetch engagement for stored post URNs
result = flow.fetch_engagement(["urn:li:activity:7442906962423640066"])
```

---

## Configuration

Create a `.env` file in your project root:

```env
# Option 1 — recommended (cookie auth, password never used)
LINKEDIN_LI_AT=AQEDATd2...

# Option 2 — fallback if no cookie
LINKEDIN_EMAIL=you@example.com
LINKEDIN_PASSWORD=yourpassword
```

Add to `.gitignore` immediately:

```
.env
linkedin_read_flow.db
```

**How to get your `li_at` cookie:**
1. Open Chrome and log into LinkedIn
2. Open DevTools (`F12`) → Application tab → Cookies → `https://www.linkedin.com`
3. Find the cookie named `li_at` → copy its Value

The cookie expires periodically. When it does, log in again in the browser and copy the fresh value.

---

## User Guide

### Authentication

Auth is handled automatically when you instantiate `ReadFlow()`. It follows this priority order:

1. **`LINKEDIN_LI_AT` cookie** — if present in `.env`, used directly. Your password is never touched.
2. **`LINKEDIN_EMAIL` + `LINKEDIN_PASSWORD`** — fallback if no cookie is set.

If neither is present, the library raises `SystemExit` with a clear message telling you exactly what to add to `.env`.

If your account triggers a 2FA or CAPTCHA challenge on password auth, the library catches it and tells you to log in manually in a browser, solve the challenge, then grab the `li_at` cookie and use that instead.

---

### Fetching Your Own Feed

```python
# fetch all posts (up to 500 per run)
result = flow.fetch_feed()

# fetch with a hard cap
result = flow.fetch_feed(max_posts=100)

# fetch only posts containing specific hashtags
result = flow.fetch_feed(hashtag_filter=["#ai", "#python", "#llm"])
```

**How it works internally:**
- Calls `linkedin-api`'s `get_feed_posts()` in batches of 100
- Each batch is normalised into a stable dict shape
- Posts already in storage are skipped (deduplication by URL)
- Posts not matching `hashtag_filter` are skipped
- New posts are saved via the storage adapter
- A 2–3.5 second delay is applied between batches

**Result dict:**

```python
{
    "success":           True,
    "fetched":           45,       # total posts returned by LinkedIn
    "saved":             38,       # newly inserted into storage
    "skipped_duplicate": 7,        # already existed in storage
    "skipped_filter":    0,        # filtered out by hashtag_filter
    "error":             None      # error message string if success=False
}
```

> **Note:** `linkedin-api 2.2.0` does not support true feed pagination. It re-fetches the same feed window on each call. This means a single run typically yields ~45 unique posts. Run the library once or twice per day to accumulate posts over time as new content appears in your feed.

---

### Fetching Posts from Specific Profiles

```python
result = flow.fetch_profile_posts(
    profile_ids=["john-doe", "824004659", "jane-smith"],
    limit_per_profile=50,
)
```

`profile_ids` accepts either:
- Vanity slugs: the part after `/in/` in a LinkedIn URL (e.g. `john-doe` from `linkedin.com/in/john-doe`)
- Numeric IDs: the raw number LinkedIn uses internally (e.g. `824004659`)

A 3-second delay is applied between each profile fetch to avoid rate limiting.

**Result dict:**

```python
{
    "success":            True,
    "profiles_attempted": 3,
    "profiles_failed":    0,        # profiles where fetch raised an error
    "fetched":            127,      # total posts across all profiles
    "saved":              95,       # newly inserted
    "skipped_duplicate":  32,
    "errors":             []        # list of "profile_id: error message" strings
}
```

If one profile fails (private profile, account deleted, etc.), the error is recorded in `errors` and the library continues with the remaining profiles. `success` is `False` only if every profile fails.

---

### Searching by Keyword or Hashtag

```python
result = flow.search("#machinelearning", limit=50)
result = flow.search("generative ai", limit=30)
```

**⚠️ Current limitation:** `linkedin-api 2.2.0` has no working post search endpoint. The `search()` method falls back to fetching your own feed and filtering by keyword match in the post content. This means:
- Results are limited to posts that already appeared in your feed
- True hashtag discovery (posts from people you don't follow) is not available
- The result dict always includes a `note` field explaining this

**Result dict:**

```python
{
    "success":           True,
    "fetched":           12,
    "saved":             9,
    "skipped_duplicate": 3,
    "error":             None,
    "note":              "linkedin-api 2.2.0 does not support native post search. ..."
}
```

When a better client is available, swap `VoyagerClient` and this method will work correctly without any other changes.

---

### Fetching Post Engagement

```python
result = flow.fetch_engagement(
    post_urns=["urn:li:activity:7442906962423640066"],
    limit_per_post=50,
)
```

Post URNs are stored in the database when posts are saved. You can query them:

```bash
sqlite3 linkedin_read_flow.db "SELECT post_urn FROM posts WHERE post_urn IS NOT NULL LIMIT 10"
```

**⚠️ Current limitation:** `linkedin-api 2.2.0` returns HTTP 500 for both `get_post_reactions()` and `get_post_comments()`. The library handles this gracefully — it returns empty lists and logs a warning rather than raising. Your code will not crash.

**Result dict:**

```python
{
    "success": True,
    "engagement": {
        "urn:li:activity:7442906962423640066": {
            "reactions": [],   # empty until client is upgraded
            "comments":  [],   # empty until client is upgraded
        }
    },
    "error": None,
    "note":  "linkedin-api 2.2.0 returns HTTP 500 for reactions and comments endpoints. ..."
}
```

---

### Plugging In Your Own Storage

The main project can replace SQLite with any storage backend by implementing `StorageProtocol` and passing it to `ReadFlow`:

```python
from linkedin_read_flow import ReadFlow, StorageProtocol
from typing import Any

class MyPostgresAdapter:
    """Example: plug in SQLAlchemy + Postgres."""

    def __init__(self, session):
        self._session = session

    def save_post(self, post: dict[str, Any]) -> bool:
        # insert into your ORM model, return True if new
        ...

    def post_exists(self, url: str) -> bool:
        # query your DB
        ...

    def get_all_urls(self) -> set[str]:
        # return all stored URLs as a set
        ...

# pass to ReadFlow
flow = ReadFlow(storage=MyPostgresAdapter(session=db_session))
```

The library never imports your adapter — it only calls the three methods defined in `StorageProtocol`. As long as your class implements those three methods with the correct signatures, it works.

---

### Understanding Result Dicts

Every public method on `ReadFlow` returns a plain `dict`. There are no custom exception types at the public boundary — errors are captured and returned in the `error` field.

**Common fields across all result dicts:**

| Field | Type | Meaning |
|---|---|---|
| `success` | `bool` | `True` if the operation completed without fatal error |
| `error` | `str \| None` | Error message if `success=False`, otherwise `None` |
| `fetched` | `int` | Total posts returned by LinkedIn |
| `saved` | `int` | Posts newly inserted into storage |
| `skipped_duplicate` | `int` | Posts already in storage, skipped |
| `note` | `str \| None` | Present when a known library limitation affected the result |

**Checking results in your code:**

```python
result = flow.fetch_feed()

if not result["success"]:
    logger.error("Feed fetch failed: %s", result["error"])
else:
    logger.info("Saved %d new posts", result["saved"])
    if result.get("note"):
        logger.warning("Library note: %s", result["note"])
```

---

### Understanding the Post Dict Shape

Every post saved to storage and returned internally has this stable shape:

```python
{
    "url":            "https://www.linkedin.com/feed/update/urn:li:activity:123/",
    "post_urn":       "urn:li:activity:123",          # None if not extractable
    "author_name":    "Jane Smith",
    "author_profile": "https://www.linkedin.com/in/jane-smith",
    "content":        "Full post text including #hashtags",
    "hashtags":       ["#ai", "#python"],              # extracted from content
    "source":         "feed",                          # "feed" | "profile" | "search"
}
```

This shape is **stable regardless of what linkedin-api returns**. If `linkedin-api` changes its response keys, only `voyager_client.py`'s normaliser methods change — the shape your code depends on stays the same.

---

## Known Limitations

These are limitations of `linkedin-api 2.2.0`, not of this library's design. They are documented explicitly rather than silently ignored.

| Feature | Status | Detail |
|---|---|---|
| Feed posts | ✅ Working | ~45 unique posts per run, no true pagination |
| Profile posts | ✅ Working | Tested and confirmed |
| Post search | ⚠️ Fallback only | Falls back to feed keyword filter — no cross-network search |
| Reactions | ⚠️ Returns `[]` | Voyager endpoint returns HTTP 500 in 2.2.0 |
| Comments | ⚠️ Returns `[]` | Same as reactions |

All limited features return gracefully — empty lists and a `note` field — rather than raising exceptions. Your code will not crash due to these limitations.

---

## Upgrading the Underlying Client

When `linkedin-api` is fixed, a new version is available, or you want to replace it with direct Voyager HTTP calls:

**Step 1:** Create a new client file implementing `LinkedInReaderProtocol`:

```python
# clients/voyager_http_client.py
from .base import LinkedInReaderProtocol

class VoyagerHTTPClient:
    """Direct HTTP implementation — no third-party library."""

    def get_feed_posts(self, limit: int) -> list[dict]: ...
    def get_profile_posts(self, public_id: str, limit: int) -> list[dict]: ...
    def search_posts(self, keywords: str, limit: int) -> list[dict]: ...
    def get_post_reactions(self, post_urn: str, limit: int) -> list[dict]: ...
    def get_post_comments(self, post_urn: str, limit: int) -> list[dict]: ...
```

**Step 2:** Update `auth.py` to return the new client:

```python
# auth.py — change one line
from .clients.voyager_http_client import VoyagerHTTPClient

def build_voyager_client() -> VoyagerHTTPClient:
    ...
    return VoyagerHTTPClient(...)
```

**Step 3:** Done. Zero changes to services, `ReadFlow`, storage, or the main project.

---

## SOLID Principles Applied

| Principle | Where applied |
|---|---|
| **S** — Single Responsibility | Each service handles exactly one domain (feed, profile, search, engagement). `VoyagerClient` only translates API calls. `SQLiteAdapter` only handles persistence. |
| **O** — Open/Closed | New read operations = new service class. Existing services never modified. New storage backends = new adapter class. |
| **L** — Liskov Substitution | Any class implementing `LinkedInReaderProtocol` or `StorageProtocol` is a valid drop-in. No special base class needed. |
| **I** — Interface Segregation | `StorageProtocol` has exactly three methods — only what services actually need. Services are not forced to depend on methods they don't use. |
| **D** — Dependency Inversion | Services depend on `LinkedInReaderProtocol` (abstraction), not `VoyagerClient` (concretion). `ReadFlow` depends on `StorageProtocol`, not `SQLiteAdapter`. |

---

## Relationship to linkedin-write-flow

This library and `linkedin-write-flow` are designed as a pair:

```
linkedin-automation (main project)
├── linkedin-read-flow   (this library)  — reads data into storage
└── linkedin-write-flow                  — publishes posts via OAuth
```

They are independent — read-flow uses `linkedin-api` (unofficial, cookie auth), write-flow uses LinkedIn's official OAuth API. They can be versioned, updated, and tested separately. The main project imports both and orchestrates them without needing to know anything about `linkedin-api` or Voyager internals.
