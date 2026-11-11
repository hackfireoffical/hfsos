import unittest

from app.providers.youtube import _first_success, _https_url


class YouTubeFallbackTests(unittest.IsolatedAsyncioTestCase):
    def test_only_https_instance_urls_are_accepted(self):
        self.assertEqual(_https_url("https://instance.example/"), "https://instance.example")
        self.assertIsNone(_https_url("http://instance.example"))
        self.assertIsNone(_https_url("not-a-url"))

    async def test_fallback_checks_more_than_one_instance(self):
        async def fake_search(base):
            if base == "healthy":
                return [{"provider": "test", "title": "result"}]
            return []

        result = await _first_success(["dead-one", "dead-two", "healthy"], fake_search)
        self.assertEqual(result[0]["title"], "result")


if __name__ == "__main__":
    unittest.main()
