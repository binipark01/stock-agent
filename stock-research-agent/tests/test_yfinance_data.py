import contextlib
import io
import math
import sys
import types
import unittest
from unittest.mock import patch


class _FakeSeries:
    def __init__(self, values):
        self._values = values

    def dropna(self):
        return self

    def tolist(self):
        return self._values


class _FakeFrame:
    def __init__(self, rows=None, columns=None):
        self._rows = rows or []
        self.columns = columns or []
        self.empty = not bool(self._rows)

    def head(self, limit):
        return _FakeFrame(self._rows[:limit], columns=self.columns)

    def reset_index(self):
        return self

    def to_dict(self, orient="records"):
        if orient == "records":
            return self._rows
        return {idx: row for idx, row in enumerate(self._rows)}

    def __getitem__(self, key):
        return _FakeSeries([row.get(key) for row in self._rows])


class _FakeOptionChain:
    def __init__(self):
        self.calls = _FakeFrame([
            {"strike": 45.0, "openInterest": 1200, "volume": 300, "lastPrice": 3.1, "impliedVolatility": 0.8},
            {"strike": 50.0, "openInterest": 2200, "volume": 500, "lastPrice": 1.4, "impliedVolatility": 0.9},
        ])
        self.puts = _FakeFrame([
            {"strike": 40.0, "openInterest": 900, "volume": 450, "lastPrice": 1.2, "impliedVolatility": 0.85},
            {"strike": 35.0, "openInterest": 300, "volume": 150, "lastPrice": 0.6, "impliedVolatility": 0.95},
        ])


class _FakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol
        self.fast_info = {
            "last_price": 44.25,
            "previous_close": 42.5,
            "market_cap": 123456789,
            "currency": "USD",
            "exchange": "NMS",
        }
        self.info = {
            "longName": "Iris Energy Limited",
            "sector": "Technology",
            "industry": "Information Technology Services",
            "marketCap": 123456789,
            "trailingPE": 31.2,
            "forwardPE": 22.4,
            "beta": 2.1,
            "shortPercentOfFloat": 0.18,
        }
        self.options = ("2026-05-15", "2026-06-19")
        self.news = [
            {"title": "IREN expands AI cloud", "publisher": "Yahoo Finance", "link": "https://example.com/iren", "providerPublishTime": 1770000000}
        ]
        self.calendar = {"Earnings Date": ["2026-05-07"], "Ex-Dividend Date": None}
        self.actions = _FakeFrame([
            {"Date": "2026-01-01", "Dividends": 0.0, "Stock Splits": 0.0},
        ])
        self.dividends = _FakeFrame([])
        self.splits = _FakeFrame([])
        self.major_holders = _FakeFrame([{"Breakdown": "insiders", "Value": "12%"}])
        self.institutional_holders = _FakeFrame([{"Holder": "Big Fund", "Shares": 1000000}])
        self.recommendations = _FakeFrame([{"period": "0m", "strongBuy": 3, "buy": 4, "hold": 2, "sell": 0, "strongSell": 0}])

    def option_chain(self, expiration):
        return _FakeOptionChain()


class _FakeOptionChainWithNanVolume:
    def __init__(self):
        self.calls = _FakeFrame([
            {"strike": 100.0, "openInterest": 10, "volume": math.nan, "lastPrice": 1.0, "impliedVolatility": 0.5},
            {"strike": 105.0, "openInterest": 20, "volume": 7, "lastPrice": 0.5, "impliedVolatility": 0.6},
        ])
        self.puts = _FakeFrame([
            {"strike": 95.0, "openInterest": 5, "volume": math.nan, "lastPrice": 0.8, "impliedVolatility": 0.7},
        ])


class _FakeTickerWithFragileProperties(_FakeTicker):
    def option_chain(self, expiration):
        return _FakeOptionChainWithNanVolume()

    @property
    def earnings_dates(self):
        raise ImportError("lxml missing")

    @property
    def insider_transactions(self):
        raise RuntimeError("holder endpoint flaky")


class _FakeFastInfoMapping:
    def __init__(self, noisy: bool = False):
        self.noisy = noisy
        self._values = {
            "lastPrice": 502.5,
            "previousClose": 500.0,
            "currency": "USD",
            "exchange": "PCX",
        }

    def get(self, key, default=None):
        if self.noisy:
            print(f"${key}: possibly delisted; no price data found", file=sys.stderr)
        return self._values.get(key, default)

    def keys(self):
        return self._values.keys()


class _FakeQuoteOnlyTicker:
    def __init__(self, symbol):
        self.symbol = symbol
        self.fast_info = {
            "last_price": 501.25,
            "previous_close": 500.0,
            "currency": "USD",
            "exchange": "PCX",
        }


    @property
    def info(self):
        raise AssertionError("quote-only fetch must not touch info/fundamentals")

    @property
    def earnings_dates(self):
        raise AssertionError("quote-only fetch must not touch earnings_dates")

    @property
    def news(self):
        raise AssertionError("quote-only fetch must not touch news")


class YfinanceDataTest(unittest.TestCase):
    def test_market_pack_collects_quote_options_fundamentals_news_calendar_and_holders(self):
        fake_yfinance = types.SimpleNamespace(Ticker=_FakeTicker)
        with patch.dict(sys.modules, {"yfinance": fake_yfinance}):
            from src.yfinance_data import build_yfinance_focus_lines, fetch_yfinance_market_pack

            pack = fetch_yfinance_market_pack("IREN")
            lines = build_yfinance_focus_lines(pack)

        self.assertTrue(pack["available"])
        self.assertEqual(pack["symbol"], "IREN")
        self.assertEqual(pack["quote"]["price"], 44.25)
        self.assertEqual(pack["fundamentals"]["long_name"], "Iris Energy Limited")
        self.assertEqual(pack["fundamentals"]["sector"], "Technology")
        self.assertEqual(pack["options"]["nearest_expiration"], "2026-05-15")
        self.assertEqual(pack["options"]["call_open_interest"], 3400)
        self.assertEqual(pack["options"]["put_volume"], 600)
        self.assertAlmostEqual(pack["options"]["put_call_volume_ratio"], 0.75)
        self.assertEqual(pack["options"]["top_call_strikes_by_oi"][0]["strike"], 50.0)
        self.assertEqual(pack["news"][0]["title"], "IREN expands AI cloud")
        self.assertIn("Earnings Date", pack["calendar"])
        self.assertEqual(pack["holders"]["institutional_holders"][0]["Holder"], "Big Fund")
        self.assertIn("YF Quote: IREN 44.25", lines[0])
        self.assertTrue(any("YF Options" in line and "P/C vol 0.75" in line for line in lines))
        self.assertTrue(any("YF Fundamentals" in line and "Technology" in line for line in lines))
        self.assertTrue(any("YF News" in line and "IREN expands AI cloud" in line for line in lines))

    def test_market_pack_is_safe_when_yfinance_is_missing(self):
        with patch.dict(sys.modules, {"yfinance": None}):
            from src.yfinance_data import build_yfinance_focus_lines, fetch_yfinance_market_pack

            pack = fetch_yfinance_market_pack("BMNR")
            lines = build_yfinance_focus_lines(pack)

        self.assertFalse(pack["available"])
        self.assertEqual(pack["source"], "yfinance_missing")
        self.assertEqual(lines, ["YF Pack: BMNR / yfinance 미설치 또는 호출 불가"])

    def test_market_pack_tolerates_nan_option_volume_and_flaky_yfinance_properties(self):
        fake_yfinance = types.SimpleNamespace(Ticker=_FakeTickerWithFragileProperties)
        with patch.dict(sys.modules, {"yfinance": fake_yfinance}):
            from src.yfinance_data import fetch_yfinance_market_pack

            pack = fetch_yfinance_market_pack("NVDA")

        self.assertTrue(pack["available"])
        self.assertEqual(pack["options"]["call_open_interest"], 30)
        self.assertEqual(pack["options"]["call_volume"], 7)
        self.assertEqual(pack["options"]["put_volume"], 0)
        self.assertEqual(pack["earnings_dates"], [])
        self.assertTrue(any("earnings_dates unavailable" in warning for warning in pack["warnings"]))
        self.assertTrue(any("insider_transactions unavailable" in warning for warning in pack["warnings"]))

    def test_yahoo_chart_quote_pack_uses_premarket_last_against_regular_close(self):
        import json
        from unittest.mock import Mock

        payload = {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "currency": "USD",
                            "exchangeName": "NYQ",
                            "regularMarketPrice": 64.98,
                            "chartPreviousClose": 76.46,
                            "regularMarketTime": 1777492802,
                        },
                        "timestamp": [1777551700, 1777551757],
                        "indicators": {"quote": [{"close": [66.0, 66.1]}]},
                    }
                ],
                "error": None,
            }
        }
        response = Mock()
        response.read.return_value = json.dumps(payload).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)

        with patch("urllib.request.urlopen", return_value=response):
            from src.yfinance_data import fetch_yahoo_chart_quote_pack

            pack = fetch_yahoo_chart_quote_pack("OKLO")

        self.assertTrue(pack["available"])
        self.assertEqual(pack["source"], "yahoo_chart_quote")
        self.assertEqual(pack["quote"]["price"], 66.1)
        self.assertEqual(pack["quote"]["previous_close"], 64.98)
        self.assertEqual(pack["quote"]["pct_change"], 1.72)
        self.assertEqual(pack["quote"]["regular_market_price"], 64.98)
        self.assertEqual(pack["quote"]["chart_previous_close"], 76.46)

    def test_quote_pack_uses_only_fast_quote_fields_for_intraday_alerts(self):
        fake_yfinance = types.SimpleNamespace(Ticker=_FakeQuoteOnlyTicker)
        with patch.dict(sys.modules, {"yfinance": fake_yfinance}):
            from src.yfinance_data import fetch_yfinance_quote_pack

            pack = fetch_yfinance_quote_pack("SPY")

        self.assertTrue(pack["available"])
        self.assertEqual(pack["source"], "yfinance_quote")
        self.assertEqual(pack["quote"]["price"], 501.25)
        self.assertEqual(pack["quote"]["previous_close"], 500.0)
        self.assertEqual(pack["quote"]["pct_change"], 0.25)
        self.assertEqual(pack["quote"]["exchange"], "PCX")

    def test_quote_pack_reads_yfinance_fast_info_mapping_objects(self):
        class _MappingQuoteTicker(_FakeQuoteOnlyTicker):
            def __init__(self, symbol):
                self.symbol = symbol
                self.fast_info = _FakeFastInfoMapping()

        fake_yfinance = types.SimpleNamespace(Ticker=_MappingQuoteTicker)
        with patch.dict(sys.modules, {"yfinance": fake_yfinance}):
            from src.yfinance_data import fetch_yfinance_quote_pack

            pack = fetch_yfinance_quote_pack("SPY")

        self.assertTrue(pack["available"])
        self.assertEqual(pack["quote"]["price"], 502.5)
        self.assertEqual(pack["quote"]["previous_close"], 500.0)
        self.assertEqual(pack["quote"]["pct_change"], 0.5)
        self.assertEqual(pack["quote"]["exchange"], "PCX")

    def test_quote_pack_suppresses_yfinance_fast_info_stderr_noise(self):
        class _NoisyMappingQuoteTicker(_FakeQuoteOnlyTicker):
            def __init__(self, symbol):
                self.symbol = symbol
                self.fast_info = _FakeFastInfoMapping(noisy=True)

        fake_yfinance = types.SimpleNamespace(Ticker=_NoisyMappingQuoteTicker)
        stderr = io.StringIO()
        with patch.dict(sys.modules, {"yfinance": fake_yfinance}), contextlib.redirect_stderr(stderr):
            from src.yfinance_data import fetch_yfinance_quote_pack

            pack = fetch_yfinance_quote_pack("VOY")

        self.assertEqual(stderr.getvalue(), "")
        self.assertTrue(pack["available"])
        self.assertEqual(pack["quote"]["price"], 502.5)
        self.assertTrue(any("possibly delisted" in warning for warning in pack["warnings"]))


if __name__ == "__main__":
    unittest.main()
