import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.kiwoom_client import (
    KiwoomConfig,
    KiwoomRestClient,
    build_kiwoom_data_client,
    build_kiwoom_trade_client,
    load_kiwoom_data_env,
    load_kiwoom_env,
    load_kiwoom_trade_env,
)


TOKEN_KEY = "to" + "ken"


class FakeResponse:
    def __init__(self, payload, headers=None, status_code=200):
        self._payload = payload
        self.headers = headers or {}
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self):
        self.posts = []
        self.responses = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.posts.append({"url": url, "json": json, "headers": headers or {}, "timeout": timeout})
        if not self.responses:
            raise AssertionError("no fake response queued")
        return self.responses.pop(0)


class KiwoomClientTest(unittest.TestCase):
    def test_load_env_selects_mock_domains_and_redacts_secrets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / "kiwoom.env"
            cache_path = Path(tmpdir) / "token.json"
            env_path.write_text(
                "KIWOOM_ENV=mock\n"
                "KIWOOM_APPKEY=fake-app-key\n"
                "KIWOOM_SECRETKEY=fake-secret-key\n"
                f"KIWOOM_TOKEN_CACHE={cache_path}\n",
                encoding="utf-8",
            )

            config = load_kiwoom_env(env_path)

            self.assertEqual(config.env, "mock")
            self.assertEqual(config.rest_base_url, "https://mockapi.kiwoom.com")
            self.assertEqual(config.websocket_url, "wss://mockapi.kiwoom.com:10000/api/dostk/websocket")
            self.assertEqual(config.token_cache, cache_path)
            self.assertNotIn("fake-app-key", repr(config))
            self.assertNotIn("fake-secret-key", repr(config))


    def test_data_and_trade_envs_are_split_between_prod_and_mock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / "kiwoom.env"
            prod_cache = Path(tmpdir) / "prod-token.json"
            mock_cache = Path(tmpdir) / "mock-token.json"
            env_path.write_text(
                "KIWOOM_ENV=mock\n"
                "KIWOOM_APPKEY=legacy-app-key\n"
                "KIWOOM_SECRETKEY=legacy-secret-key\n"
                "KIWOOM_DATA_ENV=prod\n"
                "KIWOOM_PROD_APPKEY=prod-app-key\n"
                "KIWOOM_PROD_SECRETKEY=prod-secret-key\n"
                f"KIWOOM_DATA_TOKEN_CACHE={prod_cache}\n"
                "KIWOOM_TRADE_ENV=mock\n"
                "KIWOOM_MOCK_APPKEY=mock-app-key\n"
                "KIWOOM_MOCK_SECRETKEY=mock-secret-key\n"
                f"KIWOOM_TRADE_TOKEN_CACHE={mock_cache}\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                data_config = load_kiwoom_data_env(env_path)
                trade_config = load_kiwoom_trade_env(env_path)

            self.assertEqual(data_config.normalized_env, "prod")
            self.assertEqual(data_config.purpose, "data")
            self.assertEqual(data_config.rest_base_url, "https://api.kiwoom.com")
            self.assertEqual(data_config.appkey, "prod-app-key")
            self.assertEqual(data_config.secretkey, "prod-secret-key")
            self.assertEqual(data_config.token_cache, prod_cache)
            self.assertEqual(trade_config.normalized_env, "mock")
            self.assertEqual(trade_config.purpose, "trade")
            self.assertEqual(trade_config.rest_base_url, "https://mockapi.kiwoom.com")
            self.assertEqual(trade_config.appkey, "mock-app-key")
            self.assertEqual(trade_config.secretkey, "mock-secret-key")
            self.assertEqual(trade_config.token_cache, mock_cache)
            self.assertNotIn("prod-secret-key", repr(data_config))
            self.assertNotIn("mock-secret-key", repr(trade_config))

    def test_trade_env_defaults_to_mock_even_when_legacy_env_is_prod(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / "kiwoom.env"
            env_path.write_text(
                "KIWOOM_ENV=prod\n"
                "KIWOOM_APPKEY=legacy-app-key\n"
                "KIWOOM_SECRETKEY=legacy-secret-key\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                data_config = load_kiwoom_data_env(env_path)
                trade_config = load_kiwoom_trade_env(env_path)

            self.assertEqual(data_config.normalized_env, "prod")
            self.assertEqual(data_config.purpose, "data")
            self.assertEqual(data_config.appkey, "legacy-app-key")
            self.assertEqual(trade_config.normalized_env, "mock")
            self.assertEqual(trade_config.purpose, "trade")
            self.assertEqual(trade_config.appkey, "legacy-app-key")
            self.assertTrue(str(trade_config.token_cache).endswith("kiwoom_token_mock.json"))

    def test_data_and_trade_client_factories_use_split_configs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / "kiwoom.env"
            env_path.write_text(
                "KIWOOM_DATA_ENV=prod\n"
                "KIWOOM_PROD_APPKEY=prod-app-key\n"
                "KIWOOM_PROD_SECRETKEY=prod-secret-key\n"
                "KIWOOM_TRADE_ENV=mock\n"
                "KIWOOM_MOCK_APPKEY=mock-app-key\n"
                "KIWOOM_MOCK_SECRETKEY=mock-secret-key\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                data_client = build_kiwoom_data_client(env_path, session=FakeSession())
                trade_client = build_kiwoom_trade_client(env_path, session=FakeSession())

            self.assertEqual(data_client.config.normalized_env, "prod")
            self.assertEqual(data_client.config.purpose, "data")
            self.assertEqual(trade_client.config.normalized_env, "mock")
            self.assertEqual(trade_client.config.purpose, "trade")

    def test_get_token_issues_and_caches_without_printing_secret_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "token.json"
            session = FakeSession()
            session.responses.append(
                FakeResponse(
                    {
                        "token_type": "Bearer",
                        TOKEN_KEY: "issued-token",
                        "expires_dt": "20991231235959",
                    }
                )
            )
            config = KiwoomConfig(
                env="mock",
                appkey="dummy",
                secretkey="dummy",
                token_cache=cache_path,
            )
            client = KiwoomRestClient(config, session=session)

            token = client.get_token()

            self.assertEqual(token, "issued-token")
            self.assertTrue(cache_path.exists())
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(cached["token_type"], "Bearer")
            self.assertEqual(cached["expires_dt"], "20991231235959")
            self.assertEqual(session.posts[0]["url"], "https://mockapi.kiwoom.com/oauth2/token")
            self.assertEqual(session.posts[0]["json"]["grant_type"], "client_credentials")
            self.assertNotIn("issued-token", repr(client))
            self.assertNotIn("secret-key", repr(client))

    def test_token_cache_is_scoped_to_kiwoom_environment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "token.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "env": "mock",
                        "token_type": "Bearer",
                        TOKEN_KEY: "mock-token",
                        "expires_dt": "20991231235959",
                    }
                ),
                encoding="utf-8",
            )
            session = FakeSession()
            session.responses.append(
                FakeResponse(
                    {
                        "token_type": "Bearer",
                        TOKEN_KEY: "prod-token",
                        "expires_dt": "20991231235959",
                    }
                )
            )
            config = KiwoomConfig(env="prod", appkey="app-key", secretkey="secret-key", token_cache=cache_path)
            client = KiwoomRestClient(config, session=session)

            token = client.get_token()

            self.assertEqual(token, "prod-token")
            self.assertEqual(session.posts[0]["url"], "https://api.kiwoom.com/oauth2/token")
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(cached["env"], "prod")
            self.assertEqual(cached[TOKEN_KEY], "prod-token")


    def test_issue_token_error_includes_safe_kiwoom_message(self):
        session = FakeSession()
        session.responses.append(FakeResponse({"return_code": 2, "return_msg": "투자구분이 달라서 Appkey를 사용할수가 없습니다"}))
        config = KiwoomConfig(env="prod", appkey="app-key", secretkey="secret-key", token_cache=None)
        client = KiwoomRestClient(config, session=session)

        with self.assertRaisesRegex(RuntimeError, "투자구분"):
            client.get_token()


    def test_post_tr_sends_api_id_and_continuation_headers(self):
        session = FakeSession()
        session.responses.append(
            FakeResponse(
                {
                    "token_type": "Bearer",
                    TOKEN_KEY: "issued-token",
                    "expires_dt": "20991231235959",
                }
            )
        )
        session.responses.append(
            FakeResponse(
                {"return_code": 0, "bid_req_base_tm": "093000"},
                headers={"cont-yn": "Y", "next-key": "NEXT123"},
            )
        )
        config = KiwoomConfig(env="mock", appkey="app-key", secretkey="secret-key", token_cache=None)
        client = KiwoomRestClient(config, session=session)

        result = client.post_tr("ka10004", "/api/dostk/mrkcond", {"stk_cd": "005930"})

        tr_call = session.posts[1]
        self.assertEqual(tr_call["url"], "https://mockapi.kiwoom.com/api/dostk/mrkcond")
        self.assertEqual(tr_call["headers"]["api-id"], "ka10004")
        self.assertEqual(tr_call["headers"]["authorization"], "Bearer issued-token")
        self.assertEqual(tr_call["headers"]["cont-yn"], "N")
        self.assertEqual(tr_call["headers"]["next-key"], "")
        self.assertEqual(result.data["bid_req_base_tm"], "093000")
        self.assertEqual(result.cont_yn, "Y")
        self.assertEqual(result.next_key, "NEXT123")


if __name__ == "__main__":
    unittest.main()
