from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class SectorIntelligenceTest(unittest.TestCase):
    def _theme(
        self,
        key: str = "semiconductors",
        name: str = "반도체/AI칩",
        avg: float = 2.4,
        breadth: float = 82.0,
        leaders: list[dict] | None = None,
        constituents: list[dict] | None = None,
        **extra,
    ) -> dict:
        return {
            "key": key,
            "name": name,
            "average_pct_change": avg,
            "breadth_positive_pct": breadth,
            "relative_to_spy_pct": extra.pop("relative_to_spy_pct", 1.8),
            "etf_pct_change": extra.pop("etf_pct_change", 2.1),
            "return_5d_pct": extra.pop("return_5d_pct", 7.5),
            "return_20d_pct": extra.pop("return_20d_pct", 16.0),
            "trading_value_change_pct": extra.pop("trading_value_change_pct", 65.0),
            "breakout_count": extra.pop("breakout_count", 3),
            "leaders": leaders
            or [
                {"symbol": "NVDA", "pct_change": 3.2, "pct_change_5m": 0.6, "vwap_position_pct": 0.8, "rsi14": 64, "bollinger_position_pct": 78},
                {"symbol": "MU", "pct_change": 2.7, "pct_change_5m": 0.4, "vwap_position_pct": 0.5, "rsi14": 59, "bollinger_position_pct": 70},
            ],
            "constituents": constituents
            or [
                {"symbol": "NVDA", "pct_change": 3.2, "pct_change_5m": 0.6, "vwap_position_pct": 0.8, "rsi14": 64, "bollinger_position_pct": 78},
                {"symbol": "MU", "pct_change": 2.7, "pct_change_5m": 0.4, "vwap_position_pct": 0.5, "rsi14": 59, "bollinger_position_pct": 70},
                {"symbol": "ASML", "pct_change": 2.0, "pct_change_5m": 0.2, "vwap_position_pct": 0.2, "rsi14": 56, "bollinger_position_pct": 66},
                {"symbol": "AMD", "pct_change": 1.1, "pct_change_5m": -0.1, "vwap_position_pct": -0.1, "rsi14": 52, "bollinger_position_pct": 55},
            ],
            **extra,
        }

    def _sector_report(self, themes: list[dict] | None = None) -> dict:
        return {
            "collected_at": "2026-05-13T14:00:00+00:00",
            "summary": "sector snapshot",
            "benchmark": {"NASDAQ": 0.9, "SPY": 0.4, "SOXX": 2.2, "BTCUSDT": -0.5, "WTI": -0.2, "VIX": 0.1},
            "theme_baskets": themes or [self._theme()],
            "flow_proxies": {"active": True, "candidates": [{"theme_key": "semiconductors", "summary": "거래대금/VWAP 유입"}]},
            "macro_context": {"us10y_5m_pct": 1.4, "dxy_5m_pct": 0.6, "copper_5d_pct": 3.1},
        }

    def test_scores_persistent_theme_as_multi_day_leadership(self):
        from src.us.sector.intelligence import score_theme_persistence

        score = score_theme_persistence(self._theme())

        self.assertGreaterEqual(score["score"], 75)
        self.assertEqual(score["label"], "중기 주도")
        self.assertIn("5D", " ".join(score["reasons"]))
        self.assertIn("20D", " ".join(score["reasons"]))

    def test_build_report_fuses_flow_social_macro_and_watchlist_guard(self):
        from src.us.sector.intelligence import build_sector_intelligence_report

        social_report = {
            "claims": [
                {"author_handle": "bullish_bee", "theme": "semiconductors", "symbols": ["NVDA", "MU"], "direction": "bullish", "relevance_score": 92},
                {"author_handle": "trader_jsb", "theme": "semiconductors", "symbols": ["NVDA"], "direction": "bullish", "relevance_score": 78},
            ]
        }
        flow_events = [
            {"event_type": "leader_rotation", "title": "대장 교체", "theme_key": "semiconductors", "theme_name": "반도체/AI칩", "summary": "대장 MRVL→NVDA"}
        ]

        report = build_sector_intelligence_report(
            self._sector_report(),
            flow_events=flow_events,
            social_report=social_report,
            watchlist=["NVDA", "RKLB"],
            portfolio=["MU"],
        )

        top = report["leadership_tiers"][0]
        self.assertEqual(top["theme_key"], "semiconductors")
        self.assertTrue(top["social_confirmation"]["confirmed"])
        self.assertIn("bullish_bee", top["social_confirmation"]["handles"])
        self.assertIn("NVDA", report["guard"]["watchlist_hits"])
        self.assertIn("MU", report["guard"]["portfolio_hits"])
        joined_focus = "\n".join(report["focus_lines"])
        self.assertIn("수급", joined_focus)
        self.assertIn("Threads", joined_focus)
        self.assertIn("금리", joined_focus)

    def test_premarket_plan_separates_gap_chase_from_trigger_pullback(self):
        from src.us.sector.intelligence import build_premarket_plan

        gap_theme = self._theme(avg=3.7, breadth=88.0)
        plan = build_premarket_plan(self._sector_report([gap_theme]), watchlist=["NVDA"])

        self.assertEqual(plan["mode"], "premarket_plan")
        self.assertIn("NVDA", plan["trigger_symbols"])
        self.assertTrue(any("갭상 추격 금지" in line for line in plan["chase_warnings"]))
        self.assertTrue(any("눌림" in line or "VWAP" in line for line in plan["pullback_plan"]))

    def test_closing_review_flags_open_fakeout_and_next_day_continuation(self):
        from src.us.sector.intelligence import build_closing_review

        open_report = self._sector_report([
            self._theme("space_aerospace", "우주/항공우주", avg=4.2, breadth=86.0, leaders=[{"symbol": "LUNR", "pct_change": 8.0}]),
            self._theme("semiconductors", "반도체/AI칩", avg=1.1, breadth=65.0),
        ])
        close_report = self._sector_report([
            self._theme("semiconductors", "반도체/AI칩", avg=2.5, breadth=82.0),
            self._theme("space_aerospace", "우주/항공우주", avg=-0.4, breadth=38.0, leaders=[{"symbol": "LUNR", "pct_change": -2.0}]),
        ])

        review = build_closing_review(open_report, close_report)

        self.assertEqual(review["closing_leader"]["theme_key"], "semiconductors")
        self.assertIn("space_aerospace", [item["theme_key"] for item in review["fakeouts"]])
        self.assertIn("semiconductors", [item["theme_key"] for item in review["next_session_watch"]])

    def test_outcome_log_records_follow_through_return(self):
        from src.us.sector.intelligence import build_sector_intelligence_report, record_leadership_outcome

        alert_report = build_sector_intelligence_report(self._sector_report([self._theme(avg=1.2)]))
        later_report = self._sector_report([self._theme(avg=2.4)])
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "leadership_outcomes.jsonl"
            entry = record_leadership_outcome(path, alert_report, later_report, horizon_label="30m")
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(entry["horizon_label"], "30m")
        self.assertAlmostEqual(entry["realized_theme_return_delta"], 1.2)
        self.assertEqual(rows[0]["theme_key"], "semiconductors")

    def test_symbol_entry_score_marks_overextended_leader_as_wait(self):
        from src.us.sector.intelligence import score_symbol_entry

        entry = score_symbol_entry({"symbol": "NVDA", "pct_change": 6.0, "pct_change_5m": 1.4, "vwap_position_pct": 2.1, "rsi14": 79, "bollinger_position_pct": 96})

        self.assertEqual(entry["judgment"], "눌림 대기")
        self.assertGreater(entry["wait_score"], entry["chase_score"])
        self.assertIn("과열", entry["reason"])


class SectorIntelligenceRoutingTest(unittest.TestCase):
    def test_request_modes_route_new_sector_intelligence_prompts(self):
        from src.request_modes import infer_mode

        self.assertEqual(infer_mode("주도섹터 인텔리전스 해줘"), "sector_intelligence")
        self.assertEqual(infer_mode("오늘 프리장 플랜"), "premarket_plan")
        self.assertEqual(infer_mode("장 마감 복기"), "closing_review")

    def test_build_response_uses_supplied_sector_report_without_live_fetch(self):
        from src.main import build_response

        payload = {
            "mode": "sector_intelligence",
            "request": "주도섹터 인텔리전스",
            "sector_report": {
                "collected_at": "2026-05-13T14:00:00+00:00",
                "theme_baskets": [
                    {
                        "key": "semiconductors",
                        "name": "반도체/AI칩",
                        "average_pct_change": 2.2,
                        "breadth_positive_pct": 80.0,
                        "return_5d_pct": 6.0,
                        "return_20d_pct": 14.0,
                        "leaders": [{"symbol": "NVDA", "pct_change": 3.0}],
                        "constituents": [{"symbol": "NVDA", "pct_change": 3.0}],
                    }
                ],
            },
        }

        response = build_response(json.dumps(payload, ensure_ascii=False), explicit_mode="sector_intelligence")

        self.assertEqual(response["mode"], "sector_intelligence")
        self.assertIn("sector_intelligence", response["features"])
        self.assertEqual(response["data"]["sector_intelligence"]["leadership_tiers"][0]["theme_key"], "semiconductors")


if __name__ == "__main__":
    unittest.main()
