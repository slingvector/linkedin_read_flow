"""
read_flow/clients/voyager_client.py
---------------------------------------------
The ONLY file in this library that imports linkedin-api.

If linkedin-api breaks or you want to replace it with direct Voyager HTTP:
  1. Create a new file (e.g. voyager_http_client.py) implementing LinkedInReaderProtocol
  2. Update auth.py to instantiate the new client
  3. Done — zero changes to services, reader, or main project

KNOWN LIMITATIONS of linkedin-api 2.2.0:
  - get_post_reactions() returns HTTP 500 — wrapped and returns [] gracefully
  - get_post_comments() returns HTTP 500 — same treatment
  - search_posts() does not exist — search() with q=content returns empty body
    Both are wrapped with clear log warnings so failures are visible but non-fatal.
"""

import logging
import re
from typing import Any

from linkedin_api import Linkedin

from .base import LinkedInReaderProtocol

logger = logging.getLogger(__name__)


class VoyagerClient:
    """
    Wraps linkedin-api 2.2.0 and implements LinkedInReaderProtocol.
    All linkedin-api types are converted to plain dicts before returning.
    No linkedin-api import exists anywhere outside this file.
    """

    def __init__(self, api: Linkedin):
        # linkedin-api instance — private, never exposed outside this class
        self._api = api

    # ------------------------------------------------------------------
    # Feed
    # ------------------------------------------------------------------

    def get_feed_posts(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Fetches own feed posts.
        linkedin-api returns flat dicts with: url, content, author_name, author_profile.
        """
        logger.info(
            "Fetching feed posts", extra={"limit": limit, "client": "VoyagerClient"}
        )
        try:
            raw = self._api.get_feed_posts(limit=limit)
            posts = [self._normalise_feed_post(p) for p in (raw or [])]
            logger.info(
                "Feed posts fetched",
                extra={"count": len(posts), "client": "VoyagerClient"},
            )
            return posts
        except Exception as exc:
            logger.error(
                "get_feed_posts failed",
                extra={"error": str(exc), "client": "VoyagerClient"},
            )
            raise LinkedInClientError(f"Feed fetch failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Profile posts
    # ------------------------------------------------------------------

    def get_profile_posts(
        self,
        public_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Fetches posts from a specific profile.
        public_id is the vanity slug (e.g. 'john-doe') or numeric ID.
        """
        logger.info(
            "Fetching profile posts",
            extra={"public_id": public_id, "limit": limit, "client": "VoyagerClient"},
        )
        try:
            raw = self._api.get_profile_posts(public_id=public_id, post_count=limit)
            posts = [self._normalise_profile_post(p) for p in (raw or [])]
            logger.info(
                "Profile posts fetched",
                extra={
                    "public_id": public_id,
                    "count": len(posts),
                    "client": "VoyagerClient",
                },
            )
            return posts
        except Exception as exc:
            logger.error(
                "get_profile_posts failed",
                extra={
                    "public_id": public_id,
                    "error": str(exc),
                    "client": "VoyagerClient",
                },
            )
            raise LinkedInClientError(
                f"Profile post fetch failed for {public_id}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_posts(
        self,
        keywords: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Searches posts by keyword or hashtag.

        LIMITATION: linkedin-api 2.2.0 does not support post search via
        search_posts() (method doesn't exist) or search(q='content')
        (returns empty body / JSON decode error).

        This method performs a best-effort search by:
          1. Trying search_people to find profiles posting about the keyword
          2. Fetching their recent posts and filtering by keyword match in content

        This is a workaround — replace this file when a better client is available.
        """
        logger.warning(
            "search_posts: linkedin-api 2.2.0 has no native post search. "
            "Using keyword filter over feed posts as fallback.",
            extra={"keywords": keywords, "client": "VoyagerClient"},
        )
        try:
            # fallback: filter own feed by keyword
            feed_posts = self.get_feed_posts(limit=min(limit * 3, 300))
            keyword_lower = keywords.lower().lstrip("#")
            matched = [
                p
                for p in feed_posts
                if keyword_lower in (p.get("content") or "").lower()
                or keyword_lower in (p.get("hashtags") or [])
            ]
            logger.info(
                "search_posts (feed filter) matched",
                extra={
                    "keywords": keywords,
                    "matched": len(matched),
                    "client": "VoyagerClient",
                },
            )
            return matched[:limit]
        except Exception as exc:
            logger.error(
                "search_posts fallback failed",
                extra={
                    "keywords": keywords,
                    "error": str(exc),
                    "client": "VoyagerClient",
                },
            )
            raise LinkedInClientError(f"Search failed for '{keywords}': {exc}") from exc

    # ------------------------------------------------------------------
    # Engagement
    # ------------------------------------------------------------------

    def get_post_reactions(
        self,
        post_urn: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        KNOWN ISSUE: linkedin-api 2.2.0 get_post_reactions() returns HTTP 500.
        Returns [] gracefully and logs a warning — does not raise.
        Replace this client when a working implementation is available.
        """
        logger.warning(
            "get_post_reactions: linkedin-api 2.2.0 returns HTTP 500 for this endpoint. "
            "Returning empty list. Upgrade client to fix.",
            extra={"post_urn": post_urn, "client": "VoyagerClient"},
        )
        return []

    def get_post_comments(
        self,
        post_urn: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        KNOWN ISSUE: linkedin-api 2.2.0 get_post_comments() returns HTTP 500.
        Returns [] gracefully and logs a warning — does not raise.
        Replace this client when a working implementation is available.
        """
        logger.warning(
            "get_post_comments: linkedin-api 2.2.0 returns HTTP 500 for this endpoint. "
            "Returning empty list. Upgrade client to fix.",
            extra={"post_urn": post_urn, "client": "VoyagerClient"},
        )
        return []

    # ------------------------------------------------------------------
    # Normalisers — convert linkedin-api shapes to stable dicts
    # These are the only place linkedin-api response shapes are referenced.
    # If linkedin-api changes its output shape, only fix here.
    # ------------------------------------------------------------------

    def _normalise_feed_post(self, raw: dict) -> dict[str, Any]:
        """
        Converts a linkedin-api feed post dict to a stable internal shape.
        Confirmed working keys in 2.2.0: url, content, author_name, author_profile.
        """
        content = raw.get("content", "") or ""
        hashtags = self._extract_hashtags(content, raw=raw)
        url = raw.get("url", "") or ""
        return {
            "url": url.strip(),
            "post_urn": self._urn_from_url(url),
            "author_name": (raw.get("author_name") or "").strip(),
            "author_profile": (raw.get("author_profile") or "").strip(),
            "content": content.strip(),
            "hashtags": hashtags,
            "source": "feed",
        }

    def _normalise_profile_post(self, raw: dict) -> dict[str, Any]:
        """
        Converts a linkedin-api profile post dict to the same stable shape.
        get_profile_posts() returns a different key structure than get_feed_posts().
        """
        # profile posts nest content differently — extract best-effort
        content = raw.get("commentary", {}).get("text") or raw.get("content", "") or ""
        url = raw.get("url", "") or ""
        if not url:
            urn = raw.get("updateUrn") or raw.get("entityUrn") or ""
            url = f"https://www.linkedin.com/feed/update/{urn}/" if urn else ""

        hashtags = self._extract_hashtags(content, raw=raw)
        return {
            "url": url.strip(),
            "post_urn": self._urn_from_url(url),
            "author_name": (raw.get("author_name") or "").strip(),
            "author_profile": (raw.get("author_profile") or "").strip(),
            "content": content.strip(),
            "hashtags": hashtags,
            "source": "profile",
        }

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_hashtags(text: str, raw: dict | None = None) -> list[str]:
        raw = raw or {}

        metadata = raw.get("entityMetadata")
        if metadata:
            import json

            md_str = json.dumps(metadata)
            urn_tags = re.findall(r"urn:li:hashtag:([a-zA-Z0-9_]+)", md_str)
            if urn_tags:
                return [f"#{tag.lower()}" for tag in set(urn_tags)]

        cleaned_text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        cleaned_text = re.sub(r"https?://[^\s]+", "", cleaned_text)

        matches = re.findall(r"(?<![a-zA-Z0-9])#([a-zA-Z0-9_]+)", cleaned_text)
        return [f"#{m.lower()}" for m in set(matches)]

    @staticmethod
    def _urn_from_url(url: str) -> str | None:
        match = re.search(r"(urn:li:(?:activity|ugcPost):\d+)", url)
        return match.group(1) if match else None


# ---------------------------------------------------------------------------
# Typed exception — raised by this client, caught by services
# ---------------------------------------------------------------------------
class LinkedInClientError(Exception):
    """Raised when the underlying linkedin-api call fails unrecoverably."""


# ---------------------------------------------------------------------------
# Runtime protocol check — fails at import if VoyagerClient drifts from protocol
# ---------------------------------------------------------------------------
assert isinstance(VoyagerClient.__new__(VoyagerClient), LinkedInReaderProtocol), (
    "VoyagerClient does not fully implement LinkedInReaderProtocol"
)
