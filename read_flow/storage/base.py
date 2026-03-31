"""
read_flow/storage/base.py
------------------------------------
Storage abstraction — the main project implements this to plug in
its own storage backend (Postgres, MongoDB, SQLAlchemy, etc.)

WHY: The library should not force a storage technology on the main project.
By depending on StorageProtocol, services never import sqlite3 or any ORM.
The main project passes its own adapter at construction time.

WHAT IMPLEMENTS THIS:
  sqlite_adapter.py  — default SQLite impl for standalone use / testing
  Any class the main project provides that satisfies this protocol
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StorageProtocol(Protocol):
    """
    Minimum contract any storage adapter must fulfil.
    All methods accept/return plain dicts — no ORM types.
    """

    def save_post(self, post: dict[str, Any]) -> bool:
        """
        Persist a single post dict.
        Returns True if newly inserted, False if already existed (duplicate).
        Should never raise — swallow storage errors and return False.
        """
        ...

    def post_exists(self, url: str) -> bool:
        """
        Returns True if a post with this URL is already stored.
        Used for deduplication before saving.
        """
        ...
