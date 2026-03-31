import unittest
from typing import Any
from read_flow.clients.base import LinkedInReaderProtocol
from read_flow.clients.voyager_client import LinkedInClientError
from read_flow.services.feed_service import FeedService
from read_flow.storage.base import StorageProtocol
import read_flow.services.feed_service as feed_mod

# Hack the delays to zero globally within tests to prevent pipeline sleeps
feed_mod._BASE_DELAY_S = 0
feed_mod._JITTER_S = 0

class MockClient(LinkedInReaderProtocol):
    def __init__(self, posts=None, should_fail=False):
        self.posts = posts or []
        self.should_fail = should_fail
        
    def get_feed_posts(self, limit: int = 100) -> list[dict[str, Any]]:
        if self.should_fail:
            raise LinkedInClientError("Network error")
        return self.posts[:limit]
        
    def get_profile_posts(self, public_id: str, limit: int = 100) -> list[dict[str, Any]]: return []
    def search_posts(self, keywords: str, limit: int = 50) -> list[dict[str, Any]]: return []
    def get_post_reactions(self, post_urn: str, limit: int = 50) -> list[dict[str, Any]]: return []
    def get_post_comments(self, post_urn: str, limit: int = 50) -> list[dict[str, Any]]: return []

class MockStorage(StorageProtocol):
    def __init__(self):
        self.saved_urls = set()
    def save_post(self, post: dict) -> bool:
        self.saved_urls.add(post.get("url"))
        return True
    def post_exists(self, url: str) -> bool: return url in self.saved_urls

class TestFeedServiceSync(unittest.TestCase):

    def test_feed_service_happy_path(self):
        client = MockClient(posts=[
            {"url": "u1", "hashtags": ["#ai"]},
            {"url": "u2", "hashtags": ["#python"]}
        ])
        storage = MockStorage()
        service = FeedService(client, storage)
        
        result = service.fetch_and_store(max_posts=5)
        self.assertTrue(result["success"])
        self.assertEqual(result["fetched"], 2)
        self.assertEqual(result["saved"], 2)
        self.assertEqual(result["skipped_duplicate"], 0)
        self.assertEqual(result["skipped_filter"], 0)
        self.assertEqual(len(storage.saved_urls), 2)

    def test_feed_service_filtering(self):
        client = MockClient(posts=[
            {"url": "u1", "hashtags": ["#ai"]},
            {"url": "u2", "hashtags": ["#java"]}
        ])
        storage = MockStorage()
        service = FeedService(client, storage)
        
        result = service.fetch_and_store(max_posts=5, hashtag_filter=["#ai"])
        self.assertTrue(result["success"])
        self.assertEqual(result["fetched"], 2)
        self.assertEqual(result["saved"], 1)
        self.assertEqual(result["skipped_filter"], 1)
        self.assertIn("u1", storage.saved_urls)
        self.assertNotIn("u2", storage.saved_urls)

    def test_feed_service_unhappy_path(self):
        client = MockClient(should_fail=True)
        storage = MockStorage()
        service = FeedService(client, storage)
        
        result = service.fetch_and_store(max_posts=5)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Network error")
        self.assertEqual(result["fetched"], 0)
        self.assertEqual(result["saved"], 0)

if __name__ == '__main__':
    unittest.main()
