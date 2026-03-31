import unittest
from read_flow.storage.sqlite_adapter import SQLiteAdapter

class TestSQLiteAdapter(unittest.TestCase):

    def setUp(self):
        # Set up transient memory database equivalent to the previous pytest.fixture
        self.db = SQLiteAdapter(":memory:")

    def tearDown(self):
        # Gracefully sever memory mapping post test execution
        self.db.close()

    def test_sqlite_save_post_new(self):
        post = {
            "url": "https://linkedin.com/123",
            "post_urn": "urn:123",
            "author_name": "John Doe",
            "author_profile": "https://linkedin.com/in/johndoe",
            "content": "Hello World",
            "hashtags": ["#hello", "#world"],
            "source": "feed"
        }
        self.assertTrue(self.db.save_post(post))
        
        row = self.db._conn.execute("SELECT content FROM posts WHERE url = 'https://linkedin.com/123'").fetchone()
        self.assertEqual(row[0], "Hello World")

    def test_sqlite_save_post_upsert(self):
        post = {"url": "https://linkedin.com/test", "content": "Initial content"}
        self.db.save_post(post)
        
        post["content"] = "Updated content"
        post["hashtags"] = ["#update"]
        self.assertTrue(self.db.save_post(post))
        
        row = self.db._conn.execute("SELECT content, hashtags FROM posts WHERE url = 'https://linkedin.com/test'").fetchone()
        self.assertEqual(row[0], "Updated content")
        self.assertIn("update", row[1])

    def test_sqlite_post_exists(self):
        post = {"url": "https://linkedin.com/exists"}
        self.assertFalse(self.db.post_exists("https://linkedin.com/exists"))
        self.db.save_post(post)
        self.assertTrue(self.db.post_exists("https://linkedin.com/exists"))

    def test_sqlite_db_locked(self):
        # Tear table mapping to induce a raw SQL execution crash intentionally
        self.db._conn.execute("DROP TABLE posts")
        post = {"url": "bad"}
        self.assertFalse(self.db.save_post(post))

if __name__ == '__main__':
    unittest.main()
