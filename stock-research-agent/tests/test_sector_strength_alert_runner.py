import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

SECTOR_ALERT_COMPACT_LIMIT = 1800


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

        gated_args = parser.parse_args(["--market-hours-only", "--change-only", "--cooldown-seconds", "900", "--state-file", "/tmp/sector.json", "--mode", "oil_vix"])
        self.assertTrue(gated_args.market_hours_only)
        self.assertTrue(gated_args.change_only)
        self.assertEqual(gated_args.cooldown_seconds, 900)
        self.assertEqual(gated_args.state_file, "/tmp/sector.json")
        self.assertEqual(gated_args.mode, "oil_vix")
        trigger_args = parser.parse_args(["--mode", "oil_vix", "--trigger-only"])
        self.assertTrue(trigger_args.trigger_only)

    def test_strip_alert_display_noise_preserves_parenthesized_text_after_empty_separator_cleanup(self) -> None:
        from scripts.run_sector_strength_alerts import _strip_alert_display_noise

        comma_cleaned = _strip_alert_display_noise("TE +1.00%(원전, )")
        semicolon_cleaned = _strip_alert_display_noise("OSCR +2.00%(헬스케어; )")

        self.assertEqual(comma_cleaned, "TE +1.00%(원전)")
        self.assertEqual(semicolon_cleaned, "OSCR +2.00%(헬스케어)")
        self.assertNotIn("\x01", comma_cleaned + semicolon_cleaned)

    def test_build_alert_text_uses_readable_theme_telegram_template(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        payload = {
            "mode": "sector_strength",
            "summary": "장중 테마 강약: 우주/항공우주 주도 / 암호화 약세 / 장 분위기 중립",
            "collected_at": "2026-05-07T13:35:00+00:00",
            "focus": [
                "장 분위기: 중립 / VIX/오일/금리/DXY 뚜렷한 충격 없음",
                "강한 테마: 우주/항공우주 평균 +2.00% / 상승비율 80.0% / 주도 RKLB +4.00% | 반도체 평균 +1.20% / 상승비율 66.7% / 주도 MU +3.10%",
                "약한 테마: 암호화/코인 관련주 평균 -2.00% / 상승비율 20.0% / 주도 COIN -1.00% | 양자/차세대컴퓨팅 평균 -1.10% / 상승비율 25.0% / 주도 IONQ -0.50%",
                "오늘 먼저 볼 종목: RKLB +4.00%(우주/항공우주) — RSI 64(+5): 50선 위에서 재가속, 매수세 회복; MACD 0.72/0.41 hist +0.31(+0.09): 신호선 위·히스토그램 확대, 상승 모멘텀 강화; Stoch 88/82(+4): 과열권 K>D 유지, 강하지만 꺾이면 눌림; 구름 위 +3.3%, 전환선>기준선: 중기 상승추세·구름 지지; BB 92%(+8) 상단권: 상단 확장, 추격 부담; 종합: 추세·모멘텀 개선 중이나 과열권, 눌림/돌파 확인 | MU +3.10%(메모리/스토리지) — RSI 58(-3): 50선 위지만 탄력 둔화; MACD -0.12/-0.04 hist -0.08(-0.03): 신호선 아래·히스토그램 악화; Stoch 51/49(-6): 중립권 K>D 약화; 구름 안 -0.2%, 전환선<기준선: 추세 확인 필요; BB 49% 중립: 방향성 확인 필요; 종합: 상승은 있지만 모멘텀 둔화, 돌파 확인",
                "로테이션 해석: 우주 내부 발사체로 자금 이동 / 위성 약세",
                "ETF 시장 참고: 강세 XLK +2.00% / 약세 XLU -2.00%",
                "장 분위기: NASDAQ +0.10% / SPY +0.00% / SOXX +0.20% / BTCUSDT +0.30% / WTI -0.10% / VIX -0.20% / 기준시각 2026-05-07T13:35:00+00:00",
            ],
            "next_actions": ["고베타 신규진입은 SPY 회복 확인"],
        }

        text = build_alert_text(payload)

        self.assertTrue(text.startswith("[5분 테마 알림 | 22:35 KST / 09:35 ET]"))
        for heading in ("1) 시장", "2) 강한 테마", "3) 약한 테마", "4) 먼저 볼 종목"):
            self.assertIn(heading, text)
        self.assertNotIn("결론", text)
        self.assertIn("• 우주/항공우주\n  · 상승비율 80.0%", text)
        self.assertIn("  · 주도주:\n    - RKLB +4.00%", text)
        self.assertIn("  · 주도주:\n    - MU +3.10%", text)
        self.assertNotIn("• 우주/항공우주 평균 +2.00% / 상승비율 80.0% / 주도 RKLB", text)
        self.assertIn("• 암호화/코인 관련주\n  · 상승비율 20.0%", text)
        self.assertIn("  · 주도주:\n    - COIN -1.00%", text)
        self.assertIn("  · 주도주:\n    - IONQ -0.50%", text)
        self.assertNotIn("• 암호화/코인 관련주 평균 -2.00% / 상승비율 20.0% / 주도 COIN", text)
        self.assertNotIn("[Sector Strength Alert]", text)
        self.assertNotIn("[액션]", text)
        self.assertIn("RKLB", text)
        self.assertIn("RSI 64(+5): 50선 위에서 재가속", text)
        self.assertNotIn("MACD 0.72/0.41 hist +0.31(+0.09): 신호선 위·히스토그램 확대", text)
        self.assertNotIn("Stochastic Slow 88/82(+4): 과열권 K>D 유지", text)
        self.assertNotIn("구름", text)
        self.assertNotIn("전환선", text)
        self.assertNotIn("기준선", text)
        self.assertNotIn("BB 92%(+8) 상단권", text)
        self.assertIn("종합: 추세·모멘텀 개선 중", text)
        self.assertIn("NASDAQ", text)
        self.assertNotIn("고베타", text)
        self.assertNotIn("- 상태:", text)
        self.assertIn("- NASDAQ +0.10% / SPY +0.00% / SOXX +0.20% / BTCUSDT +0.30% / WTI -0.10% / VIX -0.20%", text)
        self.assertNotIn("- 벤치:", text)
        self.assertIn("• RKLB +4.00%(우주/항공우주)", text)
        self.assertIn("  · RSI 64(+5): 50선 위에서 재가속", text)
        self.assertNotIn("  · MACD 0.72/0.41 hist +0.31(+0.09): 신호선 위·히스토그램 확대", text)
        self.assertIn("  · 종합: 추세·모멘텀 개선 중", text)
        self.assertNotIn(" | MU +3.10%", text)
        self.assertNotIn("QQQ", text)
        self.assertNotIn("DXY", text)
        self.assertNotIn("금리", text)
        self.assertNotIn("[truncated]", text)
        self.assertLessEqual(len(text), SECTOR_ALERT_COMPACT_LIMIT)

    def test_build_alert_text_formats_long_movers_as_mobile_friendly_bullets(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        payload = {
            "mode": "sector_strength",
            "summary": "장중 테마 강약: 우주/항공우주 주도 / 장 분위기 중립",
            "collected_at": "2026-05-07T13:35:00+00:00",
            "focus": [
                "장 분위기: 중립 / VIX/오일/금리/DXY 뚜렷한 충격 없음",
                "강한 테마: 우주/항공우주 평균 +2.00% / 상승비율 80.0% / 주도 RKLB +4.00%",
                "약한 테마: 암호화/코인 관련주 평균 -2.00% / 상승비율 20.0% / 주도 COIN -1.00%",
                "오늘 먼저 볼 종목: RKLB +4.00%(우주/항공우주) — RSI 64(+5): 50선 위에서 재가속, 매수세 회복; MACD 0.72/0.41 hist +0.31(+0.09): 신호선 위·히스토그램 확대, 상승 모멘텀 강화; Stoch 88/82(+4): 과열권 K>D 유지, 강하지만 꺾이면 눌림; 구름 위 +3.3%, 전환선>기준선: 중기 상승추세·구름 지지; BB 92%(+8) 상단권: 상단 확장, 추격 부담; 종합: 추세·모멘텀 개선 중이나 과열권, 눌림/돌파 확인",
                "로테이션 해석: 우주 내부 발사체로 자금 이동 / 위성 약세",
                "ETF 시장 참고: 강세 XLK +2.00% / 약세 XLU -2.00%",
                "장 분위기: NASDAQ +0.10% / SPY +0.00% / SOXX +0.20% / BTCUSDT +0.30% / WTI -0.10% / VIX -0.20% / 기준시각 2026-05-07T13:35:00+00:00",
            ],
            "next_actions": ["고베타 신규진입은 SPY 회복 확인"],
        }

        text = build_alert_text(payload)

        self.assertIn("1) 시장\n- NASDAQ", text)
        self.assertNotIn("- 벤치:", text)
        self.assertNotIn("- 상태:", text)
        self.assertNotIn("시장 중립", text)
        self.assertNotIn("장 분위기 중립", text)
        self.assertIn("4) 먼저 볼 종목\n• RKLB +4.00%(우주/항공우주)", text)
        self.assertIn("\n  · RSI 64(+5): 50선 위에서 재가속", text)
        self.assertNotIn("\n  · MACD 0.72/0.41 hist +0.31(+0.09): 신호선 위·히스토그램 확대", text)
        self.assertNotIn("\n  · Stochastic Slow 88/82(+4): 과열권 K>D 유지", text)
        self.assertNotIn("구름", text)
        self.assertNotIn("전환선", text)
        self.assertNotIn("기준선", text)
        self.assertNotIn("BB 92%(+8) 상단권", text)
        self.assertIn("\n  · 종합: 추세·모멘텀 개선 중", text)
        self.assertNotIn("\n• 로테이션:", text)
        self.assertNotIn("DXY", text)
        self.assertNotIn("금리", text)
        self.assertLessEqual(len(text), SECTOR_ALERT_COMPACT_LIMIT)

    def test_build_alert_text_reduces_verbose_movers_instead_of_cutting_sections(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        verbose = " — RSI 64: 상승 탄력 양호; MACD 0.72/0.41: 상방 추세; Stoch 88/82: 단기 과열; 구름 위: 중기 추세 우위; BB 92% 상단권: 추격 부담; 종합: 추세는 강하지만 단기 과열, 눌림 확인"
        movers = " | ".join(f"M{i} +{i}.00%(테마){verbose}" for i in range(1, 6))
        payload = {
            "mode": "sector_strength",
            "summary": "장중 테마 강약: 우주/항공우주 주도 / 장 분위기 중립",
            "collected_at": "2026-05-07T13:35:00+00:00",
            "focus": [
                "장 분위기: 중립 / VIX/오일/금리/DXY 뚜렷한 충격 없음",
                "강한 테마: 우주/항공우주 평균 +2.00% / 상승비율 80.0% / 주도 RKLB +4.00%",
                "약한 테마: 암호화/코인 관련주 평균 -2.00% / 상승비율 20.0% / 주도 COIN -1.00%",
                f"오늘 먼저 볼 종목: {movers}",
                "로테이션 해석: 우주 내부 발사체로 자금 이동 / 위성 약세",
                "장 분위기: NASDAQ +0.10% / SPY +0.00% / SOXX +0.20% / BTCUSDT +0.30% / WTI -0.10% / VIX -0.20% / 기준시각 2026-05-07T13:35:00+00:00",
            ],
            "next_actions": ["추격보다 눌림 확인"],
        }

        text = build_alert_text(payload)

        self.assertIn("4) 먼저 볼 종목", text)
        self.assertNotIn("결론", text)
        self.assertNotIn("\n• 로테이션:", text)
        self.assertNotIn("시장 중립", text)
        self.assertNotIn("장 분위기 중립", text)
        self.assertIn("M1", text)
        self.assertIn("종합:", text)
        self.assertNotIn("[truncated]", text)
        self.assertLessEqual(len(text), SECTOR_ALERT_COMPACT_LIMIT)

    def test_build_alert_text_keeps_movers_while_omitting_rotation_and_etf_noise(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        payload = {
            "summary": "장중 테마 강약: 반도체 > 메모리/스토리지 주도 / 반도체 > AI 가속기/GPU 약세 / 장 분위기 중립",
            "focus": [
                "장 분위기: 중립 / VIX/오일/금리/DXY 뚜렷한 충격 없음",
                "강한 테마: 반도체 평균 +2.00% / 상승비율 70.0% / 주도 MU +6.00%",
                "약한 테마: 암호화/코인 관련주 평균 -1.00% / 상승비율 30.0% / 주도 COIN -1.00%",
                "강한 세부테마: 반도체 > 메모리/스토리지 평균 +5.33% / 상승비율 100.0% / 주도 MU +6.00%",
                "약한 세부테마: 반도체 > AI 가속기/GPU 평균 -3.00% / 상승비율 0.0% / 주도 NVDA -3.00%",
                "로테이션 해석: 반도체 내부 메모리/스토리지로 자금 이동 / AI 가속기/GPU 약세(강세 MU +6.00% vs 약세 NVDA -3.00%)",
                "오늘 먼저 볼 종목: MU +6.00%(메모리/스토리지) | SNDK +6.00%(메모리/스토리지)",
                "ETF 시장 참고: 강세 기술 XLK +1.00% / 약세 유틸리티 XLU -1.00%",
                "장 분위기: NASDAQ +0.10% / SPY +0.00% / SOXX +0.20% / BTCUSDT +0.30% / WTI -0.10% / VIX -0.20% / 기준시각 2026-04-30T13:35:00+00:00",
            ],
            "next_actions": ["메모리/스토리지 추격은 AI 가속기/GPU 회복 전까지 눌림/분할로 제한"],
        }

        text = build_alert_text(payload)

        self.assertNotIn("결론", text)
        self.assertIn("4) 먼저 볼 종목", text)
        self.assertNotIn("- 참고:", text)
        self.assertNotIn("ETF 시장 참고:", text)
        self.assertIn("1) 시장", text)
        self.assertNotIn("• 로테이션:", text)
        self.assertNotIn("\n• 반도체\n• AI칩", text)
        self.assertNotIn("QQQ", text)
        self.assertNotIn("[truncated]", text)
        self.assertLessEqual(len(text), SECTOR_ALERT_COMPACT_LIMIT)


    def test_build_alert_text_omits_intraday_risk_spikes_from_telegram_body(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        payload = {
            "mode": "sector_strength",
            "summary": "장중 테마 강약: 우주 주도 / 장 분위기 중립",
            "collected_at": "2026-05-08T13:35:00+00:00",
            "focus": [
                "장 분위기: 중립 / VIX/오일/금리/DXY 뚜렷한 충격 없음",
                "분봉 리스크: VIX 5m +0.88pt(+5.00%) / WTI 15m +1.20% / NASDAQ 5m -0.50%, SPY 5m -0.40%",
                "강한 테마: 우주/항공우주 평균 +2.00% / 상승비율 80.0% / 주도 RKLB +4.00%",
                "약한 테마: 양자/차세대컴퓨팅 평균 -2.00% / 상승비율 20.0% / 주도 IONQ -1.00%",
                "로테이션 해석: 우주 내부 발사체로 자금 이동 / 위성 약세",
                "장 분위기: NASDAQ -0.20% / SPY -0.10% / SOXX -0.60% / BTCUSDT +0.30% / WTI +0.20% / VIX +2.80% / 기준시각 2026-05-08T13:35:00+00:00",
            ],
            "next_actions": ["VIX/WTI 분봉 리스크 급등: 강한 테마도 추격보다 VWAP 눌림 대기"],
        }

        text = build_alert_text(payload)

        self.assertIn("1) 시장", text)
        self.assertNotIn("- 리스크:", text)
        self.assertNotIn("분봉 리스크", text)
        self.assertNotIn("NASDAQ 5m -0.50%", text)
        self.assertNotIn("결론", text)
        self.assertNotIn("VIX/WTI 분봉 리스크 급등", text)
        self.assertNotIn("조건은 VWAP 눌림 대기", text)
        self.assertNotIn("5분 뒤 SPY·주도테마 재확인", text)
        self.assertNotIn("추격보다", text)
        self.assertLessEqual(len(text), SECTOR_ALERT_COMPACT_LIMIT)

    def test_build_alert_text_surfaces_previous_close_strength_line(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        payload = {
            "mode": "sector_strength",
            "summary": "장중 테마 강약: 우주 주도 / 장 분위기 중립",
            "collected_at": "2026-05-08T13:35:00+00:00",
            "focus": [
                "장 분위기: 중립 / VIX 충격 없음",
                "강한 테마: 우주/항공우주 평균 +2.00% / 상승비율 80.0% / 주도 RKLB +4.00%",
                "약한 테마: 양자/차세대컴퓨팅 평균 -2.00% / 상승비율 20.0% / 주도 IONQ -1.00%",
                "전일종가 대비 현재 강세: RKLB +10.00% 가격 110, 정규장, 기준 전일 정규장 종가 대비 현재가, 출처 Yahoo chart 1m includePrePost | MU +9.00% 가격 109, 정규장, 기준 전일 정규장 종가 대비 현재가, 출처 Yahoo chart 1m includePrePost",
                "테마별 대장주: 우주/항공우주: RKLB +10.00% 가격 110, 정규장, 주도 | 반도체: MU +9.00% 가격 109, 정규장, 주도",
                "로테이션 해석: 우주 내부 발사체로 자금 이동 / 위성 약세",
                "장 분위기: NASDAQ +0.10% / SPY +0.00% / SOXX +0.20% / BTCUSDT +0.30% / WTI -0.10% / VIX -0.20% / 기준시각 2026-05-08T13:35:00+00:00",
            ],
            "next_actions": ["추격보다 눌림 확인"],
        }

        text = build_alert_text(payload)

        self.assertIn("현재 강세", text)
        self.assertNotIn("기준: 전일 정규장 종가 대비 현재가 / Yahoo chart 1m", text)
        self.assertNotIn("전일종가 대비 현재 강세", text)
        self.assertIn("RKLB $110(+10.00%)", text)
        self.assertIn("MU $109(+9.00%)", text)
        self.assertIn("4) 현재 강세", text)
        self.assertIn("• MU $109(+9.00%)", text)
        self.assertNotIn("반도체: MU", text)
        self.assertNotIn("AI: MU", text)
        self.assertNotIn("4) 먼저 볼 종목", text)
        self.assertNotIn("테마별 대장주:", text)
        self.assertNotIn("결론", text)
        self.assertLessEqual(len(text), SECTOR_ALERT_COMPACT_LIMIT)

    def test_build_alert_text_compacts_verbose_theme_leaders_without_cutting_sections(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        tech = " — RSI 64(+5): 50선 위에서 재가속; MACD 0.72/0.41 h+0.31(+0.09): 신호선 위·히스토그램 확대; Stochastic Slow 88/82(+4): 과열권 K>D 유지; BB 92%(+8) 상단권: 상단 확장; 종합: 모멘텀 개선 중"
        leaders = " | ".join(
            f"테마{i}: AAA{i} +{i}.00% 가격 {10+i}, 정규장, 정규장 종가 대비, 주도{tech}"
            for i in range(1, 8)
        )
        payload = {
            "mode": "sector_strength",
            "summary": "장중 테마 강약: 우주 주도 / 장 분위기 중립",
            "collected_at": "2026-05-07T13:35:00+00:00",
            "focus": [
                "장 분위기: 중립 / VIX/오일/금리/DXY 뚜렷한 충격 없음",
                "강한 테마: 우주 평균 +2.00% / 상승비율 80.0% / 주도 AAA1 +1.00% | 반도체 평균 +1.00% / 상승비율 70.0% / 주도 AAA2 +2.00%",
                "약한 테마: 양자 평균 -2.00% / 상승비율 20.0% / 주도 AAA7 -1.00%",
                f"테마별 대장주: {leaders}",
                "전일종가 대비 현재 강세: RKLB +34.22% 05.47 / AMD +11.44% 55.19 / 기준 전일 정규장 종가 대비 현재가 / Yahoo chart 1m includePrePost",
                "로테이션 해석: 우주 내부 발사체로 자금 이동 / 위성 약세",
                "장 분위기: NASDAQ +0.10% / SPY +0.00% / SOXX +0.20% / BTCUSDT +0.30% / WTI -0.10% / VIX -0.20% / 기준시각 2026-05-07T13:35:00+00:00",
            ],
            "next_actions": ["추격보다 눌림 확인"],
        }

        text = build_alert_text(payload)

        self.assertIn("4) 현재 강세", text)
        self.assertNotIn("결론", text)
        self.assertNotIn("4) 먼저 볼 종목", text)
        self.assertNotIn("테마별 대장주:", text)
        self.assertIn("AAA1", text)
        self.assertIn("AAA2", text)
        self.assertIn("현재 강세", text)
        self.assertNotIn("전일종가 대비 현재 강세", text)
        self.assertNotIn("전일 정규장 종가 대비 현재가", text)
        self.assertNotIn("[truncated]", text)
        self.assertLessEqual(len(text), SECTOR_ALERT_COMPACT_LIMIT)

    def test_build_alert_text_preserves_day_and_previous_volume(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        text = build_alert_text({
            "mode": "sector_strength",
            "summary": "장중 테마 강약: 우주 주도",
            "collected_at": "2026-05-07T13:35:00+00:00",
            "focus": [
                "장 분위기: 중립 / VIX 충격 없음",
                "강한 테마: 우주/항공우주 평균 +2.00% / 상승비율 80.0% / 거래대금 7.2M / 거래량 1.5M/3.0M(-50.00%) / 주도 RKLB +4.00%",
                "약한 테마: 양자/차세대컴퓨팅 평균 -2.00% / 상승비율 20.0% / 거래대금 2.0M / 거래량 당일 500.0K / 전일 1.0M / 전일대비 -50.00% / 주도 IONQ -1.00%",
                "테마별 대장주: 우주/항공우주: RKLB +4.00% 가격 30 / 거래량 1.0M/2.0M(-50.00%), 정규장, 주도 — RSI 64(+5): 50선 위에서 재가속; MACD 0.72/0.41 h+0.31(+0.09): 신호선 위·히스토그램 확대; Stochastic Slow 88/82(+4): 과열권 K>D 유지; BB 92%(+8) 상단권: 상단 확장",
                "전일종가 대비 현재 강세: RKLB +10.00% 가격 30 / 거래량 1.0M/2.0M(-50.00%) / 기준 전일 정규장 종가 대비 현재가 / 출처 Yahoo chart 1m includePrePost",
                "장 분위기: NASDAQ +0.10% / SPY +0.00% / SOXX +0.20% / BTCUSDT +0.30% / WTI -0.10% / VIX -0.20% / 기준시각 2026-05-07T13:35:00+00:00",
            ],
            "next_actions": ["조건은 VWAP 눌림 대기"],
        })

        self.assertIn("거래량 1.5M/3.0M(-50.00%)", text)
        self.assertIn("거래량 1.0M/2.0M(-50.00%)", text)
        self.assertIn("  · 주도주:\n    - RKLB $30(+4.00%)", text)
        self.assertNotIn("종목 체크", text)
        self.assertNotIn("4) 먼저 볼 종목", text)
        self.assertNotIn("테마별 대장주:", text)
        self.assertNotIn("현재 강세", text)
        self.assertNotIn("전일종가 대비 현재 강세", text)
        self.assertLessEqual(len(text), SECTOR_ALERT_COMPACT_LIMIT)

    def test_build_alert_text_surfaces_previous_day_strong_themes(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        text = build_alert_text({
            "mode": "sector_strength",
            "summary": "장중 테마 강약: 반도체 주도",
            "collected_at": "2026-05-08T13:35:00+00:00",
            "focus": [
                "장 분위기: 중립 / VIX 충격 없음",
                "강한 테마: 반도체 상승비율 80.0% / 거래대금 $1.0B / 거래량 10.0M/20.0M(-50.00%) / 주도 MU +4.00%",
                "약한 테마: 코인 상승비율 20.0% / 거래대금 $100.0M / 거래량 1.0M/2.0M(-50.00%) / 주도 COIN -1.00%",
                "전날 강했던 테마: 우주/항공우주 전일 상승비율 100.0% / 전일 거래대금 $72.0M / 전일 거래량 6.0M / 전일 주도 RKLB +12.00% / 전일종가 30 / 전일 거래량 1.0M, LUNR +7.00% / 전일종가 12 / 전일 거래량 2.0M",
                "테마별 대장주: 반도체: MU +4.00% 가격 110 / 거래량 5.0M/8.0M(-37.50%), 주도 — RSI 64(+5): 50선 위",
                "장 분위기: NASDAQ +0.10% / SPY +0.00% / SOXX +0.20% / BTCUSDT +0.30% / WTI -0.10% / VIX -0.20% / 기준시각 2026-05-08T13:35:00+00:00",
            ],
            "next_actions": [],
        })

        self.assertIn("4) 전날 강했던 테마", text)
        self.assertIn("• 우주/항공우주\n  · 전일 상승비율 100.0% / 전일 거래대금 $72.0M / 전일 거래량 6.0M", text)
        self.assertIn("  · 전일 주도주:\n    - RKLB $30(+12.00%) / 거래량 1.0M", text)
        self.assertIn("    - LUNR $12(+7.00%) / 거래량 2.0M", text)
        self.assertNotIn("4) 먼저 볼 종목", text)
        self.assertLessEqual(len(text), SECTOR_ALERT_COMPACT_LIMIT)

    def test_build_alert_text_omits_symbol_issue_by_default(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        text = build_alert_text({
            "mode": "sector_strength",
            "summary": "장중 테마 강약: 반도체 주도",
            "collected_at": "2026-05-07T13:35:00+00:00",
            "focus": [
                "장 분위기: 중립 / VIX 충격 없음",
                "강한 테마: 반도체 상승비율 80.0% / 거래대금 $1.0B / 거래량 10.0M/20.0M(-50.00%) / 주도 MU +4.00%",
                "약한 테마: 코인 상승비율 20.0% / 거래대금 $100.0M / 거래량 1.0M/2.0M(-50.00%) / 주도 COIN -1.00%",
                "테마별 대장주: 반도체: MU +4.00% 가격 110 / 거래량 5.0M/8.0M(-37.50%), 주도 — RSI 64(+5): 50선 위; MACD 0.72/0.41 h+0.31(+0.09): 신호선 위; Stochastic Slow 88/82(+4): 과열권",
                "장 분위기: NASDAQ +0.10% / SPY +0.00% / SOXX +0.20% / BTCUSDT +0.30% / WTI -0.10% / VIX -0.20% / 기준시각 2026-05-07T13:35:00+00:00",
            ],
            "data": {
                "sector_strength": {
                    "symbol_issues": {
                        "MU": "뉴스 - Micron이 AI 메모리 수요 기대감으로 강세 / 출처 Reuters"
                    }
                }
            },
        })

        self.assertIn("    - MU $110(+4.00%)", text)
        self.assertIn("      · 거래량 5.0M/8.0M(-37.50%)", text)
        self.assertNotIn("      · 이슈:", text)
        self.assertNotIn("출처 Reuters", text)
        self.assertNotIn("COIN 이슈", text)
        self.assertLessEqual(len(text), SECTOR_ALERT_COMPACT_LIMIT)

    def test_build_alert_text_surfaces_theme_news_when_enabled(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        payload = {
            "mode": "sector_strength",
            "summary": "장중 테마 강약: 반도체 주도",
            "collected_at": "2026-05-07T13:35:00+00:00",
            "focus": [
                "장 분위기: 중립 / VIX 충격 없음",
                "강한 테마: 반도체 상승비율 80.0% / 거래대금 $1.0B / 거래량 10.0M/20.0M(-50.00%) / 주도 MU +4.00%, NVDA +3.00%",
                "약한 테마: 코인 상승비율 20.0% / 거래대금 $100.0M / 거래량 1.0M/2.0M(-50.00%) / 주도 COIN -1.00%",
                "테마별 대장주: 반도체: MU +4.00% 가격 110 / 거래량 5.0M/8.0M(-37.50%), 주도",
                "장 분위기: NASDAQ +0.10% / SPY +0.00% / SOXX +0.20% / BTCUSDT +0.30% / WTI -0.10% / VIX -0.20% / 기준시각 2026-05-07T13:35:00+00:00",
            ],
            "data": {
                "sector_strength": {
                    "strong_themes": [{"key": "semiconductors", "name": "반도체"}],
                    "theme_news": {
                        "semiconductors": "AI 메모리 수요(MU), 목표가 상향(NVDA)",
                    },
                }
            },
        }
        with patch.dict("os.environ", {"SECTOR_ALERT_ENABLE_THEME_NEWS": "1"}):
            text = build_alert_text(payload)

        self.assertIn("• 반도체", text)
        self.assertIn("  · 뉴스: AI 메모리 수요(MU), 목표가 상향(NVDA)", text)
        self.assertLess(text.index("  · 뉴스:"), text.index("  · 주도주:"))
        self.assertNotIn("출처", text)

    def test_build_alert_text_can_disable_theme_news(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        with patch.dict("os.environ", {"SECTOR_ALERT_ENABLE_THEME_NEWS": "0"}):
            text = build_alert_text({
                "mode": "sector_strength",
                "summary": "장중 테마 강약: 반도체 주도",
                "collected_at": "2026-05-07T13:35:00+00:00",
                "focus": [
                    "장 분위기: 중립 / VIX 충격 없음",
                    "강한 테마: 반도체 상승비율 80.0% / 거래대금 $1.0B / 주도 MU +4.00%",
                    "약한 테마: 코인 상승비율 20.0% / 거래대금 $100.0M / 주도 COIN -1.00%",
                    "테마별 대장주: 반도체: MU +4.00% 가격 110 / 거래량 5.0M/8.0M(-37.50%), 주도",
                ],
                "data": {
                    "sector_strength": {
                        "strong_themes": [{"key": "semiconductors", "name": "반도체"}],
                        "theme_news": {"semiconductors": "AI 메모리 수요(MU)"},
                    }
                },
            })

        self.assertNotIn("  · 뉴스:", text)

    def test_yahoo_news_issue_is_korean_summary_not_raw_english_headline(self) -> None:
        from scripts.run_sector_strength_alerts import _select_yahoo_news_issue

        issue = _select_yahoo_news_issue(
            "RDW",
            {
                "quotes": [{"symbol": "RDW", "longname": "Redwire Corporation"}],
                "news": [
                    {
                        "title": "Market Chatter: Redwire, Other Space-Related Stocks Lifted by Optimism on SpaceX's Upcoming IPO",
                        "publisher": "MT Newswires",
                        "providerPublishTime": 1779815361,
                        "relatedTickers": ["RDW"],
                    }
                ],
            },
        )

        self.assertEqual(issue, "뉴스 - Redwire 등 우주 관련주가 SpaceX IPO 기대감에 상승")
        self.assertNotIn("출처", issue)
        self.assertNotIn("Market Chatter", issue)
        self.assertNotIn("Lifted by Optimism", issue)

    def test_yahoo_theme_news_groups_concrete_korean_topics(self) -> None:
        from scripts.run_sector_strength_alerts import _select_yahoo_theme_news_hits

        hits = _select_yahoo_theme_news_hits(
            "WULF",
            {
                "quotes": [{"symbol": "WULF", "longname": "TeraWulf Inc."}],
                "news": [
                    {
                        "title": "Stock Market Today: Nasdaq Shines; Micron Joins $1 Trillion Club, SpaceX Helps Lift These Names",
                        "providerPublishTime": 1779815361,
                        "relatedTickers": ["MU", "SPAX.PVT", "AZO", "WULF", "APP", "QCOM", "^IXIC"],
                    },
                    {
                        "title": "TeraWulf Rallies After Acquiring 1 GW 'Muskie' AI Data Campus In Kentucky",
                        "providerPublishTime": 1779815461,
                        "relatedTickers": ["WULF", "BTC-USD"],
                    },
                ],
            },
        )

        self.assertEqual(hits[0]["topic"], "AI 데이터센터 캠퍼스 확보")
        self.assertEqual(hits[0]["detail"], "켄터키 1GW AI 데이터센터 캠퍼스 확보로 인프라 전환 기대")
        self.assertEqual(hits[0]["symbol"], "WULF")

    def test_price_target_news_marks_raise_or_cut(self) -> None:
        from scripts.run_sector_strength_alerts import _price_target_direction_text, _theme_news_detail_for_title

        cut_title = "BofA Adjusts Price Target on Hims & Hers Health to $25 From $28"
        raise_title = "Micron Smashes $1 Trillion Market Cap After UBS Triples Price Target"

        self.assertEqual(_price_target_direction_text(cut_title), "목표가 하향($28→$25)")
        self.assertEqual(
            _theme_news_detail_for_title("HIMS", cut_title, ["목표가 조정"]),
            "목표가 하향($28→$25)으로 투자심리 부담",
        )
        self.assertEqual(
            _theme_news_detail_for_title("MU", raise_title, ["목표가 대폭 상향"]),
            "목표가 대폭 상향으로 AI 메모리 성장성 재평가",
        )

    def test_theme_news_summary_explains_cause_not_only_keywords(self) -> None:
        from scripts.run_sector_strength_alerts import _theme_news_summary_from_hits

        summary = _theme_news_summary_from_hits(
            [
                {
                    "symbol": "RDW",
                    "topic": "SpaceX IPO 기대감",
                    "detail": "SpaceX IPO 신청 뉴스로 우주·위성주 전반에 매수세",
                    "score": 180,
                    "published": 1779815461,
                },
                {
                    "symbol": "FLY",
                    "topic": "SpaceX IPO 기대감",
                    "detail": "SpaceX IPO 신청 뉴스로 우주·위성주 전반에 매수세",
                    "score": 170,
                    "published": 1779815361,
                },
                {
                    "symbol": "SIDU",
                    "topic": "수익성 개선 기대",
                    "detail": "적자 축소와 수익성 개선 기대가 부각",
                    "score": 130,
                    "published": 1779815261,
                },
            ],
            max_topics=2,
        )

        self.assertEqual(
            summary,
            "SpaceX IPO 신청 뉴스로 우주·위성주 전반에 매수세(RDW·FLY). 적자 축소와 수익성 개선 기대가 부각(SIDU)",
        )

    def test_build_sector_response_enriches_symbol_issues_from_theme_leaders(self) -> None:
        from scripts import run_sector_strength_alerts as runner

        response = {
            "mode": "sector_strength",
            "data": {
                "sector_strength": {
                    "strong_themes": [{"name": "반도체", "leaders": [{"symbol": "MU"}, {"symbol": "NVDA"}]}],
                    "weak_themes": [{"name": "코인", "leaders": [{"symbol": "COIN"}]}],
                }
            },
        }
        with patch.dict("os.environ", {"SECTOR_ALERT_ENABLE_SYMBOL_ISSUES": "1"}), patch.object(
            runner, "build_response", return_value=response
        ), patch.object(runner, "_build_alert_symbol_issue_lookup", return_value={"MU": "뉴스 - Micron이 AI 메모리 수요 기대감으로 강세"}) as issue_lookup:
            result = runner.build_sector_response()

        issue_lookup.assert_called_once_with(["MU", "NVDA", "COIN"])
        self.assertEqual(result["data"]["sector_strength"]["symbol_issues"], {"MU": "뉴스 - Micron이 AI 메모리 수요 기대감으로 강세"})


    def test_llm_rerank_reorders_theme_leaders_and_refreshes_focus_lines(self) -> None:
        from scripts import run_sector_strength_alerts as runner

        semis = {
            "key": "semiconductors",
            "name": "반도체",
            "breadth_positive_pct": 80.0,
            "average_pct_change": 4.0,
            "trading_value": 1_000_000_000,
            "day_volume": 10_000_000,
            "previous_volume": 20_000_000,
            "volume_vs_previous_pct": -50.0,
            "leader_candidates": [
                {"symbol": "SNDK", "price": 160.0, "pct_change": 8.0, "trading_value": 200_000_000, "leader_score": 90.0, "leader_score_basis": {"theme_leader_rank": 0.0}},
                {"symbol": "NVDA", "price": 110.0, "pct_change": 3.0, "trading_value": 500_000_000, "leader_score": 80.0, "leader_score_basis": {"theme_leader_rank": 100.0}},
                {"symbol": "AMD", "price": 120.0, "pct_change": 4.0, "trading_value": 450_000_000, "leader_score": 70.0, "leader_score_basis": {"theme_leader_rank": 85.0}},
                {"symbol": "MU", "price": 100.0, "pct_change": 4.0, "trading_value": 300_000_000, "leader_score": 60.0, "leader_score_basis": {"theme_leader_rank": 70.0}},
            ],
        }
        semis["leaders"] = [semis["leader_candidates"][0], semis["leader_candidates"][3], semis["leader_candidates"][1]]
        response = {
            "mode": "sector_strength",
            "focus": [
                "시장 분위기: NASDAQ +0.10% / SPY +0.00% / SOXX +0.20% / BTCUSDT +0.30% / WTI -0.10% / VIX -0.20%",
                "강한 테마: 반도체 상승비율 80.0% / 거래대금 $1.0B / 주도 SNDK +8.00%, MU +4.00%, NVDA +3.00%",
                "약한 테마: 기준 해당 없음",
                "테마별 대장주: 반도체: SNDK +8.00%",
            ],
            "data": {
                "sector_strength": {
                    "theme_baskets": [semis],
                    "strong_themes": [semis],
                    "weak_themes": [],
                    "theme_news": {"semiconductors": "AI GPU 수요가 강하고 대형 반도체에 매수세"},
                    "symbol_issues": {"NVDA": "AI GPU 수요 기대", "AMD": "AI 가속기 수요 기대"},
                }
            },
        }

        with patch.dict("os.environ", {"SECTOR_ALERT_ENABLE_LLM_RERANK": "1", "SECTOR_ALERT_LLM_API_KEY": "unit-key"}), patch.object(
            runner,
            "_call_llm_leader_rerank",
            return_value={"_model": "unit-llm", "themes": [{"key": "semiconductors", "leaders": ["NVDA", "AMD", "SNDK"], "reason": "대표성과 뉴스"}]},
        ) as llm_call:
            result = runner._rerank_sector_response_with_llm(response)

        llm_call.assert_called_once()
        leaders = result["data"]["sector_strength"]["strong_themes"][0]["leaders"]
        self.assertEqual([row["symbol"] for row in leaders], ["NVDA", "AMD", "SNDK"])
        self.assertIn("주도 NVDA +3.00%, AMD +4.00%, SNDK +8.00%", result["focus"][1])
        self.assertEqual(result["data"]["sector_strength"]["llm_leader_rerank"]["changed_theme_count"], 1)

    def test_build_sector_response_does_not_enrich_symbol_issues_by_default(self) -> None:
        from scripts import run_sector_strength_alerts as runner

        response = {
            "mode": "sector_strength",
            "data": {
                "sector_strength": {
                    "strong_themes": [{"name": "반도체", "leaders": [{"symbol": "MU"}]}],
                }
            },
        }
        with patch.object(runner, "build_response", return_value=response), patch.object(runner, "_build_alert_symbol_issue_lookup") as issue_lookup:
            result = runner.build_sector_response()

        issue_lookup.assert_not_called()
        self.assertNotIn("symbol_issues", result["data"]["sector_strength"])

    def test_build_sector_response_enriches_theme_news_when_enabled(self) -> None:
        from scripts import run_sector_strength_alerts as runner

        response = {
            "mode": "sector_strength",
            "data": {
                "sector_strength": {
                    "strong_themes": [{"key": "semiconductors", "name": "반도체", "leaders": [{"symbol": "MU"}]}],
                    "weak_themes": [{"key": "crypto_equities", "name": "코인", "leaders": [{"symbol": "COIN"}]}],
                }
            },
        }
        theme_news = {
            "semiconductors": "AI 메모리 수요(MU)",
            "반도체": "AI 메모리 수요(MU)",
        }
        with patch.dict("os.environ", {"SECTOR_ALERT_ENABLE_THEME_NEWS": "1"}), patch.object(
            runner, "build_response", return_value=response
        ), patch.object(runner, "_build_alert_theme_news_lookup", return_value=theme_news) as news_lookup:
            result = runner.build_sector_response()

        news_lookup.assert_called_once_with(result["data"]["sector_strength"])
        self.assertEqual(result["data"]["sector_strength"]["theme_news"], theme_news)

    def test_build_sector_response_can_disable_theme_news(self) -> None:
        from scripts import run_sector_strength_alerts as runner

        response = {
            "mode": "sector_strength",
            "data": {
                "sector_strength": {
                    "strong_themes": [{"key": "semiconductors", "name": "반도체", "leaders": [{"symbol": "MU"}]}],
                }
            },
        }
        with patch.dict("os.environ", {"SECTOR_ALERT_ENABLE_THEME_NEWS": "0"}), patch.object(
            runner, "build_response", return_value=response
        ), patch.object(runner, "_build_alert_theme_news_lookup") as news_lookup:
            result = runner.build_sector_response()

        news_lookup.assert_not_called()
        self.assertNotIn("theme_news", result["data"]["sector_strength"])

    def test_theme_news_row_selection_keeps_weak_theme_coverage(self) -> None:
        from scripts.run_sector_strength_alerts import _theme_news_rows

        rows = _theme_news_rows(
            {
                "strong_themes": [
                    {"key": "strong_1", "name": "강1"},
                    {"key": "strong_2", "name": "강2"},
                    {"key": "strong_3", "name": "강3"},
                ],
                "weak_themes": [
                    {"key": "weak_1", "name": "약1"},
                    {"key": "weak_2", "name": "약2"},
                ],
            },
            max_themes=4,
        )

        self.assertEqual([row["key"] for row in rows], ["strong_1", "weak_1", "strong_2", "weak_2"])

    def test_build_alert_text_does_not_cut_strong_themes_to_two_when_leaders_exist(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        text = build_alert_text({
            "mode": "sector_strength",
            "summary": "장중 테마 강약: 우주 주도",
            "collected_at": "2026-05-07T13:35:00+00:00",
            "focus": [
                "장 분위기: 중립 / VIX 충격 없음",
                "강한 테마: 우주 평균 +3.00% / 상승비율 80.0% / 주도 AAA +3.00% | 반도체 평균 +2.00% / 상승비율 70.0% / 주도 BBB +2.00% | 양자 평균 +1.00% / 상승비율 60.0% / 주도 CCC +1.00%",
                "약한 테마: 헬스 평균 -1.00% / 상승비율 20.0% / 주도 DDD -1.00% | 코인 평균 -2.00% / 상승비율 10.0% / 주도 EEE -2.00% | 원전 평균 -3.00% / 상승비율 5.0% / 주도 FFF -3.00%",
                "테마별 대장주: 우주: AAA +3.00% 가격 10, 주도 | 반도체: BBB +2.00% 가격 20, 주도 | 양자: CCC +1.00% 가격 30, 주도",
                "장 분위기: NASDAQ +0.10% / SPY +0.00% / SOXX +0.20% / BTCUSDT +0.30% / WTI -0.10% / VIX -0.20% / 기준시각 2026-05-07T13:35:00+00:00",
            ],
        })

        self.assertIn("• 우주\n  · 상승비율 80.0%", text)
        self.assertIn("• 반도체\n  · 상승비율 70.0%", text)
        self.assertIn("• 양자\n  · 상승비율 60.0%", text)
        self.assertIn("• 헬스\n  · 상승비율 20.0%", text)
        self.assertIn("• 코인\n  · 상승비율 10.0%", text)
        self.assertIn("• 원전\n  · 상승비율 5.0%", text)
        self.assertNotIn("4) 먼저 볼 종목", text)

    def test_oil_vix_alert_signature_and_text_focus_on_triggers(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_signature, build_alert_text

        response = {
            "mode": "oil_vix",
            "summary": "Oil/VIX: 백워데이션 / 유가 급등/인플레 압력",
            "focus": [
                "트리거: vix_high, vix_backwardation, oil_shock",
                "VIX: 27 / +12.00% / 9D 30 / 3M 24",
                "유가: WTI 85 +4.20% / Brent 88 +3.90%",
            ],
            "data": {
                "oil_vix": {
                    "alerts": ["vix_high", "vix_backwardation", "oil_shock"],
                    "vix": {"structure": "backwardation", "spot": {"pct_change": 12.0}},
                    "oil": {"state": "oil_shock", "wti": {"pct_change": 4.2}},
                }
            },
            "next_actions": ["고베타 추격 중지"],
        }

        self.assertEqual(build_alert_signature(response), "oil_vix|vix_high,vix_backwardation,oil_shock|backwardation|oil_shock")
        text = build_alert_text(response)
        self.assertIn("vix_high", text)
        self.assertIn("WTI", text)
        self.assertIn("고베타", text)

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
    def test_trigger_only_skips_oil_vix_when_no_explicit_alerts(self) -> None:
        from scripts.run_sector_strength_alerts import run_once

        response = {
            "mode": "oil_vix",
            "summary": "Oil/VIX: 콘탱고 / 유가 충격 제한",
            "data": {"oil_vix": {"alerts": [], "vix": {"structure": "contango"}, "oil": {"state": "neutral"}}},
        }
        fake_sender = Mock(return_value={"ok": True, "dry_run": True})

        result = run_once(
            response_builder=Mock(return_value=response),
            sender=fake_sender,
            dry_run=True,
            trigger_only=True,
        )

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "no_trigger")
        fake_sender.assert_not_called()

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
            "summary": "장중 테마 강약: 반도체 주도 / 암호화 약세 / 레짐 중립",
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

    def test_build_alert_text_includes_session_context_when_present(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        text = build_alert_text({
            "mode": "sector_strength",
            "summary": "장중 테마 강약: 우주 주도",
            "collected_at": "2026-05-07T21:10:00+00:00",
            "focus": [
                "장 분위기: 중립 / VIX 충격 없음",
                "세션: 토스 데이마켓/주간거래 / Toss base 대비 / source toss_wts_stock_prices",
                "강한 테마: 우주/항공우주 평균 +2.00% / 상승비율 80.0% / 주도 RKLB +4.00%",
                "약한 테마: 암호화/코인 관련주 평균 -2.00% / 상승비율 20.0% / 주도 COIN -1.00%",
                "오늘 먼저 볼 종목: RKLB +2.64%(우주/항공우주; 7.2, 토스 데이마켓/주간거래, Toss base 대비)",
                "로테이션 해석: 뚜렷한 세부테마 내부 로테이션 없음",
                "장 분위기: NASDAQ n/a / SPY +1.10% / SOXX +0.90% / BTCUSDT n/a / WTI n/a / VIX n/a / 세션 토스 데이마켓/주간거래 / 기준시각 2026-05-07T21:10:00+00:00",
            ],
            "next_actions": ["정규장 종가 기준이면 추격 금지"],
        })

        self.assertNotIn("- 세션:", text)
        self.assertNotIn("Toss base 대비", text)
        self.assertNotIn("source toss_wts_stock_prices", text)
        self.assertNotIn("- 벤치:", text)
        self.assertIn("RKLB +2.64%(우주/항공우주; 7.2)", text)
        self.assertNotIn("QQQ", text)
        self.assertNotIn("시장 레짐", text)



    def test_build_alert_text_surfaces_flow_proxy_line(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        text = build_alert_text({
            "mode": "sector_strength",
            "summary": "장중 테마 강약: 반도체 주도",
            "collected_at": "2026-04-30T13:35:00+00:00",
            "focus": [
                "장 분위기: 중립 / SPY 보합",
                "수급 proxy: 반도체 기관성 유입 의심 / 거래대금 .7B / 상승비율 80.0% / SPY 대비 +2.30% / 5m AMD +1.20%, NVDA +0.80% / VWAP 위 3종목",
                "강한 테마: 반도체 평균 +2.30% / 상승비율 80.0% / 거래대금 .7B / 주도 AMD +6.00%, NVDA +4.00%",
                "약한 테마: AI/빅테크/인프라 평균 -0.20% / 상승비율 40.0% / 주도 MSFT +0.10%",
                "테마별 대장주: • 반도체: AMD +6.00% 06.00 | RSI 64(+4), MACD 0.50/0.30 h+0.20(+0.05), Stochastic Slow 78/70(+8), BB 85%(+5) 상단근접",
                "로테이션 해석: 반도체 내부 CPU/서버/PC칩로 자금 이동",
            ],
            "next_actions": ["기관성 유입 의심은 거래대금/VWAP/상대강도 기반 proxy로만 보고 단정 금지"],
        })

        self.assertNotIn("- 수급:", text)
        self.assertNotIn("VWAP 위 3종목", text)
        self.assertNotIn("결론", text)
        self.assertIn("  · 주도주:\n    - AMD $6(+6.00%)", text)
        self.assertIn("    - NVDA +4.00%", text)
        self.assertNotIn("종목 체크", text)
        self.assertNotIn("4) 먼저 볼 종목", text)
        self.assertNotIn("테마별 대장주:", text)
        self.assertNotIn("단정 금지", text)
        self.assertLessEqual(len(text), SECTOR_ALERT_COMPACT_LIMIT)

if __name__ == "__main__":
    unittest.main()
