import unittest
from unittest.mock import patch

from src.chat_llm import build_llm_chat_response, should_use_llm_chat


class ChatLlmTest(unittest.TestCase):
    def test_short_general_chat_uses_llm_chat(self):
        self.assertTrue(should_use_llm_chat("야"))
        self.assertTrue(should_use_llm_chat("안녕"))

    def test_stock_like_request_does_not_use_llm_chat(self):
        self.assertFalse(should_use_llm_chat("NVDA 체크해줘"))
        self.assertFalse(should_use_llm_chat("오늘 미국장 체크포인트 정리해줘"))
        self.assertFalse(should_use_llm_chat("나스닥 뭐 봐야 해?"))

    def test_missing_api_key_returns_configuration_message(self):
        with patch.dict("os.environ", {}, clear=True):
            response = build_llm_chat_response("야")

        self.assertEqual(response["mode"], "chat")
        self.assertIn("OPENAI_API_KEY", response["summary"])
        self.assertIn("llm_unconfigured", response["features"])


if __name__ == "__main__":
    unittest.main()
