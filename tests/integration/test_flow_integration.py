import unittest
from unittest.mock import patch
from read_flow.reader import ReadFlow
from read_flow.storage.sqlite_adapter import SQLiteAdapter
import read_flow.services.feed_service as feed_mod

feed_mod._BASE_DELAY_S = 0
feed_mod._JITTER_S = 0

class IntegrationMockClient:
    def get_feed_posts(self, limit=100):
        return [
            {"url": "int_u1", "content": "Integration Test 1", "hashtags": ["#test"]},
            {"url": "int_u2", "content": "Integration Test 2", "hashtags": []}
        ]

class TestFlowIntegration(unittest.TestCase):

    def setUp(self):
        self.patcher = patch("read_flow.reader.build_voyager_client")
        self.mock_build = self.patcher.start()
        self.mock_build.return_value = IntegrationMockClient()
        
        self.storage = SQLiteAdapter(":memory:")
        self.flow = ReadFlow(storage=self.storage)

    def tearDown(self):
        self.storage.close()
        self.patcher.stop()

    def test_integration_fetch_feed(self):
        result = self.flow.fetch_feed()
        self.assertTrue(result["success"])
        self.assertEqual(result["saved"], 2)
        
        rows = self.storage._conn.execute("SELECT url, content FROM posts ORDER BY url").fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], ("int_u1", "Integration Test 1"))
        self.assertEqual(rows[1], ("int_u2", "Integration Test 2"))

    def test_integration_duplicate_processing(self):
        self.flow.fetch_feed()
        result = self.flow.fetch_feed()
        
        self.assertTrue(result["success"])
        self.assertEqual(result["saved"], 2)
        self.assertEqual(result["skipped_duplicate"], 0)
        
        rows = self.storage._conn.execute("SELECT url FROM posts").fetchall()
        self.assertEqual(len(rows), 2)

if __name__ == '__main__':
    unittest.main()
