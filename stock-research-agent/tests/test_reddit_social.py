import json
import unittest
from unittest.mock import patch

from src.main import build_response, infer_mode
from src.reddit_social import build_reddit_search_payload, parse_reddit_listing


class RedditSocialTest(unittest.TestCase):
    def test_parse_reddit_listing_extracts_ranked_posts(self) -> None:
        listing = {
            "data": {
                "children": [
                    {
                        "data": {
                            "subreddit": "wallstreetbets",
                            "title": "NVDA demand looks strong into earnings",
                            "selftext": "AI capex still looks bullish.",
                            "score": 321,
                            "num_comments": 88,
                            "permalink": "/r/wallstreetbets/comments/abc/nvda/",
                            "created_utc": 1710000000,
                            "url": "https://www.reddit.com/r/wallstreetbets/comments/abc/nvda/",
                        }
                    },
                    {
                        "data": {
                            "subreddit": "stocks",
                            "title": "MSFT capex risk debate",
                            "selftext": "margin pressure discussion",
                            "score": 80,
                            "num_comments": 12,
                            "permalink": "/r/stocks/comments/def/msft/",
                            "created_utc": 1710000100,
                        }
                    },
                ]
            }
        }

        posts = parse_reddit_listing(listing, query="NVDA")

        self.assertEqual(posts[0]["subreddit"], "wallstreetbets")
        self.assertEqual(posts[0]["score"], 321)
        self.assertEqual(posts[0]["comments"], 88)
        self.assertIn("NVDA demand", posts[0]["title"])
        self.assertTrue(posts[0]["url"].startswith("https://www.reddit.com/r/"))
        self.assertGreater(posts[0]["engagement_score"], posts[1]["engagement_score"])

    def test_reddit_search_payload_summarizes_public_hits(self) -> None:
        fake_posts = [
            {
                "subreddit": "stocks",
                "title": "NVDA earnings setup",
                "score": 120,
                "comments": 30,
                "url": "https://www.reddit.com/r/stocks/comments/1/nvda/",
                "text": "AI demand bullish",
                "query": "NVDA",
                "engagement_score": 180,
            }
        ]
        with patch("src.reddit_social.search_reddit_public", return_value=fake_posts):
            summary, focus, next_actions = build_reddit_search_payload("레딧 NVDA 반응", ["NVDA"])

        self.assertIn("Reddit", summary)
        self.assertTrue(any("r/stocks" in item for item in focus))
        self.assertTrue(any("score 120" in item for item in focus))
        self.assertTrue(any("교차검증" in item for item in next_actions))

    def test_reddit_mode_routes_and_build_response_uses_reddit_payload(self) -> None:
        self.assertEqual(infer_mode("레딧에서 NVDA 반응 찾아줘"), "reddit_search")
        fake_posts = [
            {
                "subreddit": "stocks",
                "title": "NVDA retail sentiment",
                "score": 10,
                "comments": 4,
                "url": "https://www.reddit.com/r/stocks/comments/2/nvda/",
                "text": "watch earnings",
                "query": "NVDA",
                "engagement_score": 18,
            }
        ]
        with patch("src.reddit_social.search_reddit_public", return_value=fake_posts):
            payload = build_response(json.dumps({"mode": "reddit_search", "symbols": ["NVDA"], "request": "레딧 NVDA"}, ensure_ascii=False))

        self.assertEqual(payload["mode"], "reddit_search")
        self.assertIn("reddit_public_search", payload["features"])
        self.assertTrue(any("Reddit" in item for item in payload["focus"]))


if __name__ == "__main__":
    unittest.main()
