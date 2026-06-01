import tempfile
import unittest
from pathlib import Path


class FlowStoreTest(unittest.TestCase):
    def test_sqlite_store_round_trips_theme_snapshots_and_events(self):
        from src.flow_store import init_flow_db, load_recent_theme_snapshots, save_flow_events, save_theme_snapshots, should_emit_event

        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "flow.db")
            init_flow_db(db_path)
            save_theme_snapshots(db_path, [{"timestamp": "2026-05-10T13:35:00+00:00", "theme_key": "space", "theme_name": "우주", "flow_score": 82, "breadth_positive_pct": 80.0}])
            rows = load_recent_theme_snapshots(db_path, theme_key="space")
            self.assertEqual(rows[0]["theme_key"], "space")
            self.assertEqual(rows[0]["flow_score"], 82)

            event = {"timestamp": "2026-05-10T13:40:00+00:00", "event_type": "flow_started", "theme_key": "space", "theme_name": "우주", "score": 82, "previous_score": 35, "summary": "score 35→82"}
            self.assertTrue(should_emit_event(db_path, event, cooldown_minutes=15, now="2026-05-10T13:40:00+00:00"))
            save_flow_events(db_path, [event])
            self.assertFalse(should_emit_event(db_path, event, cooldown_minutes=15, now="2026-05-10T13:45:00+00:00"))
            self.assertTrue(should_emit_event(db_path, event, cooldown_minutes=15, now="2026-05-10T14:00:00+00:00"))


if __name__ == "__main__":
    unittest.main()
