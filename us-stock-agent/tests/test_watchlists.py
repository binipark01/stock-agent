import json
import tempfile
import unittest
from pathlib import Path


class WatchlistsModuleTest(unittest.TestCase):
    def test_load_watchlist_normalizes_aliases_named_lists_and_reexports_from_main(self) -> None:
        from src.main import load_watchlist as main_load_watchlist
        from src.watchlists import load_watchlist

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config" / "watchlist.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "watchlist": ["nvda", "레딧", "  pltr "],
                        "portfolio": ["tsla"],
                        "lists": {
                            "optical": ["aaoi", "lite", "cohr"],
                            "ai_infra": ["엔비디아", "팔란티어"],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            loaded = load_watchlist(path)
            loaded_from_main = main_load_watchlist(path)

        self.assertEqual(loaded["watchlist"], ["NVDA", "RDDT", "PLTR"])
        self.assertEqual(loaded["portfolio"], ["TSLA"])
        self.assertEqual(loaded["lists"]["optical"], ["AAOI", "LITE", "COHR"])
        self.assertEqual(loaded["lists"]["ai_infra"], ["NVDA", "PLTR"])
        self.assertEqual(loaded_from_main, loaded)

    def test_save_watchlist_creates_parent_and_flatten_dedupes_symbols(self) -> None:
        from src.watchlists import flatten_watchlist_symbols, load_watchlist, save_watchlist

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "watchlist.json"
            saved = save_watchlist(
                path,
                watchlist=["레딧", "nvda", "RDDT"],
                portfolio=["tsla"],
                lists={"crypto": ["coin", "mara"], "optical": ["aaoi", "lite"]},
            )
            reloaded = load_watchlist(path)

        self.assertTrue(saved["saved"])
        self.assertEqual(reloaded["watchlist"], ["RDDT", "NVDA"])
        self.assertEqual(reloaded["portfolio"], ["TSLA"])
        self.assertEqual(flatten_watchlist_symbols(reloaded), ["RDDT", "NVDA", "TSLA", "COIN", "MARA", "AAOI", "LITE"])

    def test_filter_watchlist_scope_supports_korean_named_list_aliases(self) -> None:
        from src.watchlists import filter_watchlist_scope, flatten_watchlist_symbols, infer_watchlist_scope

        watchlist_data = {
            "watchlist": ["RDDT", "NVDA"],
            "portfolio": ["TSLA"],
            "lists": {"optical": ["AAOI", "LITE"], "crypto": ["COIN", "MARA"]},
        }

        scope = infer_watchlist_scope("광통신 watchlist만 봐줘", watchlist_data)
        filtered = filter_watchlist_scope(watchlist_data, scope)

        self.assertEqual(scope, "optical")
        self.assertEqual(flatten_watchlist_symbols(filtered), ["AAOI", "LITE"])
        self.assertEqual(filtered["watchlist"], [])
        self.assertEqual(filtered["portfolio"], [])
        self.assertEqual(filtered["lists"], {"optical": ["AAOI", "LITE"]})

    def test_stockcrew_krx_theme_aliases_normalize_to_yfinance_symbols(self) -> None:
        from src.watchlists import normalize_symbols

        self.assertEqual(
            normalize_symbols(["한미반도체", "에코프로비엠", "HD현대일렉트릭", "LIG넥스원", "두산로보틱스"]),
            ["042700.KS", "247540.KQ", "267260.KS", "079550.KS", "454910.KS"],
        )

    def test_infer_watchlist_scope_supports_stockcrew_krx_theme_aliases(self) -> None:
        from src.watchlists import filter_watchlist_scope, flatten_watchlist_symbols, infer_watchlist_scope

        watchlist_data = {"watchlist": [], "portfolio": [], "lists": {"krx_stockcrew_leaders": ["005930.KS", "000660.KS"]}}

        scope = infer_watchlist_scope("주식크루 국장 테마 리스트만 봐줘", watchlist_data)
        self.assertEqual(scope, "krx_stockcrew_leaders")
        self.assertEqual(flatten_watchlist_symbols(filter_watchlist_scope(watchlist_data, scope)), ["005930.KS", "000660.KS"])
        self.assertEqual(infer_watchlist_scope("한국장 대장섹터만", watchlist_data), "krx_stockcrew_leaders")
        sub_theme_data = {
            "watchlist": [],
            "portfolio": [],
            "lists": {
                "krx_stockcrew_leaders": ["005930.KS", "000660.KS"],
                "krx_stockcrew_semiconductors": ["005930.KS"],
                "krx_stockcrew_shipbuilding": ["329180.KS"],
            },
        }
        self.assertEqual(infer_watchlist_scope("국장 반도체만 봐줘", sub_theme_data), "krx_stockcrew_semiconductors")
        self.assertEqual(infer_watchlist_scope("국장 조선만 봐줘", sub_theme_data), "krx_stockcrew_shipbuilding")

    def test_repo_watchlist_contains_stockcrew_krx_theme_lists(self) -> None:
        from src.watchlists import load_watchlist

        watchlist = load_watchlist(Path(__file__).resolve().parents[1] / "config" / "watchlist.json")
        lists = watchlist["lists"]

        self.assertIn("krx_stockcrew_leaders", lists)
        self.assertIn("krx_stockcrew_semiconductors", lists)
        self.assertIn("krx_stockcrew_battery", lists)
        self.assertIn("krx_stockcrew_power_infra", lists)
        self.assertIn("krx_stockcrew_defense", lists)
        self.assertIn("krx_stockcrew_shipbuilding", lists)
        self.assertIn("krx_stockcrew_robotics", lists)
        self.assertIn("005930.KS", lists["krx_stockcrew_semiconductors"])
        self.assertIn("000660.KS", lists["krx_stockcrew_semiconductors"])
        self.assertIn("373220.KS", lists["krx_stockcrew_battery"])
        self.assertIn("267260.KS", lists["krx_stockcrew_power_infra"])
        self.assertIn("012450.KS", lists["krx_stockcrew_defense"])
        self.assertIn("329180.KS", lists["krx_stockcrew_shipbuilding"])
        self.assertIn("454910.KS", lists["krx_stockcrew_robotics"])
        self.assertEqual(len(lists["krx_stockcrew_leaders"]), len(set(lists["krx_stockcrew_leaders"])))

    def test_build_watchlist_scan_ranks_movers_and_keeps_list_context(self) -> None:
        from src.watchlists import build_watchlist_scan

        watchlist_data = {
            "watchlist": ["RDDT", "NVDA"],
            "portfolio": ["TSLA"],
            "lists": {"optical": ["AAOI", "LITE"], "crypto": ["COIN", "MARA"]},
        }
        quotes = {
            "SPY": {"price": 500.0, "previous_close": 500.0, "source": "unit", "timestamp": "2026-05-02T13:35:00+00:00"},
            "RDDT": {"price": 162.0, "previous_close": 150.0, "source": "unit", "timestamp": "2026-05-02T13:35:00+00:00"},
            "NVDA": {"price": 104.0, "previous_close": 100.0, "source": "unit", "timestamp": "2026-05-02T13:35:00+00:00"},
            "TSLA": {"price": 190.0, "previous_close": 200.0, "source": "unit", "timestamp": "2026-05-02T13:35:00+00:00"},
            "AAOI": {"price": 18.0, "previous_close": 16.0, "source": "unit", "timestamp": "2026-05-02T13:35:00+00:00"},
            "LITE": {"price": 70.0, "previous_close": 69.0, "source": "unit", "timestamp": "2026-05-02T13:35:00+00:00"},
            "COIN": {"price": 220.0, "previous_close": 210.0, "source": "unit", "timestamp": "2026-05-02T13:35:00+00:00"},
            "MARA": {"price": 14.0, "previous_close": 14.2, "source": "unit", "timestamp": "2026-05-02T13:35:00+00:00"},
        }

        scan = build_watchlist_scan(watchlist_data, quotes, collected_at="2026-05-02T13:35:00+00:00")

        self.assertTrue(scan["available"])
        self.assertEqual(scan["top_movers"][0]["symbol"], "AAOI")
        self.assertIn("optical", scan["top_movers"][0]["lists"])
        self.assertEqual(scan["weak_movers"][0]["symbol"], "TSLA")
        self.assertTrue(any("관심종목 스캔" in line and "AAOI" in line for line in scan["focus_lines"]))
        self.assertTrue(any("약한 종목" in line and "TSLA" in line for line in scan["focus_lines"]))


if __name__ == "__main__":
    unittest.main()
