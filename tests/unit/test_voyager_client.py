import unittest
from read_flow.clients.voyager_client import VoyagerClient

class TestVoyagerClient(unittest.TestCase):

    def test_extract_hashtags_from_metadata(self):
        text = "Here is some text without inline tags."
        raw = {
            "entityMetadata": {
                "tags": [
                    {"urn": "urn:li:hashtag:Python", "id": 123},
                    {"urn": "urn:li:hashtag:ai", "id": 456}
                ]
            }
        }
        extracted = VoyagerClient._extract_hashtags(text, raw)
        self.assertIn("#python", extracted)
        self.assertIn("#ai", extracted)
        self.assertEqual(len(extracted), 2)

    def test_extract_hashtags_regex_strips_urls_codeblocks(self):
        text = "Check out my link https://site.com/#header and my ```#code block``` plus an actual #Tag!"
        extracted = VoyagerClient._extract_hashtags(text)
        self.assertEqual(extracted, ["#tag"])

    def test_extract_hashtags_regex_matches_properly(self):
        text = "Great #MachineLearning and #AI. Also #python_dev!"
        extracted = VoyagerClient._extract_hashtags(text)
        self.assertIn("#machinelearning", extracted)
        self.assertIn("#ai", extracted)
        self.assertIn("#python_dev", extracted)
        self.assertEqual(len(extracted), 3)

if __name__ == '__main__':
    unittest.main()
