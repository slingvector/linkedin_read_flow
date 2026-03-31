"""
read_flow/services/profile_service.py
------------------------------------------------
Service Layer: fetch posts from specific LinkedIn profiles.
"""

import logging
import time
import uuid
from typing import Any

from ..clients.base import LinkedInReaderProtocol
from ..clients.voyager_client import LinkedInClientError
from ..storage.base import StorageProtocol

logger = logging.getLogger(__name__)

_INTER_PROFILE_DELAY_S = 3.0  # between profiles — be polite


class ProfileService:
    """Fetches and stores posts from a list of target LinkedIn profiles."""

    def __init__(
        self,
        client: LinkedInReaderProtocol,
        storage: StorageProtocol,
    ):
        self._client = client
        self._storage = storage

    def fetch_and_store(
        self,
        profile_ids: list[str],
        limit_per_profile: int = 50,
    ) -> dict[str, Any]:
        """
        Fetches recent posts from each profile in the list.

        Args:
            profile_ids       : list of vanity slugs or numeric IDs
                                e.g. ['john-doe', '824004659']
            limit_per_profile : max posts to fetch per profile

        Returns:
            result dict {success, profiles_attempted, profiles_failed,
                         fetched, saved, skipped_duplicate, errors}
        """
        correlation_id = str(uuid.uuid4())
        existing_urls: set[str] = set()
        profiles_attempted = 0
        profiles_failed = 0
        fetched_total = 0
        saved = 0
        skipped_duplicate = 0
        errors: list[str] = []

        logger.info(
            "ProfileService.fetch_and_store started",
            extra={
                "correlation_id": correlation_id,
                "profile_count": len(profile_ids),
                "limit_per_profile": limit_per_profile,
            },
        )

        for profile_id in profile_ids:
            profiles_attempted += 1
            logger.info(
                "Fetching profile posts",
                extra={"correlation_id": correlation_id, "profile_id": profile_id},
            )

            try:
                posts = self._client.get_profile_posts(
                    public_id=profile_id,
                    limit=limit_per_profile,
                )
            except LinkedInClientError as exc:
                logger.error(
                    "Profile fetch failed",
                    extra={
                        "correlation_id": correlation_id,
                        "profile_id": profile_id,
                        "error": str(exc),
                    },
                )
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
            logger.info(
                "Profile posts fetched",
                extra={
                    "correlation_id": correlation_id,
                    "profile_id": profile_id,
                    "count": len(posts),
                },
            )

            if profiles_attempted < len(profile_ids):
                time.sleep(_INTER_PROFILE_DELAY_S)

        success = profiles_failed < profiles_attempted
        logger.info(
            "ProfileService.fetch_and_store complete",
            extra={
                "correlation_id": correlation_id,
                "profiles_attempted": profiles_attempted,
                "profiles_failed": profiles_failed,
                "fetched": fetched_total,
                "saved": saved,
            },
        )

        return {
            "success": success,
            "profiles_attempted": profiles_attempted,
            "profiles_failed": profiles_failed,
            "fetched": fetched_total,
            "saved": saved,
            "skipped_duplicate": skipped_duplicate,
            "errors": errors,
        }
