"""
read_flow/services/feed_service.py
--------------------------------------------
Service Layer: own feed read operations.

Depends on:
  LinkedInReaderProtocol  — never on VoyagerClient directly (DIP)
  StorageProtocol         — never on SQLiteAdapter directly (DIP)
"""

import logging
import random
import time
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


class FeedService:
    """Fetches and stores posts from the authenticated account's own feed."""

    def __init__(
        self,
        client: LinkedInReaderProtocol,
        storage: StorageProtocol,
    ):
        self._client = client
        self._storage = storage

    def fetch_and_store(
        self,
        max_posts: int = _MAX_POSTS_PER_RUN,
        hashtag_filter: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Fetches feed posts in batches, deduplicates, filters by hashtag if provided,
        and persists new posts via the storage adapter.

        Args:
            max_posts      : hard cap on total posts fetched per run
            hashtag_filter : if set, only keep posts containing at least one tag
                             e.g. ['#ai', '#python']  — case-insensitive, # optional

        Returns:
            result dict {success, fetched, saved, skipped_duplicate,
                         skipped_filter, error}
        """
        correlation_id = str(uuid.uuid4())
        logger.info(
            "FeedService.fetch_and_store started",
            extra={
                "correlation_id": correlation_id,
                "max_posts": max_posts,
                "hashtag_filter": hashtag_filter,
            },
        )

        existing_urls: set[str] = set()
        normalised_tags = self._normalise_tags(hashtag_filter or [])

        fetched_total = 0
        saved = 0
        skipped_duplicate = 0
        skipped_filter = 0

        try:
            while fetched_total < max_posts:
                batch_size = min(_BATCH_SIZE, max_posts - fetched_total)
                logger.info(
                    "Fetching feed batch",
                    extra={
                        "correlation_id": correlation_id,
                        "batch_size": batch_size,
                        "fetched_total": fetched_total,
                    },
                )

                posts = self._client.get_feed_posts(limit=batch_size)

                if not posts:
                    logger.info(
                        "Feed exhausted", extra={"correlation_id": correlation_id}
                    )
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

                # linkedin-api returns fewer than batch_size when feed is exhausted
                if len(posts) < batch_size:
                    logger.info(
                        "Feed exhausted (partial batch)",
                        extra={
                            "correlation_id": correlation_id,
                            "fetched_total": fetched_total,
                        },
                    )
                    break

                delay = _BASE_DELAY_S + random.uniform(0, _JITTER_S)
                logger.info(
                    "Rate limit delay",
                    extra={
                        "correlation_id": correlation_id,
                        "delay_s": round(delay, 1),
                    },
                )
                time.sleep(delay)

        except LinkedInClientError as exc:
            logger.error(
                "FeedService fetch failed",
                extra={"correlation_id": correlation_id, "error": str(exc)},
            )
            return self._result(
                False, fetched_total, saved, skipped_duplicate, skipped_filter, str(exc)
            )

        logger.info(
            "FeedService.fetch_and_store complete",
            extra={
                "correlation_id": correlation_id,
                "fetched": fetched_total,
                "saved": saved,
                "skipped_duplicate": skipped_duplicate,
                "skipped_filter": skipped_filter,
            },
        )
        return self._result(
            True, fetched_total, saved, skipped_duplicate, skipped_filter
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_tags(tags: list[str]) -> set[str]:
        return {t.lower().lstrip("#") for t in tags}

    @staticmethod
    def _passes_filter(post: dict, normalised_tags: set[str]) -> bool:
        post_tags = {t.lstrip("#") for t in (post.get("hashtags") or [])}
        return bool(normalised_tags & post_tags)

    @staticmethod
    def _result(
        success: bool,
        fetched: int,
        saved: int,
        skipped_duplicate: int,
        skipped_filter: int,
        error: str | None = None,
    ) -> dict[str, Any]:
        return {
            "success": success,
            "fetched": fetched,
            "saved": saved,
            "skipped_duplicate": skipped_duplicate,
            "skipped_filter": skipped_filter,
            "error": error,
        }
