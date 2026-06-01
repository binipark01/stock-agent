import json
import tempfile
from pathlib import Path

from src.main import build_response, run_ingest, build_brief_from_db
from src.repository import get_connection, fetch_upcoming_earnings
from src.tossinvest_data import store_toss_index_snapshot, store_toss_news_items
from src.saveticker_data import store_saveticker_items

class NewsBriefModeCases:
            def test_saveticker_breaking_mode_returns_only_important_alerts(self) -> None:
                with tempfile.TemporaryDirectory() as tmpdir:
                    db_path = Path(tmpdir) / "stock_agent.db"
                    conn = get_connection(db_path)
                    store_saveticker_items(
                        conn,
                        [
                            {
                                "headline": "테슬라, 로보택시 생산 일정 앞당김",
                                "kind": "속보",
                                "published_text": "8분 전",
                                "tickers": ["TSLA"],
                                "popularity_text": "12.4K",
                                "source": "saveticker_api:SAVE:오선",
                                "collected_at": "2026-04-30T00:00:00+00:00",
                                "url": "https://www.saveticker.com/app/news/tsla",
                            },
                            {
                                "headline": "유럽 통신주 분기 실적 발표",
                                "kind": "정보",
                                "published_text": "6분 전",
                                "tickers": [],
                                "popularity_text": "1.0K",
                                "source": "saveticker_api:reuters",
                                "collected_at": "2026-04-30T00:01:00+00:00",
                                "url": "https://www.saveticker.com/app/news/eu",
                            },
                        ],
                    )
                    conn.commit()
                    conn.close()

                    payload = build_response(
                        json.dumps(
                            {
                                "mode": "saveticker_breaking",
                                "request": "SaveTicker 속보 중요한 것만 알려줘",
                                "symbols": ["TSLA"],
                                "watchlist": ["TSLA"],
                                "db_path": str(db_path),
                            },
                            ensure_ascii=False,
                        )
                    )

                    self.assertEqual(payload["mode"], "saveticker_breaking")
                    self.assertIn("중요 속보", payload["summary"])
                    self.assertTrue(any("테슬라" in item and "중요도" in item for item in payload["focus"]))
                    self.assertFalse(any("유럽 통신주" in item for item in payload["focus"]))
                    self.assertTrue(any("루머" in item or "검증" in item for item in payload["next_actions"]))

            def test_what_changed_mode_summarizes_latest_market_symbol_and_breaking_changes(self) -> None:
                with tempfile.TemporaryDirectory() as tmpdir:
                    db_path = Path(tmpdir) / "stock_agent.db"
                    run_ingest(["NVDA", "PLTR"], db_path=db_path)
                    conn = get_connection(db_path)
                    store_toss_index_snapshot(
                        conn,
                        {
                            "index_code": "COMP.NAI",
                            "index_name": "나스닥",
                            "collected_at": "2026-04-24T00:00:00+00:00",
                            "close": 24438.50,
                            "change_value": 219.06,
                            "change_pct": 1.12,
                            "volume": 6705087891.0,
                            "trading_value_text": "-",
                            "open": 24553.74,
                            "high": 24664.86,
                            "low": 24209.73,
                            "source": "tossinvest",
                            "note": "test",
                        },
                    )
                    store_toss_news_items(
                        conn,
                        [
                            {
                                "headline": "엔비디아, 데이터센터 투자 확대",
                                "source_name": "로이터",
                                "published_text": "35분 전",
                                "url": "https://www.tossinvest.com/feed/news?contentType=news&id=changed-1",
                                "source": "tossinvest_feed",
                                "collected_at": "2026-04-24T00:00:00+00:00",
                            }
                        ],
                    )
                    store_saveticker_items(
                        conn,
                        [
                            {
                                "headline": "팔란티어, 신규 정부 계약 확대",
                                "kind": "속보",
                                "published_text": "12분 전",
                                "tickers": ["PLTR"],
                                "popularity_text": "8.4K",
                                "source": "saveticker",
                                "collected_at": "2026-04-24T00:05:00+00:00",
                                "url": "https://www.saveticker.com/app/news?id=changed-breaking",
                            }
                        ],
                    )
                    conn.commit()
                    conn.close()

                    payload = build_response(
                        json.dumps(
                            {
                                "request": "NVDA PLTR 뭐가 달라졌어",
                                "symbols": ["NVDA", "PLTR"],
                                "db_path": str(db_path),
                            },
                            ensure_ascii=False,
                        )
                    )
                    self.assertEqual(payload["mode"], "what_changed")
                    self.assertTrue(any(item.startswith("시장 변화:") for item in payload["focus"]))
                    self.assertTrue(any(item.startswith("종목 변화:") for item in payload["focus"]))
                    self.assertTrue(any(item.startswith("속보 변화:") for item in payload["focus"]))
                    self.assertTrue(any(item.startswith("변화 결론:") for item in payload["focus"]))
                    self.assertTrue(any("나스닥" in item for item in payload["focus"]))
                    self.assertTrue(any("PLTR" in item for item in payload["focus"]))

            def test_overnight_recap_mode_summarizes_after_close_to_pre_market_changes(self) -> None:
                with tempfile.TemporaryDirectory() as tmpdir:
                    db_path = Path(tmpdir) / "stock_agent.db"
                    run_ingest(["NVDA", "PLTR"], db_path=db_path)
                    conn = get_connection(db_path)
                    store_toss_index_snapshot(
                        conn,
                        {
                            "index_code": "SPX.CBI",
                            "index_name": "S&P 500",
                            "collected_at": "2026-04-24T00:00:00+00:00",
                            "close": 7108.40,
                            "change_value": 29.50,
                            "change_pct": 0.41,
                            "volume": 12345.0,
                            "trading_value_text": "-",
                            "open": 7120.0,
                            "high": 7130.0,
                            "low": 7090.0,
                            "source": "tossinvest",
                            "note": "test",
                        },
                    )
                    store_toss_news_items(
                        conn,
                        [
                            {
                                "headline": "미국 증시, 장후 반도체 강세 지속",
                                "source_name": "로이터",
                                "published_text": "1시간 전",
                                "url": "https://www.tossinvest.com/feed/news?contentType=news&id=overnight-1",
                                "source": "tossinvest_feed",
                                "collected_at": "2026-04-24T00:00:00+00:00",
                            }
                        ],
                    )
                    store_saveticker_items(
                        conn,
                        [
                            {
                                "headline": "엔비디아, 주요 고객사 AI 서버 주문 확대",
                                "kind": "속보",
                                "published_text": "18분 전",
                                "tickers": ["NVDA"],
                                "popularity_text": "7.9K",
                                "source": "saveticker",
                                "collected_at": "2026-04-24T00:05:00+00:00",
                                "url": "https://www.saveticker.com/app/news?id=overnight-breaking",
                            }
                        ],
                    )
                    conn.commit()
                    conn.close()

                    payload = build_response(
                        json.dumps(
                            {
                                "request": "NVDA PLTR overnight recap 해줘",
                                "symbols": ["NVDA", "PLTR"],
                                "db_path": str(db_path),
                            },
                            ensure_ascii=False,
                        )
                    )
                    self.assertEqual(payload["mode"], "overnight_recap")
                    self.assertTrue(any(item.startswith("야간 시장:") for item in payload["focus"]))
                    self.assertTrue(any(item.startswith("야간 속보:") for item in payload["focus"]))
                    self.assertTrue(any(item.startswith("장전 체크:") for item in payload["focus"]))
                    self.assertTrue(any(item.startswith("야간 결론:") for item in payload["focus"]))
                    self.assertTrue(any("NVDA" in item for item in payload["focus"]))

            def test_why_symbol_mode_explains_why_symbol_matters_now(self) -> None:
                with tempfile.TemporaryDirectory() as tmpdir:
                    db_path = Path(tmpdir) / "stock_agent.db"
                    run_ingest(["NVDA"], db_path=db_path)
                    payload = build_response(
                        json.dumps(
                            {
                                "request": "왜 NVDA 봐야 해?",
                                "symbols": ["NVDA"],
                                "db_path": str(db_path),
                            },
                            ensure_ascii=False,
                        )
                    )
                    self.assertEqual(payload["mode"], "why_symbol")
                    self.assertTrue(any(item.startswith("핵심 이유:") for item in payload["focus"]))
                    self.assertTrue(any(item.startswith("뉴스 이유:") for item in payload["focus"]))
                    self.assertTrue(any(item.startswith("실적 이유:") for item in payload["focus"]))
                    self.assertTrue(any(item.startswith("차트 이유:") for item in payload["focus"]))
                    self.assertTrue(any(item.startswith("한줄 결론:") for item in payload["focus"]))

            def test_watchlist_weight_promotes_related_theme_without_portfolio(self) -> None:
                with tempfile.TemporaryDirectory() as tmpdir:
                    db_path = Path(tmpdir) / "stock_agent.db"
                    watchlist_path = Path(tmpdir) / "watchlist.json"
                    watchlist_path.write_text(
                        json.dumps(
                            {
                                "watchlist": ["PLTR", "GOOGL"],
                                "portfolio": [],
                            },
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
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
                    store_toss_news_items(
                        conn,
                        [
                            {
                                "headline": "팔란티어, 소프트웨어 비관론 여파 주가 7% 급락",
                                "source_name": "연합인포맥스",
                                "published_text": "3시간 전",
                                "url": "https://www.tossinvest.com/feed/news?contentType=news&id=pltr-watchlist",
                                "source": "tossinvest_feed",
                                "collected_at": "2026-04-24T00:00:00+00:00",
                            },
                            {
                                "headline": "미국 증시, 협상 기대에 상승",
                                "source_name": "로이터",
                                "published_text": "2시간 전",
                                "url": "https://www.tossinvest.com/feed/news?contentType=news&id=macro-watchlist",
                                "source": "tossinvest_feed",
                                "collected_at": "2026-04-24T00:10:00+00:00",
                            },
                        ],
                    )
                    store_saveticker_items(
                        conn,
                        [
                            {
                                "headline": "(카더라) 이란 협상 재개 기대",
                                "kind": "정보",
                                "published_text": "1시간 전",
                                "tickers": [],
                                "popularity_text": "5.1K",
                                "source": "saveticker",
                                "collected_at": "2026-04-24T00:30:00+00:00",
                                "url": "https://www.saveticker.com/app/news?id=watchlist-macro-1",
                            },
                            {
                                "headline": "백악관 협상 기대에 증시 반등",
                                "kind": "정보",
                                "published_text": "50분 전",
                                "tickers": [],
                                "popularity_text": "4.9K",
                                "source": "saveticker",
                                "collected_at": "2026-04-24T00:40:00+00:00",
                                "url": "https://www.saveticker.com/app/news?id=watchlist-macro-2",
                            },
                        ],
                    )
                    conn.commit()
                    conn.close()

                    payload = build_response(
                        json.dumps(
                            {
                                "mode": "brief",
                                "db_path": str(db_path),
                                "watchlist_path": str(watchlist_path),
                                "request": "미국장 브리핑 만들어줘",
                            },
                            ensure_ascii=False,
                        )
                    )

                    self.assertEqual(payload["symbols"], ["PLTR", "GOOGL"])
                    self.assertIn("오늘 테마는 소프트웨어(watchlist, 0.50), 매크로(general, 0.50)", payload["focus"][0])
                    self.assertIn("핵심 뉴스는 팔란티어, 소프트웨어 비관론 여파 주가 7% 급락 / 백악관 협상 기대에 증시 반등", payload["focus"][0])

            def test_headline_priority_prefers_related_news_across_sources(self) -> None:
                with tempfile.TemporaryDirectory() as tmpdir:
                    db_path = Path(tmpdir) / "stock_agent.db"
                    watchlist_path = Path(tmpdir) / "watchlist.json"
                    watchlist_path.write_text(
                        json.dumps(
                            {
                                "watchlist": ["GOOGL"],
                                "portfolio": [],
                            },
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
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
                    store_toss_news_items(
                        conn,
                        [
                            {
                                "headline": "미국 증시, 협상 기대에 상승",
                                "source_name": "로이터",
                                "published_text": "3시간 전",
                                "url": "https://www.tossinvest.com/feed/news?contentType=news&id=macro-priority",
                                "source": "tossinvest_feed",
                                "collected_at": "2026-04-24T00:00:00+00:00",
                            }
                        ],
                    )
                    store_saveticker_items(
                        conn,
                        [
                            {
                                "headline": "구글, 앤트로픽에 최대 400억 달러 투자 계획",
                                "kind": "속보",
                                "published_text": "2시간 전",
                                "tickers": ["GOOGL", "AVGO"],
                                "popularity_text": "6.7K",
                                "source": "saveticker",
                                "collected_at": "2026-04-24T00:10:00+00:00",
                                "url": "https://www.saveticker.com/app/news?id=priority-1",
                            }
                        ],
                    )
                    conn.commit()
                    conn.close()

                    payload = build_response(
                        json.dumps(
                            {
                                "mode": "brief",
                                "db_path": str(db_path),
                                "watchlist_path": str(watchlist_path),
                                "request": "미국장 브리핑 만들어줘",
                            },
                            ensure_ascii=False,
                        )
                    )

                    self.assertIn("핵심 뉴스는 구글, 앤트로픽에 최대 400억 달러 투자 계획 / 미국 증시, 협상 기대에 상승", payload["focus"][0])

            def test_market_summary_prioritizes_portfolio_breaking_headline_within_same_source(self) -> None:
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
                    store_toss_news_items(
                        conn,
                        [
                            {
                                "headline": "미국 증시, 협상 기대에 상승",
                                "source_name": "로이터",
                                "published_text": "2시간 전",
                                "url": "https://www.tossinvest.com/feed/news?contentType=news&id=portfolio-summary-macro",
                                "source": "tossinvest_feed",
                                "collected_at": "2026-04-24T00:00:00+00:00",
                            }
                        ],
                    )
                    store_saveticker_items(
                        conn,
                        [
                            {
                                "headline": "엔비디아·마이크로소프트·아마존, AI 클라우드 투자 확대",
                                "kind": "속보",
                                "published_text": "7분 전",
                                "tickers": ["NVDA", "MSFT", "AMZN"],
                                "popularity_text": "11.2K",
                                "source": "saveticker",
                                "collected_at": "2026-04-24T00:07:00+00:00",
                                "url": "https://www.saveticker.com/app/news?id=portfolio-summary-broad",
                            },
                            {
                                "headline": "팔란티어, 미 국방 데이터 계약 확대",
                                "kind": "속보",
                                "published_text": "11분 전",
                                "tickers": ["PLTR"],
                                "popularity_text": "8.4K",
                                "source": "saveticker",
                                "collected_at": "2026-04-24T00:11:00+00:00",
                                "url": "https://www.saveticker.com/app/news?id=portfolio-summary-pltr",
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

                    self.assertIn("핵심 뉴스는 팔란티어, 미 국방 데이터 계약 확대 / 미국 증시, 협상 기대에 상승", payload["focus"][0])
                    self.assertNotIn("핵심 뉴스는 엔비디아·마이크로소프트·아마존, AI 클라우드 투자 확대 / 미국 증시, 협상 기대에 상승", payload["focus"][0])
                    self.assertIn("혼합 소스 기준입니다.", payload["focus"][0])

            def test_market_summary_marks_wire_based_headlines_when_top_news_are_high_reliability(self) -> None:
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
                    store_toss_news_items(
                        conn,
                        [
                            {
                                "headline": "미국 증시, 협상 기대에 상승",
                                "source_name": "로이터",
                                "published_text": "20분 전",
                                "url": "https://www.tossinvest.com/feed/news?contentType=news&id=wire-1",
                                "source": "tossinvest_feed",
                                "collected_at": "2026-04-24T00:00:00+00:00",
                            },
                            {
                                "headline": "애플, 신형 칩 공급망 재점검",
                                "source_name": "블룸버그",
                                "published_text": "35분 전",
                                "url": "https://www.tossinvest.com/feed/news?contentType=news&id=wire-2",
                                "source": "tossinvest_feed",
                                "collected_at": "2026-04-24T00:05:00+00:00",
                            }
                        ],
                    )
                    conn.commit()
                    conn.close()

                    payload = build_response(
                        json.dumps(
                            {
                                "mode": "brief",
                                "symbols": ["AAPL"],
                                "db_path": str(db_path),
                                "request": "미국장 브리핑 만들어줘",
                            },
                            ensure_ascii=False,
                        )
                    )

                    self.assertIn("주요 통신 기준입니다.", payload["focus"][0])

            def test_brief_mode_prioritizes_fresh_breaking_news(self) -> None:
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
                    store_toss_news_items(
                        conn,
                        [
                            {
                                "headline": "엔비디아, 데이터센터 투자 확대",
                                "source_name": "로이터",
                                "published_text": "3시간 전",
                                "url": "https://www.tossinvest.com/feed/news?contentType=news&id=older",
                                "source": "tossinvest_feed",
                                "collected_at": "2026-04-24T00:00:00+00:00",
                            }
                        ],
                    )
                    store_saveticker_items(
                        conn,
                        [
                            {
                                "headline": "(카더라) 구글, 앤트로픽 추가 투자 검토",
                                "kind": "속보",
                                "published_text": "12분 전",
                                "tickers": ["GOOGL"],
                                "popularity_text": "7.2K",
                                "source": "saveticker",
                                "collected_at": "2026-04-24T00:05:00+00:00",
                                "url": "https://www.saveticker.com/app/news?id=fresh-breaking",
                            }
                        ],
                    )
                    conn.commit()
                    conn.close()

                    payload = build_response(
                        json.dumps(
                            {
                                "mode": "brief",
                                "symbols": ["NVDA", "GOOGL"],
                                "db_path": str(db_path),
                                "request": "미국장 브리핑 만들어줘",
                            },
                            ensure_ascii=False,
                        )
                    )
                    self.assertTrue(any(item.startswith("속보 우선:") for item in payload["focus"]))
                    breaking_line = next(item for item in payload["focus"] if item.startswith("속보 우선:"))
                    self.assertIn("[watchlist 관련][신속][신뢰도:낮음][루머 주의]", breaking_line)
                    self.assertIn("12분 전", breaking_line)
                    self.assertIn("구글, 앤트로픽 추가 투자 검토", breaking_line)
                    self.assertLess(payload["focus"].index(breaking_line), payload["focus"].index(next(item for item in payload["focus"] if item.startswith("차트 한줄:"))))

            def test_brief_mode_warns_when_source_specific_news_is_stale(self) -> None:
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
                    store_toss_news_items(
                        conn,
                        [
                            {
                                "headline": "미국 증시, 협상 기대에 상승",
                                "source_name": "로이터",
                                "published_text": "5시간 전",
                                "url": "https://www.tossinvest.com/feed/news?contentType=news&id=stale-toss",
                                "source": "tossinvest_feed",
                                "collected_at": "2026-04-24T00:00:00+00:00",
                            }
                        ],
                    )
                    store_saveticker_items(
                        conn,
                        [
                            {
                                "headline": "엔비디아, AI 서버 공급 확대",
                                "kind": "속보",
                                "published_text": "2시간 전",
                                "tickers": ["NVDA"],
                                "popularity_text": "6.1K",
                                "source": "saveticker",
                                "collected_at": "2026-04-24T00:30:00+00:00",
                                "url": "https://www.saveticker.com/app/news?id=stale-save",
                            }
                        ],
                    )
                    conn.commit()
                    conn.close()

                    payload = build_response(
                        json.dumps(
                            {
                                "mode": "brief",
                                "symbols": ["NVDA"],
                                "db_path": str(db_path),
                                "request": "미국장 브리핑 만들어줘",
                            },
                            ensure_ascii=False,
                        )
                    )
                    self.assertTrue(any(item.startswith("최신성 경고:") for item in payload["focus"]))
                    stale_line = next(item for item in payload["focus"] if item.startswith("최신성 경고:"))
                    self.assertIn("Toss 5시간 전", stale_line)
                    self.assertIn("SaveTicker 2시간 전", stale_line)

            def test_brief_mode_normalizes_absolute_timestamp_in_staleness_warning(self) -> None:
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
                    store_toss_news_items(
                        conn,
                        [
                            {
                                "headline": "미국 증시, 협상 기대에 상승",
                                "source_name": "로이터",
                                "published_text": "5시간 전",
                                "url": "https://www.tossinvest.com/feed/news?contentType=news&id=stale-absolute-toss",
                                "source": "tossinvest_feed",
                                "collected_at": "2026-04-24T00:00:00+00:00",
                            }
                        ],
                    )
                    store_saveticker_items(
                        conn,
                        [
                            {
                                "headline": "인텔 - 실적발표",
                                "kind": "속보",
                                "published_text": "2020. 01. 01. 00:00",
                                "tickers": ["INTC"],
                                "popularity_text": "2.1K",
                                "source": "saveticker",
                                "collected_at": "2026-04-24T00:30:00+00:00",
                                "url": "https://www.saveticker.com/app/news?id=stale-absolute-save",
                            }
                        ],
                    )
                    conn.commit()
                    conn.close()

                    payload = build_response(
                        json.dumps(
                            {
                                "mode": "brief",
                                "symbols": ["INTC"],
                                "db_path": str(db_path),
                                "request": "미국장 브리핑 만들어줘",
                            },
                            ensure_ascii=False,
                        )
                    )
                    stale_line = next(item for item in payload["focus"] if item.startswith("최신성 경고:"))
                    self.assertIn("Toss 5시간 전", stale_line)
                    self.assertIn("SaveTicker ", stale_line)
                    self.assertIn("전", stale_line)
                    self.assertNotIn("2020. 01. 01. 00:00", stale_line)
