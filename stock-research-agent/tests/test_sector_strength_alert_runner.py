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

    def test_build_alert_text_uses_readable_six_part_telegram_template(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        payload = {
            "mode": "sector_strength",
            "summary": "장중 테마 강약: 우주/항공우주 주도 / 암호화 약세 / 장 분위기 중립",
            "collected_at": "2026-05-07T13:35:00+00:00",
            "focus": [
                "장 분위기: 중립 / VIX/오일/금리/DXY 뚜렷한 충격 없음",
                "강한 테마: 우주/항공우주 평균 +2.00% / 상승비율 80.0% / 주도 RKLB +4.00% | 반도체/AI칩 평균 +1.20% / 상승비율 66.7% / 주도 MU +3.10%",
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
        for heading in ("1) 장 분위기", "2) 강한 테마", "3) 약한 테마", "4) 주도 종목", "5) 로테이션", "6) 매매 관점", "한줄 판단:"):
            self.assertIn(heading, text)
        self.assertNotIn("[Sector Strength Alert]", text)
        self.assertNotIn("[액션]", text)
        self.assertIn("RKLB", text)
        self.assertIn("RSI 64(+5): 50선 위에서 재가속", text)
        self.assertIn("MACD 0.72/0.41 hist +0.31(+0.09): 신호선 위·히스토그램 확대", text)
        self.assertIn("Stoch 88/82(+4): 과열권 K>D 유지", text)
        self.assertIn("구름 위 +3.3%, 전환선>기준선", text)
        self.assertIn("BB 92%(+8) 상단권: 상단 확장", text)
        self.assertIn("종합: 추세·모멘텀 개선 중", text)
        self.assertIn("NASDAQ", text)
        self.assertIn("고베타", text)
        self.assertIn("- 상태: 중립", text)
        self.assertIn("- 벤치: NASDAQ +0.10% / SPY +0.00% / SOXX +0.20% / BTCUSDT +0.30% / WTI -0.10% / VIX -0.20%", text)
        self.assertIn("• RKLB +4.00%(우주/항공우주)", text)
        self.assertIn("  · RSI 64(+5): 50선 위에서 재가속", text)
        self.assertIn("  · MACD 0.72/0.41 hist +0.31(+0.09): 신호선 위·히스토그램 확대", text)
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

        self.assertIn("1) 장 분위기\n- 상태: 중립\n- 벤치:", text)
        self.assertIn("4) 주도 종목\n• RKLB +4.00%(우주/항공우주)", text)
        self.assertIn("\n  · RSI 64(+5): 50선 위에서 재가속", text)
        self.assertIn("\n  · MACD 0.72/0.41 hist +0.31(+0.09): 신호선 위·히스토그램 확대", text)
        self.assertIn("\n  · Stoch 88/82(+4): 과열권 K>D 유지", text)
        self.assertIn("\n  · 구름 위 +3.3%, 전환선>기준선", text)
        self.assertIn("\n  · BB 92%(+8) 상단권", text)
        self.assertIn("\n  · 종합: 추세·모멘텀 개선 중", text)
        self.assertIn("5) 로테이션\n• 우주 내부 발사체로 자금 이동\n• 위성 약세", text)
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

        self.assertIn("4) 주도 종목", text)
        self.assertIn("5) 로테이션", text)
        self.assertIn("\n• 우주 내부 발사체로 자금 이동", text)
        self.assertIn("6) 매매 관점", text)
        self.assertIn("한줄 판단:", text)
        self.assertIn("M1", text)
        self.assertIn("종합:", text)
        self.assertNotIn("[truncated]", text)
        self.assertLessEqual(len(text), SECTOR_ALERT_COMPACT_LIMIT)

    def test_build_alert_text_keeps_movers_and_etf_when_rotation_lines_expand_focus(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        payload = {
            "summary": "장중 테마 강약: 반도체/AI칩 > 메모리/스토리지 주도 / 반도체/AI칩 > AI 가속기/GPU 약세 / 장 분위기 중립",
            "focus": [
                "장 분위기: 중립 / VIX/오일/금리/DXY 뚜렷한 충격 없음",
                "강한 테마: 반도체/AI칩 평균 +2.00% / 상승비율 70.0% / 주도 MU +6.00%",
                "약한 테마: 암호화/코인 관련주 평균 -1.00% / 상승비율 30.0% / 주도 COIN -1.00%",
                "강한 세부테마: 반도체/AI칩 > 메모리/스토리지 평균 +5.33% / 상승비율 100.0% / 주도 MU +6.00%",
                "약한 세부테마: 반도체/AI칩 > AI 가속기/GPU 평균 -3.00% / 상승비율 0.0% / 주도 NVDA -3.00%",
                "로테이션 해석: 반도체/AI칩 내부 메모리/스토리지로 자금 이동 / AI 가속기/GPU 약세(강세 MU +6.00% vs 약세 NVDA -3.00%)",
                "오늘 먼저 볼 종목: MU +6.00%(메모리/스토리지) | SNDK +6.00%(메모리/스토리지)",
                "ETF 시장 참고: 강세 기술 XLK +1.00% / 약세 유틸리티 XLU -1.00%",
                "장 분위기: NASDAQ +0.10% / SPY +0.00% / SOXX +0.20% / BTCUSDT +0.30% / WTI -0.10% / VIX -0.20% / 기준시각 2026-04-30T13:35:00+00:00",
            ],
            "next_actions": ["메모리/스토리지 추격은 AI 가속기/GPU 회복 전까지 눌림/분할로 제한"],
        }

        text = build_alert_text(payload)

        self.assertIn("5) 로테이션", text)
        self.assertIn("4) 주도 종목", text)
        self.assertIn("ETF 시장 참고", text)
        self.assertIn("1) 장 분위기", text)
        self.assertIn("• 반도체/AI칩 내부 메모리/스토리지로 자금 이동", text)
        self.assertIn("• AI 가속기/GPU 약세", text)
        self.assertNotIn("\n• 반도체\n• AI칩", text)
        self.assertNotIn("QQQ", text)
        self.assertNotIn("[truncated]", text)
        self.assertLessEqual(len(text), SECTOR_ALERT_COMPACT_LIMIT)


    def test_build_alert_text_surfaces_intraday_risk_spikes(self) -> None:
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

        self.assertIn("1) 장 분위기", text)
        self.assertIn("- 리스크: VIX 5m +0.88pt(+5.00%) / WTI 15m +1.20%", text)
        self.assertIn("NASDAQ 5m -0.50%", text)
        self.assertIn("6) 매매 관점", text)
        self.assertIn("VIX/WTI 분봉 리스크 급등", text)
        self.assertIn("추격보다 VWAP 눌림 대기", text)
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
                "테마별 대장주: 우주/항공우주: RKLB +10.00% 가격 110, 정규장, 주도 | 반도체/AI칩: MU +9.00% 가격 109, 정규장, 주도",
                "로테이션 해석: 우주 내부 발사체로 자금 이동 / 위성 약세",
                "장 분위기: NASDAQ +0.10% / SPY +0.00% / SOXX +0.20% / BTCUSDT +0.30% / WTI -0.10% / VIX -0.20% / 기준시각 2026-05-08T13:35:00+00:00",
            ],
            "next_actions": ["추격보다 눌림 확인"],
        }

        text = build_alert_text(payload)

        self.assertIn("전일종가 대비 현재 강세", text)
        self.assertIn("기준: 전일 정규장 종가 대비 현재가 / Yahoo chart 1m", text)
        self.assertIn("RKLB +10.00%", text)
        self.assertIn("MU +9.00%", text)
        self.assertIn("반도체: MU", text)
        self.assertNotIn("AI: MU", text)
        for heading in ("5) 로테이션", "6) 매매 관점", "한줄 판단:"):
            self.assertIn(heading, text)
        self.assertLessEqual(len(text), SECTOR_ALERT_COMPACT_LIMIT)

    def test_build_alert_text_compacts_verbose_theme_leaders_without_cutting_sections(self) -> None:
        from scripts.run_sector_strength_alerts import build_alert_text

        tech = " — RSI 64(+5): 50선 위에서 재가속; MACD 0.72/0.41 h+0.31(+0.09): 신호선 위·히스토그램 확대; 스토캐스틱 Slow 88/82(+4): 과열권 K>D 유지; BB 92%(+8) 상단권: 상단 확장; 종합: 모멘텀 개선 중"
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

        for heading in ("4) 주도 종목", "5) 로테이션", "6) 매매 관점", "한줄 판단:"):
            self.assertIn(heading, text)
        self.assertIn("AAA1", text)
        self.assertIn("AAA2", text)
        self.assertIn("전일종가 대비 현재 강세", text)
        self.assertIn("전일 정규장 종가 대비 현재가", text)
        self.assertIn("스토캐스틱 Slow", text)
        self.assertGreaterEqual(text.count("스토캐스틱 Slow"), 2)
        self.assertNotIn("[truncated]", text)
        self.assertGreater(len(text), 1200)
        self.assertLessEqual(len(text), SECTOR_ALERT_COMPACT_LIMIT)

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

        self.assertIn("- 세션: 토스 데이마켓/주간거래 / Toss base 대비 / source toss_wts_stock_prices", text)
        self.assertIn("RKLB +2.64%(우주/항공우주; 7.2, 토스 데이마켓/주간거래, Toss base 대비)", text)
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
                "수급 proxy: 반도체/AI칩 기관성 유입 의심 / 거래대금 .7B / 상승비율 80.0% / SPY 대비 +2.30% / 5m AMD +1.20%, NVDA +0.80% / VWAP 위 3종목",
                "강한 테마: 반도체/AI칩 평균 +2.30% / 상승비율 80.0% / 거래대금 .7B / 주도 AMD +6.00%, NVDA +4.00%",
                "약한 테마: AI/빅테크/인프라 평균 -0.20% / 상승비율 40.0% / 주도 MSFT +0.10%",
                "테마별 대장주: • 반도체: AMD +6.00% 06.00 | RSI 64(+4), MACD 0.50/0.30 h+0.20(+0.05), 스토캐스틱 Slow 78/70(+8), BB 85%(+5) 상단근접",
                "로테이션 해석: 반도체/AI칩 내부 CPU/서버/PC칩로 자금 이동",
            ],
            "next_actions": ["기관성 유입 의심은 거래대금/VWAP/상대강도 기반 proxy로만 보고 단정 금지"],
        })

        self.assertIn("- 수급: 반도체/AI칩 기관성 유입 의심", text)
        self.assertIn("VWAP 위 3종목", text)
        self.assertIn("6) 매매 관점", text)
        self.assertIn("단정 금지", text)
        self.assertLessEqual(len(text), SECTOR_ALERT_COMPACT_LIMIT)

if __name__ == "__main__":
    unittest.main()
