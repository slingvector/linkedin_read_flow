"""
read_flow/reader.py
-----------------------------
Public facade — the ONLY class the main project imports from this library.

The main project never touches:
  - linkedin_api (unofficial library)
  - VoyagerClient
  - Any service class directly
  - Any storage adapter directly (unless it's building its own)

USAGE IN MAIN PROJECT:

    from read_flow import ReadFlow
    from read_flow.storage.sqlite_adapter import SQLiteAdapter

    # default SQLite storage
    flow = ReadFlow()

    # or plug in your own storage adapter
    flow = ReadFlow(storage=MyPostgresAdapter())

    # fetch own feed
    result = flow.fetch_feed()

    # fetch posts from specific profiles
    result = flow.fetch_profile_posts(['john-doe', 'jane-smith'])

    # search by hashtag (limited in 2.2.0 — see note in result)
    result = flow.search('#ai')

    # fetch engagement for stored posts
    result = flow.fetch_engagement(['urn:li:activity:123', 'urn:li:activity:456'])
"""

import logging
from typing import Any

from .auth import build_voyager_client
from .services.engagement_service import EngagementService
from .services.feed_service import FeedService
from .services.profile_service import ProfileService
from .services.search_service import SearchService
from .storage.base import StorageProtocol
from .storage.sqlite_adapter import SQLiteAdapter

logger = logging.getLogger(__name__)


class ReadFlow:
    """
    Single entry point for all LinkedIn read operations.
    Instantiate once; call methods as needed.

    Args:
        storage : any object implementing StorageProtocol.
                  Defaults to SQLiteAdapter (local file 'read_flow.db').
                  Pass your own adapter to plug in Postgres, MongoDB, etc.
    """

    def __init__(self, storage: StorageProtocol | None = None):
        logger.info("ReadFlow initialising", extra={"layer": "facade"})

        # Auth — builds VoyagerClient (the linkedin-api wrapper)
        self._client = build_voyager_client()

        # Storage — default SQLite, swappable by main project
        self._storage = storage or SQLiteAdapter()

        # Services — each depends only on protocols, never on concretions
        self._feed_service = FeedService(self._client, self._storage)
        self._profile_service = ProfileService(self._client, self._storage)
        self._search_service = SearchService(self._client, self._storage)
        self._engagement_service = EngagementService(self._client)

        logger.info("ReadFlow ready", extra={"layer": "facade"})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_feed(
        self,
        max_posts: int = 500,
        hashtag_filter: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Fetch posts from the authenticated account's own feed.

        Args:
            max_posts      : hard cap per run (default 500)
            hashtag_filter : e.g. ['#ai', '#python'] — None means keep all

        Returns:
            {success, fetched, saved, skipped_duplicate, skipped_filter, error}
        """
        logger.info(
            "ReadFlow.fetch_feed called",
            extra={"max_posts": max_posts, "hashtag_filter": hashtag_filter},
        )
        return self._feed_service.fetch_and_store(
            max_posts=max_posts,
            hashtag_filter=hashtag_filter,
        )

    def fetch_profile_posts(
        self,
        profile_ids: list[str],
        limit_per_profile: int = 50,
    ) -> dict[str, Any]:
        """
        Fetch recent posts from a list of LinkedIn profiles.

        Args:
            profile_ids       : vanity slugs or numeric IDs
                                e.g. ['john-doe', '824004659']
            limit_per_profile : max posts per profile (default 50)

        Returns:
            {success, profiles_attempted, profiles_failed,
             fetched, saved, skipped_duplicate, errors}
        """
        logger.info(
            "ReadFlow.fetch_profile_posts called",
            extra={
                "profile_count": len(profile_ids),
                "limit_per_profile": limit_per_profile,
            },
        )
        return self._profile_service.fetch_and_store(
            profile_ids=profile_ids,
            limit_per_profile=limit_per_profile,
        )

    def search(
        self,
        keywords: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        Search for posts by keyword or hashtag.

        NOTE: linkedin-api 2.2.0 has no native post search.
        This falls back to filtering own feed by keyword.
        The result dict includes a 'note' field explaining this.
        Will work correctly once VoyagerClient is upgraded.

        Args:
            keywords : search term e.g. '#ai' or 'machine learning'
            limit    : max results (default 50)

        Returns:
            {success, fetched, saved, skipped_duplicate, error, note}
        """
        logger.info(
            "ReadFlow.search called",
            extra={"keywords": keywords, "limit": limit},
        )
        return self._search_service.fetch_and_store(keywords=keywords, limit=limit)

    def fetch_engagement(
        self,
        post_urns: list[str],
        limit_per_post: int = 50,
    ) -> dict[str, Any]:
        """
        Fetch reactions and comments for a list of post URNs.

        NOTE: linkedin-api 2.2.0 returns HTTP 500 for both endpoints.
        Returns empty lists gracefully. Will work once VoyagerClient is upgraded.

        Args:
            post_urns      : e.g. ['urn:li:activity:123']
            limit_per_post : max reactions + comments per post

        Returns:
            {success, engagement: {<urn>: {reactions, comments}}, error, note}
        """
        logger.info(
            "ReadFlow.fetch_engagement called",
            extra={"post_count": len(post_urns)},
        )
        return self._engagement_service.fetch_engagement(
            post_urns=post_urns,
            limit_per_post=limit_per_post,
        )
