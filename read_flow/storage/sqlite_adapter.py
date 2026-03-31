"""
read_flow/storage/sqlite_adapter.py
----------------------------------------------
Default SQLite storage adapter. Implements StorageProtocol.

Use this for:
  - Standalone usage of the library
  - Local development / testing
  - When the main project doesn't provide its own adapter

The main project can replace this entirely by passing any object
that satisfies StorageProtocol to ReadFlow().
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any

from .base import StorageProtocol

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = "read_flow.db"


class SQLiteAdapter:
    """
    SQLite implementation of StorageProtocol.
    Thread-safe for single-process use (check_same_thread=False + WAL mode).
    """

    def __init__(self, db_path: str | Path = _DEFAULT_DB_PATH):
        self._db_path = str(db_path)
        self._conn = self._init_db()

    def _init_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")  # better concurrent read perf
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                url            TEXT    NOT NULL UNIQUE,
                post_urn       TEXT,
                author_name    TEXT,
                author_profile TEXT,
                content        TEXT,
                hashtags       TEXT,   -- JSON array string
                source         TEXT,   -- 'feed' | 'profile' | 'search'
                created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        logger.info(
            "SQLite storage ready",
            extra={"db_path": self._db_path, "adapter": "SQLiteAdapter"},
        )
        return conn

    def save_post(self, post: dict[str, Any]) -> bool:
        """
        Inserts or updates post. Returns True if successful.
        INSERT OR REPLACE handles updates at the DB level.
        """
        import json

        try:
            hashtags = post.get("hashtags") or []
            self._conn.execute(
                """
                INSERT OR REPLACE INTO posts
                    (url, post_urn, author_name, author_profile, content, hashtags, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    post.get("url"),
                    post.get("post_urn"),
                    post.get("author_name"),
                    post.get("author_profile"),
                    post.get("content"),
                    json.dumps(hashtags),
                    post.get("source"),
                ),
            )
            self._conn.commit()
            logger.debug(
                "Post saved or updated",
                extra={"url": post.get("url"), "adapter": "SQLiteAdapter"},
            )
            return True
        except Exception as exc:
            logger.error(
                "save_post failed",
                extra={
                    "url": post.get("url"),
                    "error": str(exc),
                    "adapter": "SQLiteAdapter",
                },
            )
            return False

    def post_exists(self, url: str) -> bool:
        try:
            row = self._conn.execute(
                "SELECT 1 FROM posts WHERE url = ? LIMIT 1", (url,)
            ).fetchone()
            return row is not None
        except Exception as exc:
            logger.error(
                "post_exists query failed",
                extra={"url": url, "error": str(exc), "adapter": "SQLiteAdapter"},
            )
            return False

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


# Runtime protocol check
assert isinstance(SQLiteAdapter.__new__(SQLiteAdapter), StorageProtocol), (
    "SQLiteAdapter does not implement StorageProtocol"
)
