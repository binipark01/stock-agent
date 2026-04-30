import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch


class SectorStrengthAlertRunnerTest(unittest.TestCase):
    def test_default_interval_is_five_minutes_and_once_dry_run_is_supported(self) -> None:
        from scripts.run_sector_strength_alerts import build_arg_parser

        parser = build_arg_parser()
        args = parser.parse_args([])
        self.assertEqual(args.interval_seconds, 300)
        self.assertFalse(args.once)
        self.assertFalse(args.dry_run)

        once_args = parser.parse_args(["--once", "--dry-run", "--interval-seconds", "60"])
        self.assertTrue(once_args.once)
        self.assertTrue(once_args.dry_run)
        self.assertEqual(once_args.interval_seconds, 60)

        gated_args = parser.parse_args(["--market-hours-only", "--change-only", "--cooldown-seconds", "900", "--state-file", "/tmp/sector.json"])
        self.assertTrue(gated_args.market_hours_only)
        self.assertTrue(gated_args.change_only)
        self.assertEqual(gated_args.cooldown_seconds, 900)
        self.assertEqual(gated_args.state_file, "/tmp/sector.json")

    def test_build_alert_text_is_concise_and_includes_top_sector_and_regime(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        payload = {
            "summary": "장중 테마 강약: 우주/항공우주 주도 / 암호화 약세 / 레짐 중립",
            "focus": [
                "시장 레짐: 중립",
                "강한 테마: 우주/항공우주 평균 +2.00% / 상승비율 80.0% / 주도 RKLB +4.00%",
                "약한 테마: 암호화/코인 관련주 평균 -2.00% / 상승비율 20.0% / 주도 COIN -1.00%",
                "오늘 먼저 볼 종목: RKLB +4.00%(우주/항공우주)",
                "ETF 시장 참고: 강세 XLK +2.00% / 약세 XLU -2.00%",
            ],
            "next_actions": ["고베타 신규진입은 QQQ/SPY 회복 확인"],
        }

        text = build_alert_text(payload)

        self.assertIn("장중 테마 강약", text)
        self.assertIn("RKLB", text)
        self.assertIn("ETF 시장 참고", text)
        self.assertIn("고베타", text)
        self.assertLessEqual(len(text), 1200)

    def test_build_alert_text_keeps_movers_and_etf_when_rotation_lines_expand_focus(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        payload = {
            "summary": "장중 테마 강약: 반도체/AI칩 > 메모리/스토리지 주도 / 반도체/AI칩 > AI 가속기/GPU 약세 / 레짐 중립",
            "focus": [
                "시장 레짐: 중립 / VIX 안정",
                "강한 테마: 반도체/AI칩 평균 +2.00% / 상승비율 70.0% / 주도 MU +6.00%",
                "약한 테마: 암호화/코인 관련주 평균 -1.00% / 상승비율 30.0% / 주도 COIN -1.00%",
                "강한 세부테마: 반도체/AI칩 > 메모리/스토리지 평균 +5.33% / 상승비율 100.0% / 주도 MU +6.00%",
                "약한 세부테마: 반도체/AI칩 > AI 가속기/GPU 평균 -3.00% / 상승비율 0.0% / 주도 NVDA -3.00%",
                "로테이션 해석: 반도체/AI칩 내부 메모리/스토리지로 자금 이동 / AI 가속기/GPU 약세(강세 MU +6.00% vs 약세 NVDA -3.00%)",
                "오늘 먼저 볼 종목: MU +6.00%(메모리/스토리지) | SNDK +6.00%(메모리/스토리지)",
                "ETF 시장 참고: 강세 기술 XLK +1.00% / 약세 유틸리티 XLU -1.00%",
                "벤치마크: SPY +0.00% / QQQ +0.00% / 기준시각 2026-04-30T13:35:00+00:00",
            ],
            "next_actions": ["메모리/스토리지 추격은 AI 가속기/GPU 회복 전까지 눌림/분할로 제한"],
        }

        text = build_alert_text(payload)

        self.assertIn("로테이션 해석", text)
        self.assertIn("오늘 먼저 볼 종목", text)
        self.assertIn("ETF 시장 참고", text)
        self.assertIn("벤치마크", text)
        self.assertLessEqual(len(text), 1200)

    def test_once_dry_run_calls_telegram_helper_without_real_send(self) -> None:
        from scripts.run_sector_strength_alerts import run_once

        response = {
            "summary": "장중 섹터 강약: XLK 주도",
            "focus": ["강한 섹터: 기술 XLK +2.00%"],
            "next_actions": ["추격매수 자제"],
        }
        fake_sender = Mock(return_value={"ok": True, "dry_run": True, "message_id": None})

        result = run_once(
            response_builder=Mock(return_value=response),
            sender=fake_sender,
            dry_run=True,
            env_file="/tmp/fake.env",
            timeout_seconds=3,
        )

        self.assertTrue(result["telegram"]["dry_run"])
        fake_sender.assert_called_once()
        config = fake_sender.call_args.args[1]
        self.assertTrue(config.dry_run)
        self.assertEqual(config.env_file, "/tmp/fake.env")
    def test_market_hours_only_skips_outside_regular_session_without_sending(self) -> None:
        from scripts.run_sector_strength_alerts import run_once

        fake_sender = Mock(return_value={"ok": True, "dry_run": True})
        result = run_once(
            response_builder=Mock(return_value={"summary": "장중 섹터 강약: XLK 주도"}),
            sender=fake_sender,
            dry_run=True,
            market_hours_only=True,
            now_provider=lambda: datetime(2026, 5, 2, 14, 0, tzinfo=timezone.utc),  # Saturday
        )

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "outside_market_hours")
        fake_sender.assert_not_called()

    def test_change_only_skips_unchanged_signature_inside_cooldown(self) -> None:
        from scripts.run_sector_strength_alerts import run_once

        response = {
            "mode": "sector_strength",
            "summary": "장중 테마 강약: 반도체/AI칩 주도 / 암호화 약세 / 레짐 중립",
            "data": {"sector_strength": {"regime": {"label": "neutral"}, "strong": [{"symbol": "XLK"}], "weak": [{"symbol": "XLU"}], "strong_themes": [{"key": "semiconductors"}], "weak_themes": [{"key": "crypto_equities"}], "strong_sub_themes": [{"key": "semis_memory_storage"}], "weak_sub_themes": [{"key": "semis_ai_accelerators"}], "watchlist_movers": [{"symbol": "MU"}] }},
        }
        fake_sender = Mock(return_value={"ok": True, "dry_run": True})
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "sector_state.json"
            first = run_once(
                response_builder=Mock(return_value=response),
                sender=fake_sender,
                dry_run=True,
                change_only=True,
                cooldown_seconds=900,
                state_file=str(state_file),
                now_provider=lambda: datetime(2026, 4, 30, 14, 0, tzinfo=timezone.utc),
            )
            second = run_once(
                response_builder=Mock(return_value=response),
                sender=fake_sender,
                dry_run=True,
                change_only=True,
                cooldown_seconds=900,
                state_file=str(state_file),
                now_provider=lambda: datetime(2026, 4, 30, 14, 5, tzinfo=timezone.utc),
            )

        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["signature"], "neutral|semiconductors|crypto_equities|semis_memory_storage|semis_ai_accelerators|MU")
        self.assertNotIn("XLK", first["signature"])
        self.assertEqual(second["status"], "skipped")
        self.assertEqual(second["reason"], "unchanged_cooldown")
        self.assertEqual(fake_sender.call_count, 1)

    def test_change_only_sends_when_regime_or_leader_changes_and_updates_state(self) -> None:
        from scripts.run_sector_strength_alerts import run_once

        neutral = {
            "mode": "sector_strength",
            "summary": "장중 섹터 강약: XLK 주도 / XLU 약세 / 레짐 중립",
            "data": {"sector_strength": {"regime": {"label": "neutral"}, "strong": [{"symbol": "XLK"}], "weak": [{"symbol": "XLU"}], "strong_themes": [{"key": "space_aerospace"}]}},
        }
        risk_off = {
            "mode": "sector_strength",
            "summary": "장중 섹터 강약: XLE 주도 / ARKK 약세 / 레짐 리스크오프",
            "data": {"sector_strength": {"regime": {"label": "risk_off"}, "strong": [{"symbol": "XLE"}], "weak": [{"symbol": "ARKK"}], "strong_themes": [{"key": "crypto_equities"}]}},
        }
        fake_sender = Mock(return_value={"ok": True, "dry_run": True})
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "sector_state.json"
            run_once(response_builder=Mock(return_value=neutral), sender=fake_sender, dry_run=True, change_only=True, state_file=str(state_file), now_provider=lambda: datetime(2026, 4, 30, 14, 0, tzinfo=timezone.utc))
            changed = run_once(response_builder=Mock(return_value=risk_off), sender=fake_sender, dry_run=True, change_only=True, state_file=str(state_file), now_provider=lambda: datetime(2026, 4, 30, 14, 5, tzinfo=timezone.utc))

        self.assertEqual(changed["status"], "ok")
        self.assertIn("signature", changed)
        self.assertEqual(fake_sender.call_count, 2)


if __name__ == "__main__":
    unittest.main()
