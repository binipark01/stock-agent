import json
import tempfile
from pathlib import Path

from src.main import build_response, run_ingest, build_brief_from_db
from src.repository import get_connection, fetch_upcoming_earnings
from src.tossinvest_data import store_toss_index_snapshot, store_toss_news_items
from src.saveticker_data import store_saveticker_items

class PortfolioNewsModeCases:
            def test_brief_mode_adds_position_alert_for_portfolio_related_breaking_news(self) -> None:
                with tempfile.TemporaryDirectory() as tmpdir:
                    db_path = Path(tmpdir) / "stock_agent.db"
                    conn = get_connection(db_path)
                    store_toss_index_snapshot(
                        conn,
                        {
                            "index_code": "COMP.NAI",
                            "index_name": "나스닥",
                            "collected_at": "2026-04-24T00:00:00+00:00",
                            "close": 24438.50,
                            "change_value": -219.06,
                            "change_pct": -0.88,
                            "volume": 6705087891.0,
                            "trading_value_text": "-",
                            "open": 24553.74,
                            "high": 24664.86,
                            "low": 24209.73,
                            "source": "tossinvest",
                            "note": "test",
                        },
                    )
                    store_saveticker_items(
                        conn,
                        [
                            {
                                "headline": "팔란티어, 신규 정부 계약 확대",
                                "kind": "속보",
                                "published_text": "9분 전",
                                "tickers": ["PLTR"],
                                "popularity_text": "9.1K",
                                "source": "saveticker",
                                "collected_at": "2026-04-24T00:02:00+00:00",
                                "url": "https://www.saveticker.com/app/news?id=portfolio-breaking",
                            }
                        ],
                    )
                    conn.commit()
                    conn.close()

                    payload = build_response(
                        json.dumps(
                            {
                                "mode": "brief",
                                "symbols": ["PLTR", "NVDA"],
                                "portfolio": ["PLTR"],
                                "db_path": str(db_path),
                                "request": "미국장 브리핑 만들어줘",
                            },
                            ensure_ascii=False,
                        )
                    )
                    self.assertTrue(any(item.startswith("포지션 경고:") for item in payload["focus"]))
                    alert_line = next(item for item in payload["focus"] if item.startswith("포지션 경고:"))
                    self.assertIn("[초신속][신뢰도:낮음]", alert_line)
                    self.assertIn("PLTR", alert_line)
                    self.assertIn("9분 전", alert_line)
                    thesis_line = next(item for item in payload["focus"] if item.startswith("thesis break 이유:"))
                    self.assertIn("PLTR", thesis_line)
                    self.assertIn("기대 선반영", thesis_line)
                    self.assertLess(payload["focus"].index(alert_line), payload["focus"].index(thesis_line))
                    self.assertLess(payload["focus"].index(thesis_line), payload["focus"].index(next(item for item in payload["focus"] if item.startswith("차트 한줄:"))))

            def test_portfolio_relevance_prioritizes_mapped_news(self) -> None:
                with tempfile.TemporaryDirectory() as tmpdir:
                    db_path = Path(tmpdir) / "stock_agent.db"
                    conn = get_connection(db_path)
                    store_toss_news_items(
                        conn,
                        [
                            {
                                "headline": "팔란티어, 소프트웨어 비관론 여파 주가 7% 급락",
                                "source_name": "연합인포맥스",
                                "published_text": "3시간 전",
                                "url": "https://www.tossinvest.com/feed/news?contentType=news&id=pltr",
                                "source": "tossinvest_feed",
                                "collected_at": "2026-04-24T00:00:00+00:00",
                            },
                            {
                                "headline": "미국 IPO 쓰나미 온다…AI 열풍 속 뉴욕증시 경고등",
                                "source_name": "뉴스1",
                                "published_text": "23분 전",
                                "url": "https://www.tossinvest.com/feed/news?contentType=news&id=macro",
                                "source": "tossinvest_feed",
                                "collected_at": "2026-04-24T00:00:00+00:00",
                            },
                        ],
                    )
                    conn.commit()
                    conn.close()
                    payload = build_response(
                        json.dumps(
                            {
                                "mode": "brief",
                                "symbols": ["PLTR"],
                                "portfolio": ["PLTR"],
                                "db_path": str(db_path),
                                "request": "미국장 브리핑 만들어줘",
                            },
                            ensure_ascii=False,
                        )
                    )
                    news_lines = [item for item in payload["focus"] if "관련종목:" in item]
                    self.assertGreaterEqual(len(news_lines), 2)
                    self.assertIn("PLTR", news_lines[0])
