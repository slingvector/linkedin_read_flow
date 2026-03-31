"""
read_flow/services/engagement_service.py
---------------------------------------------------
Service Layer: fetch post engagement (reactions + comments).

NOTE ON LIMITATIONS:
  Both get_post_reactions() and get_post_comments() return HTTP 500
  in linkedin-api 2.2.0. VoyagerClient returns [] gracefully for both.

  This service is fully implemented and structured correctly — it will
  work automatically once VoyagerClient is upgraded to a working implementation.
  The main project sees consistent result dicts regardless.
"""

import logging
import time
import uuid
from typing import Any

from ..clients.base import LinkedInReaderProtocol
from ..clients.voyager_client import LinkedInClientError

logger = logging.getLogger(__name__)

_INTER_POST_DELAY_S = 2.0


class EngagementService:
    """Fetches reactions and comments for a list of post URNs."""

    def __init__(self, client: LinkedInReaderProtocol):
        # Engagement data is not persisted by this service —
        # it's returned to the caller (ReadFlow / main project) to handle.
        self._client = client

    def fetch_engagement(
        self,
        post_urns: list[str],
        limit_per_post: int = 50,
    ) -> dict[str, Any]:
        """
        Fetches reactions and comments for each post URN.

        Args:
            post_urns      : list of URN strings e.g. ['urn:li:activity:123']
            limit_per_post : max reactions + comments to fetch per post

        Returns:
            result dict {
                success: bool,
                engagement: {
                    <post_urn>: {
                        reactions: list[dict],
                        comments:  list[dict],
                    }
                },
                error: str | None,
                note:  str | None,   # library limitation notice if applicable
            }
        """
        correlation_id = str(uuid.uuid4())
        logger.info(
            "EngagementService.fetch_engagement started",
            extra={
                "correlation_id": correlation_id,
                "post_count": len(post_urns),
            },
        )

        engagement: dict[str, dict] = {}
        errors: list[str] = []

        for i, urn in enumerate(post_urns):
            try:
                reactions = self._client.get_post_reactions(urn, limit=limit_per_post)
                comments = self._client.get_post_comments(urn, limit=limit_per_post)
                engagement[urn] = {
                    "reactions": reactions,
                    "comments": comments,
                }
                logger.info(
                    "Engagement fetched",
                    extra={
                        "correlation_id": correlation_id,
                        "post_urn": urn,
                        "reactions": len(reactions),
                        "comments": len(comments),
                    },
                )
            except LinkedInClientError as exc:
                logger.error(
                    "Engagement fetch failed for post",
                    extra={
                        "correlation_id": correlation_id,
                        "post_urn": urn,
                        "error": str(exc),
                    },
                )
                errors.append(f"{urn}: {exc}")
                engagement[urn] = {"reactions": [], "comments": [], "error": str(exc)}

            if i < len(post_urns) - 1:
                time.sleep(_INTER_POST_DELAY_S)

        note = (
            "linkedin-api 2.2.0 returns HTTP 500 for reactions and comments endpoints. "
            "All engagement lists are empty. Upgrade VoyagerClient to fix."
            if all(
                len(v.get("reactions", [])) == 0 and len(v.get("comments", [])) == 0
                for v in engagement.values()
            )
            else None
        )

        logger.info(
            "EngagementService.fetch_engagement complete",
            extra={"correlation_id": correlation_id, "posts_processed": len(post_urns)},
        )

        return {
            "success": len(errors) < len(post_urns),
            "engagement": engagement,
            "error": "; ".join(errors) if errors else None,
            "note": note,
        }
