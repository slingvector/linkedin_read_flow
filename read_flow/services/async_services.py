"""
read_flow/async_services.py
-------------------------------------
Async Service Layer: Contains asyncio-compatible versions of the read operations.
Replaces time.sleep() with asyncio.sleep() to prevent blocking the event loop.
"""

import asyncio
import logging
import random
import uuid
from typing import Any

from ..clients.base import LinkedInReaderProtocol
from ..clients.voyager_client import LinkedInClientError
from ..storage.base import StorageProtocol

logger = logging.getLogger(__name__)

_MAX_POSTS_PER_RUN = 500
_BATCH_SIZE = 100
_BASE_DELAY_S = 2.0
_JITTER_S = 1.5
_INTER_PROFILE_DELAY_S = 3.0
_INTER_POST_DELAY_S = 2.0


class AsyncFeedService:
    def __init__(self, client: LinkedInReaderProtocol, storage: StorageProtocol):
        self._client = client
        self._storage = storage

    async def fetch_and_store(
        self,
        max_posts: int = _MAX_POSTS_PER_RUN,
        hashtag_filter: list[str] | None = None,
    ) -> dict[str, Any]:
        correlation_id = str(uuid.uuid4())
        logger.info(
            "AsyncFeedService.fetch_and_store started",
            extra={"correlation_id": correlation_id},
        )

        existing_urls: set[str] = set()
        normalised_tags = self._normalise_tags(hashtag_filter or [])
        fetched_total, saved, skipped_duplicate, skipped_filter = 0, 0, 0, 0

        try:
            while fetched_total < max_posts:
                batch_size = min(_BATCH_SIZE, max_posts - fetched_total)
                # Note: The raw client request remains synchronous.
                # This is intentional to reuse VoyagerClient while avoiding thread-locking on sleep overhead.
                posts = self._client.get_feed_posts(limit=batch_size)

                if not posts:
                    break

                for post in posts:
                    url = post.get("url", "")
                    if not url:
                        continue
                    if url in existing_urls:
                        skipped_duplicate += 1
                        continue
                    if normalised_tags and not self._passes_filter(
                        post, normalised_tags
                    ):
                        skipped_filter += 1
                        continue
                    if self._storage.save_post(post):
                        existing_urls.add(url)
                        saved += 1

                fetched_total += len(posts)

                if len(posts) < batch_size:
                    break

                delay = _BASE_DELAY_S + random.uniform(0, _JITTER_S)
                await asyncio.sleep(delay)

        except LinkedInClientError as exc:
            return self._result(
                False, fetched_total, saved, skipped_duplicate, skipped_filter, str(exc)
            )

        return self._result(
            True, fetched_total, saved, skipped_duplicate, skipped_filter
        )

    @staticmethod
    def _normalise_tags(tags: list[str]) -> set[str]:
        return {t.lower().lstrip("#") for t in tags}

    @staticmethod
    def _passes_filter(post: dict, normalised_tags: set[str]) -> bool:
        post_tags = {t.lstrip("#") for t in (post.get("hashtags") or [])}
        return bool(normalised_tags & post_tags)

    @staticmethod
    def _result(success, fetched, saved, skipped_duplicate, skipped_filter, error=None):
        return {
            "success": success,
            "fetched": fetched,
            "saved": saved,
            "skipped_duplicate": skipped_duplicate,
            "skipped_filter": skipped_filter,
            "error": error,
        }


class AsyncProfileService:
    def __init__(self, client: LinkedInReaderProtocol, storage: StorageProtocol):
        self._client = client
        self._storage = storage

    async def fetch_and_store(
        self, profile_ids: list[str], limit_per_profile: int = 50
    ) -> dict[str, Any]:
        existing_urls: set[str] = set()
        profiles_attempted, profiles_failed = 0, 0
        fetched_total, saved, skipped_duplicate = 0, 0, 0
        errors: list[str] = []

        for profile_id in profile_ids:
            profiles_attempted += 1
            try:
                posts = self._client.get_profile_posts(
                    public_id=profile_id, limit=limit_per_profile
                )
            except LinkedInClientError as exc:
                profiles_failed += 1
                errors.append(f"{profile_id}: {exc}")
                continue

            for post in posts:
                url = post.get("url", "")
                if not url or url in existing_urls:
                    skipped_duplicate += 1
                    continue
                if self._storage.save_post(post):
                    existing_urls.add(url)
                    saved += 1

            fetched_total += len(posts)

            if profiles_attempted < len(profile_ids):
                await asyncio.sleep(_INTER_PROFILE_DELAY_S)

        success = profiles_failed < profiles_attempted
        return {
            "success": success,
            "profiles_attempted": profiles_attempted,
            "profiles_failed": profiles_failed,
            "fetched": fetched_total,
            "saved": saved,
            "skipped_duplicate": skipped_duplicate,
            "errors": errors,
        }


class AsyncSearchService:
    def __init__(self, client: LinkedInReaderProtocol, storage: StorageProtocol):
        self._client = client
        self._storage = storage

    async def fetch_and_store(self, keywords: str, limit: int = 50) -> dict[str, Any]:
        existing_urls: set[str] = set()

        try:
            posts = self._client.search_posts(keywords=keywords, limit=limit)
        except LinkedInClientError as exc:
            return {
                "success": False,
                "fetched": 0,
                "saved": 0,
                "skipped_duplicate": 0,
                "error": str(exc),
                "note": None,
            }

        saved, skipped_duplicate = 0, 0
        for post in posts:
            url = post.get("url", "")
            if not url or url in existing_urls:
                skipped_duplicate += 1
                continue
            if self._storage.save_post(post):
                existing_urls.add(url)
                saved += 1

        note = "linkedin-api 2.2.0 does not support native post search. Results are filtered from the own feed. Upgrade VoyagerClient for true hashtag search."
        return {
            "success": True,
            "fetched": len(posts),
            "saved": saved,
            "skipped_duplicate": skipped_duplicate,
            "error": None,
            "note": note,
        }


class AsyncEngagementService:
    def __init__(self, client: LinkedInReaderProtocol):
        self._client = client

    async def fetch_engagement(
        self, post_urns: list[str], limit_per_post: int = 50
    ) -> dict[str, Any]:
        engagement: dict[str, dict] = {}
        errors: list[str] = []

        for i, urn in enumerate(post_urns):
            try:
                reactions = self._client.get_post_reactions(urn, limit=limit_per_post)
                comments = self._client.get_post_comments(urn, limit=limit_per_post)
                engagement[urn] = {"reactions": reactions, "comments": comments}
            except LinkedInClientError as exc:
                errors.append(f"{urn}: {exc}")
                engagement[urn] = {"reactions": [], "comments": [], "error": str(exc)}

            if i < len(post_urns) - 1:
                await asyncio.sleep(_INTER_POST_DELAY_S)

        note = (
            "linkedin-api 2.2.0 returns HTTP 500 for reactions and comments endpoints. All engagement lists are empty. Upgrade VoyagerClient to fix."
            if all(
                len(v.get("reactions", [])) == 0 and len(v.get("comments", [])) == 0
                for v in engagement.values()
            )
            else None
        )
        return {
            "success": len(errors) < len(post_urns),
            "engagement": engagement,
            "error": "; ".join(errors) if errors else None,
            "note": note,
        }
