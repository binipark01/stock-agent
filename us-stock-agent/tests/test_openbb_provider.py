import json
import subprocess
import unittest

from src.openbb_provider import (
    build_openbb_history,
    build_openbb_history_response,
    build_openbb_profile,
    build_openbb_profile_response,
    build_openbb_quote,
    build_openbb_quote_response,
)


class OpenBBProviderTest(unittest.TestCase):
    def test_build_openbb_quote_uses_external_python_and_normalizes_json(self) -> None:
        calls = []

        def fake_runner(cmd, *, input, text, capture_output, timeout, check):
            calls.append({"cmd": cmd, "input": input, "timeout": timeout, "check": check})
            payload = {
                "symbol": "RDDT",
                "name": "Reddit, Inc.",
                "last_price": 161.46,
                "prev_close": 166.56,
                "open": 168.5,
                "high": 169.1,
                "low": 159.6,
                "volume": 2726614,
                "currency": "USD",
            }
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

        quote = build_openbb_quote("RDDT", python_path="/tmp/openbb-python", runner=fake_runner)

        self.assertEqual(calls[0]["cmd"], ["/tmp/openbb-python", "-"])
        self.assertIn("obb.equity.price.quote", calls[0]["input"])
        self.assertEqual(quote["status"], "ok")
        self.assertEqual(quote["symbol"], "RDDT")
        self.assertEqual(quote["source"], "openbb:yfinance")
        self.assertEqual(quote["price"], 161.46)
        self.assertEqual(quote["previous_close"], 166.56)
        self.assertEqual(quote["pct_change"], -3.06)
        self.assertEqual(quote["volume"], 2726614)

    def test_build_openbb_history_returns_rows_from_external_python(self) -> None:
        def fake_runner(cmd, *, input, text, capture_output, timeout, check):
            payload = [
                {"date": "2024-01-02", "open": 472.16, "high": 473.67, "low": 470.49, "close": 472.65, "volume": 123623700},
                {"date": "2024-01-03", "open": 470.43, "high": 471.19, "low": 468.17, "close": 468.79, "volume": 103585900},
            ]
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

        history = build_openbb_history("SPY", start_date="2024-01-02", end_date="2024-01-05", python_path="/tmp/openbb-python", runner=fake_runner)

        self.assertEqual(history["status"], "ok")
        self.assertEqual(history["symbol"], "SPY")
        self.assertEqual(history["source"], "openbb:yfinance")
        self.assertEqual(len(history["rows"]), 2)
        self.assertEqual(history["rows"][0]["close"], 472.65)

    def test_build_openbb_profile_returns_company_profile(self) -> None:
        def fake_runner(cmd, *, input, text, capture_output, timeout, check):
            self.assertIn("obb.equity.profile", input)
            payload = {
                "symbol": "NVDA",
                "name": "NVIDIA Corporation",
                "sector": "Technology",
                "industry": "Semiconductors",
                "market_cap": 3000000000000,
                "exchange": "NMS",
                "website": "https://www.nvidia.com",
            }
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

        profile = build_openbb_profile("NVDA", python_path="/tmp/openbb-python", runner=fake_runner)

        self.assertEqual(profile["status"], "ok")
        self.assertEqual(profile["symbol"], "NVDA")
        self.assertEqual(profile["source"], "openbb:yfinance")
        self.assertEqual(profile["name"], "NVIDIA Corporation")
        self.assertEqual(profile["sector"], "Technology")
        self.assertEqual(profile["market_cap"], 3000000000000)

    def test_openbb_history_response_summarizes_rows(self) -> None:
        response = build_openbb_history_response({
            "status": "ok",
            "symbol": "SPY",
            "source": "openbb:yfinance",
            "rows": [
                {"date": "2024-01-02", "open": 472.16, "high": 473.67, "low": 470.49, "close": 472.65, "volume": 123623700},
                {"date": "2024-01-05", "open": 467.49, "high": 470.44, "low": 466.43, "close": 467.92, "volume": 86118900},
            ],
        })

        self.assertEqual(response["mode"], "openbb_history")
        self.assertTrue(any("SPY" in item and "2 rows" in item for item in response["focus"]))
        self.assertEqual(response["data"]["openbb_history"]["rows"][0]["close"], 472.65)

    def test_openbb_profile_response_summarizes_company_fields(self) -> None:
        response = build_openbb_profile_response({
            "status": "ok",
            "symbol": "NVDA",
            "name": "NVIDIA Corporation",
            "sector": "Technology",
            "industry": "Semiconductors",
            "market_cap": 3000000000000,
            "exchange": "NMS",
            "source": "openbb:yfinance",
        })

        self.assertEqual(response["mode"], "openbb_profile")
        self.assertTrue(any("Technology" in item for item in response["focus"]))

    def test_openbb_quote_response_uses_runtime_payload_without_live_call(self) -> None:
        response = build_openbb_quote_response(
            {
                "status": "ok",
                "symbol": "RDDT",
                "name": "Reddit, Inc.",
                "price": 161.46,
                "previous_close": 166.56,
                "pct_change": -3.06,
                "open": 168.5,
                "high": 169.1,
                "low": 159.6,
                "volume": 2726614,
                "currency": "USD",
                "source": "openbb:yfinance",
            }
        )

        self.assertEqual(response["mode"], "openbb_quote")
        self.assertIn("openbb", response["features"])
        self.assertTrue(any("RDDT" in item and "161.46" in item for item in response["focus"]))

    def test_build_openbb_quote_reports_unavailable_when_python_is_missing(self) -> None:
        def fake_runner(cmd, *, input, text, capture_output, timeout, check):
            raise FileNotFoundError(cmd[0])

        quote = build_openbb_quote("NVDA", python_path="/missing/openbb-python", runner=fake_runner)

        self.assertEqual(quote["status"], "unavailable")
        self.assertEqual(quote["symbol"], "NVDA")
        self.assertIn("/missing/openbb-python", quote["error"])


if __name__ == "__main__":
    unittest.main()
