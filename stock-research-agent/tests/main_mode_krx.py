import json
import tempfile
from pathlib import Path

from src.main import build_response, run_ingest, build_brief_from_db
from src.repository import get_connection, fetch_upcoming_earnings
from src.tossinvest_data import store_toss_index_snapshot, store_toss_news_items
from src.saveticker_data import store_saveticker_items

class KrxModeCases:
        def test_krx_flow_snapshot_mode_uses_runtime_context_payload(self) -> None:
            krx_snapshot = {
                "mode": "krx_flow_snapshot",
                "source": "kiwoom",
                "collected_at": "2026-05-07T19:40:00+09:00",
                "symbols": ["005930"],
                "stocks": [
                    {
                        "code": "005930",
                        "name": "삼성전자",
                        "basic": {"current_price": 71500, "change_pct": 0.70, "tr": "ka10001"},
                        "execution_strength": {"latest": {"execution_strength": 152.3}, "tr": "ka10046"},
                        "intraday_investor_flow": {"net_buy_quantity": 180000, "tr": "ka10063"},
                        "program_intraday": {"latest": {"program_net_buy_amount": 5500}, "tr": "ka90008"},
                    }
                ],
            }
            payload = build_response(
                json.dumps(
                    {
                        "mode": "krx_flow_snapshot",
                        "symbols": ["삼성전자"],
                        "request": "삼성전자 수급 봐줘",
                    },
                    ensure_ascii=False,
                ),
                runtime_context={"krx_flow_snapshot": krx_snapshot},
            )

            self.assertEqual(payload["mode"], "krx_flow_snapshot")
            self.assertEqual(payload["symbols"], ["005930"])
            self.assertIn("Kiwoom", payload["summary"])
            joined = "\n".join(payload["focus"] + payload["next_actions"])
            self.assertIn("삼성전자(005930)", joined)
            self.assertIn("현재가 71,500", joined)
            self.assertIn("체결강도 152.3", joined)
            self.assertIn("ka10001", joined)
            self.assertIn("ka90008", joined)

        def test_krx_flow_rank_scan_mode_uses_runtime_context_payload(self) -> None:
            rank_scan = {
                "mode": "krx_flow_rank_scan",
                "source": "kiwoom",
                "collected_at": "2026-05-07T10:00:00+09:00",
                "sections": {
                    "trade_value": {
                        "label": "거래대금 상위",
                        "tr": "ka10032",
                        "status": "ok",
                        "rows": [{"rank": 1, "code": "005930", "name": "삼성전자", "trading_value": 8580000000}],
                    },
                    "program_net_buy": {
                        "label": "프로그램 순매수 상위",
                        "tr": "ka90003",
                        "status": "ok",
                        "rows": [{"rank": 1, "code": "005930", "name": "삼성전자", "program_net_buy_amount": 5500}],
                    },
                },
            }
            payload = build_response(
                json.dumps({"mode": "krx_flow_rank_scan", "request": "국장 수급 상위 보여줘"}, ensure_ascii=False),
                runtime_context={"krx_flow_rank_scan": rank_scan},
            )

            self.assertEqual(payload["mode"], "krx_flow_rank_scan")
            self.assertIn("수급/매매 랭킹", payload["summary"])
            joined = "\n".join(payload["focus"] + payload["next_actions"])
            self.assertIn("거래대금 상위", joined)
            self.assertIn("프로그램", joined)

        def test_krx_flow_rank_watch_mode_compares_runtime_rank_scans(self) -> None:
            previous = {
                "mode": "krx_flow_rank_scan",
                "source": "kiwoom",
                "collected_at": "2026-05-07T09:55:00+09:00",
                "sections": {
                    "trade_value": {"rows": [{"rank": 3, "code": "005930", "name": "삼성전자", "trading_value": 1000}]},
                    "investor_intraday": {"rows": []},
                    "foreign_institution": {"rows": []},
                    "program_net_buy": {"rows": []},
                },
            }
            current = {
                "mode": "krx_flow_rank_scan",
                "source": "kiwoom",
                "collected_at": "2026-05-07T10:00:00+09:00",
                "sections": {
                    "trade_value": {"rows": [{"rank": 1, "code": "005930", "name": "삼성전자", "trading_value": 8580000000}]},
                    "investor_intraday": {"rows": [{"rank": 1, "code": "000660", "name": "SK하이닉스", "net_buy_quantity": 95293}]},
                    "foreign_institution": {"rows": [{"rank": 1, "foreign_net_buy_code": "005930", "foreign_net_buy_name": "삼성전자", "foreign_net_buy_amount": 366597}]},
                    "program_net_buy": {"rows": [{"rank": 1, "code": "005930", "name": "삼성전자", "program_net_buy_amount": 5500}]},
                },
            }
            payload = build_response(
                json.dumps({"mode": "krx_flow_rank_watch", "request": "국장 수급 랭킹 5분마다 감시"}, ensure_ascii=False),
                runtime_context={"previous_krx_flow_rank_scan": previous, "current_krx_flow_rank_scan": current},
            )

            self.assertEqual(payload["mode"], "krx_flow_rank_watch")
            self.assertIn("랭킹 변화", payload["summary"])
            joined = "\n".join(payload["focus"])
            self.assertIn("signal_strengthening", joined)
            self.assertIn("new_candidate", joined)

        def test_krx_flow_watch_mode_compares_runtime_snapshots(self) -> None:
            previous = {
                "collected_at": "2026-05-07T09:55:00+09:00",
                "stocks": [{"code": "005930", "name": "삼성전자", "basic": {"current_price": 70000}, "execution_strength": {"latest": {"execution_strength": 101.0, "accumulated_trading_value": 1000000}}, "intraday_investor_flow": {"net_buy_amount": 100}, "program_intraday": {"latest": {"program_net_buy_amount": 1000}}}],
            }
            current = {
                "collected_at": "2026-05-07T10:00:00+09:00",
                "stocks": [{"code": "005930", "name": "삼성전자", "basic": {"current_price": 71500}, "execution_strength": {"latest": {"execution_strength": 152.3, "accumulated_trading_value": 8580000000}}, "intraday_investor_flow": {"net_buy_amount": 12500}, "program_intraday": {"latest": {"program_net_buy_amount": 5500}}}],
            }
            payload = build_response(
                json.dumps({"mode": "krx_flow_watch", "request": "삼성전자 5분마다 수급 확인"}, ensure_ascii=False),
                runtime_context={"previous_krx_flow_snapshot": previous, "current_krx_flow_snapshot": current},
            )

            self.assertEqual(payload["mode"], "krx_flow_watch")
            self.assertIn("변화", payload["summary"])
            self.assertIn("program_net_buy_acceleration", "\n".join(payload["focus"]))

        def test_krx_session_flow_watch_mode_uses_runtime_session_snapshots(self) -> None:
            snapshots = [
                {
                    "session": "regular",
                    "collected_at": "2026-05-08T15:20:00+09:00",
                    "env": "mock",
                    "source": "kiwoom",
                    "stocks": [{"code": "005380", "name": "현대차", "price": 613000, "change_pct": 7.17, "foreign_net_buy": 523820, "institution_net_buy": 439195, "program_net_buy": 462230, "volume": 5020568}],
                },
                {
                    "session": "nxt",
                    "collected_at": "2026-05-08T18:10:00+09:00",
                    "env": "mock",
                    "source": "nxt_quote+latest_kiwoom_flow",
                    "stocks": [{"code": "005380", "name": "현대차", "price": 620000, "change_pct": 8.39, "foreign_net_buy": 610000, "institution_net_buy": 470000, "program_net_buy": 540000, "volume": 5520000}],
                },
            ]
            payload = build_response(
                json.dumps({"mode": "krx_session_flow_watch", "request": "NXT까지 수급 감시"}, ensure_ascii=False),
                runtime_context={"krx_session_flow_snapshots": snapshots},
            )

            self.assertEqual(payload["mode"], "krx_session_flow_watch")
            self.assertIn("수급 변화", payload["summary"])
            joined = "\n".join(payload["focus"] + payload["next_actions"])
            self.assertIn("NXT", joined)
            self.assertIn("session_continuation", joined)
            self.assertIn("가격/거래량 변화 감시 중심", joined)

        def test_krx_symbol_brief_mode_uses_runtime_template_report(self) -> None:
            report = {
                "mode": "krx_symbol_brief",
                "symbol": "005380",
                "name": "현대차",
                "source": {"flow_env": "mock", "flow_base_url": "https://mockapi.kiwoom.com"},
                "collected_at": "2026-05-08T15:31:00+09:00",
                "supply_signal": "동반순매수",
                "price_pct": 7.17,
                "flow_snapshot": {
                    "requested_date": "20260508",
                    "data_dates": {"ka10009": "20260508"},
                    "is_today_confirmed": True,
                    "institution_net_buy_qty": 439195,
                    "foreign_net_buy_qty": 523820,
                    "program_net_buy_qty": 462230,
                    "warnings": [],
                },
                "naver_deal_trend": {
                    "bizdate": "20260508",
                    "closePrice": "613,000",
                    "compareToPreviousClosePrice": "41,000",
                    "accumulatedTradingVolume": "5,020,568",
                    "organPureBuyQuant": "+439,195",
                    "foreignerPureBuyQuant": "+309,580",
                    "individualPureBuyQuant": "-745,834",
                },
                "news_items": [{"title": "현대차그룹 급등", "source": "YTN", "datetime": "202605082245"}],
                "next_actions": ["수급은 좋지만 상승폭 확인"],
            }
            payload = build_response(
                json.dumps({"request": "현대차 어때", "symbols": ["005380"], "mode": "krx_symbol_brief"}, ensure_ascii=False),
                runtime_context={"krx_symbol_supply_news_report": report},
            )
            text = "\n".join([payload["summary"], *payload["focus"]])
            self.assertEqual("krx_symbol_brief", payload["mode"])
            self.assertIn("현대차(005380) 수급+뉴스", text)
            self.assertIn("기관 +439,195주", text)
            self.assertIn("현대차그룹 급등", text)

        def test_krx_condition_scan_mode_uses_runtime_universe(self):
            payload = build_response(
                json.dumps({"request": "국장 검색식 여러개", "mode": "krx_condition_scan"}, ensure_ascii=False),
                runtime_context={
                    "krx_condition_universe": [
                        {
                            "code": "005380", "name": "현대차", "change_pct": 7.17, "trade_value_rank": 5,
                            "close_position_pct": 88, "theme_strength_score": 3, "theme_leader_rank": 1,
                            "foreign_net_buy": 523820, "institution_net_buy": 439195, "program_net_buy": 462230,
                            "news_momentum": 2, "is_management_stock": False, "is_investment_warning": False,
                        },
                        {
                            "code": "000660", "name": "SK하이닉스", "change_pct": 2.8, "trade_value_rank": 3,
                            "close_position_pct": 81, "foreign_net_buy": -980000, "program_net_buy": -760000,
                            "price_up_flow_divergence": True, "is_management_stock": False, "is_investment_warning": False,
                        },
                    ],
                    "collected_at": "t",
                },
            )
            text = "\n".join([payload["summary"], *payload["focus"], *payload.get("next_actions", [])])
            self.assertEqual("krx_condition_scan", payload["mode"])
            self.assertIn("국장 검색식", payload["summary"])
            self.assertIn("만쥬식 종가배팅", text)
            self.assertIn("현대차(005380)", text)
            self.assertIn("위험제외", text)
