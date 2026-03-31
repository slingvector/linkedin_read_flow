"""
read_flow/async_reader.py
-----------------------------------
Public async facade for integrating with non-blocking architectures (e.g. FastAPI).
Provides AsyncReadFlow leveraging asyncio.sleep() rather than time.sleep().
"""

import logging
from typing import Any

from .auth import build_voyager_client
from .services.async_services import (
    AsyncEngagementService,
    AsyncFeedService,
    AsyncProfileService,
    AsyncSearchService,
)
from .storage.base import StorageProtocol
from .storage.sqlite_adapter import SQLiteAdapter

logger = logging.getLogger(__name__)


class AsyncReadFlow:
    """
    Async single entry point for all LinkedIn read operations.
    Functions exactly like ReadFlow but methods must be awaited.
    """

    def __init__(self, storage: StorageProtocol | None = None):
        logger.info("AsyncReadFlow initialising", extra={"layer": "facade"})

        self._client = build_voyager_client()
        self._storage = storage or SQLiteAdapter()

        self._feed_service = AsyncFeedService(self._client, self._storage)
        self._profile_service = AsyncProfileService(self._client, self._storage)
        self._search_service = AsyncSearchService(self._client, self._storage)
        self._engagement_service = AsyncEngagementService(self._client)

        logger.info("AsyncReadFlow ready", extra={"layer": "facade"})

    async def fetch_feed(
        self, max_posts: int = 500, hashtag_filter: list[str] | None = None
    ) -> dict[str, Any]:
        return await self._feed_service.fetch_and_store(
            max_posts=max_posts, hashtag_filter=hashtag_filter
        )

    async def fetch_profile_posts(
        self, profile_ids: list[str], limit_per_profile: int = 50
    ) -> dict[str, Any]:
        return await self._profile_service.fetch_and_store(
            profile_ids=profile_ids, limit_per_profile=limit_per_profile
        )

    async def search(self, keywords: str, limit: int = 50) -> dict[str, Any]:
        return await self._search_service.fetch_and_store(
            keywords=keywords, limit=limit
        )

    async def fetch_engagement(
        self, post_urns: list[str], limit_per_post: int = 50
    ) -> dict[str, Any]:
        return await self._engagement_service.fetch_engagement(
            post_urns=post_urns, limit_per_post=limit_per_post
        )
