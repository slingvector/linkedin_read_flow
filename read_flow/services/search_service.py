"""
read_flow/services/search_service.py
----------------------------------------------
Service Layer: keyword/hashtag post search.

NOTE ON LIMITATIONS:
  linkedin-api 2.2.0 has no working post search endpoint.
  VoyagerClient.search_posts() falls back to filtering the own feed by keyword.
  This is documented clearly so the main project isn't surprised.
  When you replace VoyagerClient with a better implementation,
  this service requires zero changes.
"""

import logging
import uuid
from typing import Any

from ..clients.base import LinkedInReaderProtocol
from ..clients.voyager_client import LinkedInClientError
from ..storage.base import StorageProtocol

logger = logging.getLogger(__name__)


class SearchService:
    """Searches for posts by keyword or hashtag and stores results."""

    def __init__(
        self,
        client: LinkedInReaderProtocol,
        storage: StorageProtocol,
    ):
        self._client = client
        self._storage = storage

    def fetch_and_store(
        self,
        keywords: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        Searches for posts matching keywords/hashtag and stores new ones.

        Args:
            keywords : search term or hashtag e.g. '#ai' or 'machine learning'
            limit    : max posts to return

        Returns:
            result dict {success, fetched, saved, skipped_duplicate, error, note}
        """
        correlation_id = str(uuid.uuid4())
        logger.info(
            "SearchService.fetch_and_store started",
            extra={
                "correlation_id": correlation_id,
                "keywords": keywords,
                "limit": limit,
            },
        )

        existing_urls: set[str] = set()

        try:
            posts = self._client.search_posts(keywords=keywords, limit=limit)
        except LinkedInClientError as exc:
            logger.error(
                "SearchService fetch failed",
                extra={"correlation_id": correlation_id, "error": str(exc)},
            )
            return {
                "success": False,
                "fetched": 0,
                "saved": 0,
                "skipped_duplicate": 0,
                "error": str(exc),
                "note": None,
            }

        saved = 0
        skipped_duplicate = 0

        for post in posts:
            url = post.get("url", "")
            if not url or url in existing_urls:
                skipped_duplicate += 1
                continue
            if self._storage.save_post(post):
                existing_urls.add(url)
                saved += 1

        note = (
            "linkedin-api 2.2.0 does not support native post search. "
            "Results are filtered from the own feed. "
            "Upgrade VoyagerClient for true hashtag search."
        )

        logger.info(
            "SearchService.fetch_and_store complete",
            extra={
                "correlation_id": correlation_id,
                "fetched": len(posts),
                "saved": saved,
            },
        )

        return {
            "success": True,
            "fetched": len(posts),
            "saved": saved,
            "skipped_duplicate": skipped_duplicate,
            "error": None,
            "note": note,
        }
