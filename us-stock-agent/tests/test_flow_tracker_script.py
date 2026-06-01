import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class FlowTrackerScriptTest(unittest.TestCase):
    def _report(self, weak=False):
        return {
            "collected_at": "2026-05-10T13:35:00+00:00" if weak else "2026-05-10T13:40:00+00:00",
            "theme_baskets": [{
                "key": "space_aerospace",
                "name": "우주/항공우주",
                "average_pct_change": 0.2 if weak else 3.0,
                "breadth_positive_pct": 35.0 if weak else 78.0,
                "relative_to_spy_pct": 0.1 if weak else 4.2,
                "trading_value": 50_000_000 if weak else 2_500_000_000,
                "leaders": [{"symbol": "RKLB", "pct_change": 8.0}],
                "constituents": [{"symbol": "RKLB", "pct_change_5m": 0.1 if weak else 1.2, "vwap_position_pct": -0.1 if weak else 2.0, "score_eligible": True}],
            }],
            "flow_proxies": {"active": not weak, "candidates": [] if weak else [{"theme_key": "space_aerospace"}]},
        }

    def test_script_reads_input_json_and_prints_only_event_text_by_default(self):
        root = Path(__file__).resolve().parents[1]
        script = root / "scripts" / "run_flow_tracker_alerts.py"
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "flow.db"
            weak_path = Path(tmp) / "weak.json"
            strong_path = Path(tmp) / "strong.json"
            weak_path.write_text(json.dumps(self._report(weak=True), ensure_ascii=False), encoding="utf-8")
            strong_path.write_text(json.dumps(self._report(weak=False), ensure_ascii=False), encoding="utf-8")
            first = subprocess.run([sys.executable, str(script), "--db-path", str(db_path), "--input-json", str(weak_path)], text=True, capture_output=True, check=True)
            second = subprocess.run([sys.executable, str(script), "--db-path", str(db_path), "--input-json", str(strong_path)], text=True, capture_output=True, check=True)

        self.assertEqual(first.stdout.strip(), "")
        self.assertIn("[수급 신규] 우주/항공우주", second.stdout)
        self.assertIn("VWAP 눌림", second.stdout)


if __name__ == "__main__":
    unittest.main()
