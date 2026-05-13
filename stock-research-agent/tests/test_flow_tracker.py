import tempfile
import unittest
from pathlib import Path


class FlowTrackerTest(unittest.TestCase):
    def _report(
        self,
        score_theme="space_aerospace",
        avg=3.0,
        breadth=78.0,
        relative=4.2,
        trading_value=2_500_000_000,
        vwap_above=5,
        pct5=1.2,
        leaders=None,
        constituents=None,
    ):
        default_constituents = [
            {"symbol": "RKLB", "pct_change_5m": pct5, "vwap_position_pct": 2.0, "rsi14": 78.0, "bollinger_position_pct": 96.0, "score_eligible": True},
            {"symbol": "RDW", "pct_change_5m": 0.8, "vwap_position_pct": 1.0, "rsi14": 66.0, "bollinger_position_pct": 82.0, "score_eligible": True},
            {"symbol": "ASTS", "pct_change_5m": 0.5, "vwap_position_pct": 0.5, "rsi14": 61.0, "bollinger_position_pct": 74.0, "score_eligible": True},
            {"symbol": "LUNR", "pct_change_5m": 0.2, "vwap_position_pct": 0.1, "rsi14": 57.0, "bollinger_position_pct": 62.0, "score_eligible": True},
            {"symbol": "PL", "pct_change_5m": 0.1, "vwap_position_pct": 0.1, "rsi14": 55.0, "bollinger_position_pct": 58.0, "score_eligible": True},
        ]
        return {
            "collected_at": "2026-05-10T13:35:00+00:00",
            "theme_baskets": [
                {
                    "key": score_theme,
                    "name": "우주/항공우주",
                    "average_pct_change": avg,
                    "breadth_positive_pct": breadth,
                    "relative_to_spy_pct": relative,
                    "trading_value": trading_value,
                    "leaders": leaders or [{"symbol": "RKLB", "pct_change": 8.0}, {"symbol": "RDW", "pct_change": 5.0}],
                    "constituents": (constituents if constituents is not None else default_constituents[:vwap_above]),
                }
            ],
            "flow_proxies": {"active": True, "candidates": [{"theme_key": score_theme, "summary": "우주 기관성 유입 의심"}]},
        }

    def test_theme_snapshot_scores_flow_proxy_inputs(self):
        from src.flow_tracker import build_theme_flow_snapshots

        snapshots = build_theme_flow_snapshots(self._report())

        self.assertEqual(snapshots[0]["theme_key"], "space_aerospace")
        self.assertGreaterEqual(snapshots[0]["flow_score"], 70)
        self.assertTrue(snapshots[0]["flow_proxy_active"])
        self.assertIn("RKLB", snapshots[0]["top_5m_symbols"])


    def test_theme_snapshot_includes_participation_and_entry_scores(self):
        from src.flow_tracker import build_theme_flow_snapshots

        snapshots = build_theme_flow_snapshots(self._report())
        snapshot = snapshots[0]

        self.assertEqual(snapshot["participation"]["state"], "확산")
        self.assertGreaterEqual(snapshot["participation"]["breadth_score"], 70)
        self.assertIn("RKLB", snapshot["participation"]["active_symbols"])
        self.assertIn(snapshot["entry_signal"]["judgment"], {"눌림 대기", "재돌파 확인"})
        self.assertGreater(snapshot["entry_signal"]["wait_score"], snapshot["entry_signal"]["chase_score"])
        self.assertIn("VWAP", snapshot["entry_signal"]["reason"])

    def test_detects_theme_leader_rotation(self):
        from src.flow_tracker import build_theme_flow_snapshots, detect_flow_events

        previous = build_theme_flow_snapshots(self._report(leaders=[{"symbol": "RKLB", "pct_change": 5.0}, {"symbol": "RDW", "pct_change": 3.0}]))
        current = build_theme_flow_snapshots(self._report(leaders=[{"symbol": "RDW", "pct_change": 7.0}, {"symbol": "RKLB", "pct_change": 4.0}]))

        events = detect_flow_events(current, previous)
        rotations = [event for event in events if event["event_type"] == "leader_rotation"]

        self.assertEqual(len(rotations), 1)
        self.assertIn("RKLB→RDW", rotations[0]["summary"])
        self.assertIn("대장 교체", rotations[0]["title"])

    def test_build_event_alert_includes_entry_judgment_and_rotation(self):
        from src.flow_tracker import build_flow_event_alert

        text = build_flow_event_alert([
            {
                "event_type": "leader_rotation",
                "title": "대장 교체",
                "theme_name": "우주/항공우주",
                "summary": "대장 RKLB→RDW / score 76→82 / 확산 3→5종목",
                "entry_signal": {"judgment": "눌림 대기", "chase_score": 42, "wait_score": 78},
            }
        ])

        self.assertIn("[대장 교체]", text)
        self.assertIn("RKLB→RDW", text)
        self.assertIn("눌림 대기", text)
        self.assertIn("추격42/대기78", text)

    def test_detects_new_flow_started_from_history(self):
        from src.flow_tracker import build_theme_flow_snapshots, detect_flow_events

        previous = build_theme_flow_snapshots(self._report(avg=0.2, breadth=35.0, relative=0.1, trading_value=50_000_000, vwap_above=1, pct5=0.1))
        current = build_theme_flow_snapshots(self._report())

        events = detect_flow_events(current, previous)

        self.assertTrue(any(event["event_type"] == "flow_started" for event in events))
        event = events[0]
        self.assertEqual(event["theme_key"], "space_aerospace")
        self.assertIn("score", event["summary"])
        self.assertIn("VWAP 위", event["summary"])

    def test_detects_flow_faded(self):
        from src.flow_tracker import build_theme_flow_snapshots, detect_flow_events

        previous = build_theme_flow_snapshots(self._report())
        current = build_theme_flow_snapshots(self._report(avg=0.1, breadth=35.0, relative=-0.2, trading_value=40_000_000, vwap_above=1, pct5=-0.5))

        events = detect_flow_events(current, previous)

        self.assertTrue(any(event["event_type"] == "flow_faded" for event in events))
        self.assertIn("약화", events[0]["title"])

    def test_run_cycle_persists_snapshots_and_suppresses_duplicate_events(self):
        from src.flow_tracker import run_flow_tracker_cycle

        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "flow.db")
            quiet = run_flow_tracker_cycle(self._report(avg=0.2, breadth=35.0, relative=0.1, trading_value=50_000_000, vwap_above=1, pct5=0.1), db_path=db_path)
            alert = run_flow_tracker_cycle(self._report(), db_path=db_path)
            duplicate = run_flow_tracker_cycle(self._report(relative=4.3), db_path=db_path)

        self.assertEqual(quiet["alert_text"], "")
        self.assertIn("[수급 신규]", alert["alert_text"])
        self.assertEqual(duplicate["alert_text"], "")

    def test_build_event_alert_is_short_and_actionable(self):
        from src.flow_tracker import build_flow_event_alert

        text = build_flow_event_alert([
            {
                "event_type": "flow_started",
                "title": "수급 신규",
                "theme_name": "우주/항공우주",
                "score": 81,
                "previous_score": 35,
                "summary": "score 35→81 / SPY대비 +4.20% / VWAP 위 5종목 / 5m RKLB +1.20%, RDW +0.80%",
            }
        ])

        self.assertIn("[수급 신규] 우주/항공우주", text)
        self.assertIn("VWAP 눌림", text)
        self.assertLessEqual(len(text), 700)


if __name__ == "__main__":
    unittest.main()
