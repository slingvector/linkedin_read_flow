"""
read_flow/clients/base.py
-----------------------------------
The isolation boundary for the unofficial linkedin-api library.

WHY THIS EXISTS:
  linkedin-api 2.2.0 is an unofficial library that can break silently
  when LinkedIn changes their internal API. By depending on this Protocol
  instead of on linkedin-api directly, the entire rest of the codebase
  (services, reader, main project) is insulated from that risk.

  If linkedin-api breaks:
    → implement a new VoyagerHTTPClient that hits Voyager directly
    → swap it into auth.py
    → zero changes anywhere else

WHAT IMPLEMENTS THIS:
  voyager_client.py  — wraps linkedin-api 2.2.0 (current)
  Any future client  — direct HTTP, mock for tests, etc.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LinkedInReaderProtocol(Protocol):
    """
    Minimum contract any LinkedIn read client must fulfil.
    All methods return raw dicts/lists — no linkedin-api types leak out.
    """

    def get_feed_posts(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Fetch posts from the authenticated account's own feed.
        Returns a list of raw post dicts.
        """
        ...

    def get_profile_posts(
        self,
        public_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Fetch posts from a specific profile by vanity slug or numeric ID.
        Returns a list of raw post dicts.
        """
        ...

    def search_posts(
        self,
        keywords: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Search for posts by keyword or hashtag.
        Returns a list of raw post dicts.
        Note: limited in linkedin-api 2.2.0 — see voyager_client.py for details.
        """
        ...

    def get_post_reactions(
        self,
        post_urn: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Fetch reactions for a post URN.
        Returns a list of raw reactor dicts.
        """
        ...

    def get_post_comments(
        self,
        post_urn: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Fetch comments for a post URN.
        Returns a list of raw comment dicts.
        """
        ...
