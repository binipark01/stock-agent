import tempfile
import unittest
from pathlib import Path

from src.repository import get_connection
from src.saveticker_data import (
    build_saveticker_brief,
    build_saveticker_important_breaking,
    map_saveticker_item,
    normalize_saveticker_api_item,
    parse_saveticker_news_markdown,
    select_important_saveticker_breaking,
    store_saveticker_items,
)


SAVETICKER_SAMPLE = """
# 뉴스 : 세이브티커

SAVE

·

속보

2시간 전

구글, 앤트로픽에 최대 400억 달러 투자 계획

#

GOOGL

#

AVGO

6.7K

SAVE

·

속보

11시간 전

일론 머스크, \"사이버캡 생산 시작\"

#

TSLA

30.1K

SAVE

·

정보

2026. 04. 23. 23:05

마이클 버리, \"마이크로소프트 신규 매수\"

#

MSFT

21.6K

SAVE

·

정보

2026. 04. 23. 17:08

(카더라) 이란 의회의장, 협상팀에서 사퇴

20.3K
"""


class SaveTickerParserTest(unittest.TestCase):
    def test_parse_saveticker_news_markdown(self) -> None:
        items = parse_saveticker_news_markdown(SAVETICKER_SAMPLE)
        self.assertGreaterEqual(len(items), 3)
        self.assertEqual(items[0]["kind"], "속보")
        self.assertIn("GOOGL", items[0]["tickers"])
        self.assertEqual(items[1]["tickers"], ["TSLA"])

    def test_normalize_saveticker_api_item_preserves_ohsun_and_tickers(self) -> None:
        item = normalize_saveticker_api_item(
            {
                "id": 115805,
                "title": "(카더라) 딥시크 V4 공개 후 중국 대형 IT 기업들, 화웨이 AI 칩 물량 확보 경쟁",
                "source": "로이터",
                "author_name": "오선",
                "created_at": "2026-04-29T09:00:00+09:00",
                "view_count": 1234,
                "tag_names": ["정보", "$NVDA", "$AMD"],
            }
        )
        self.assertEqual(item["kind"], "정보")
        self.assertEqual(item["published_text"], "2026-04-29T09:00:00+09:00")
        self.assertEqual(item["tickers"], ["NVDA", "AMD"])
        self.assertEqual(item["popularity_text"], "1234")
        self.assertEqual(item["source"], "saveticker_api:로이터:오선")
        self.assertEqual(item["url"], "https://www.saveticker.com/app/news/115805")

    def test_map_saveticker_item_marks_rumor_and_themes(self) -> None:
        mapped = map_saveticker_item(
            {
                "headline": "(카더라) 이란 의회의장, 협상팀에서 사퇴",
                "kind": "정보",
                "published_text": "2026. 04. 23. 17:08",
                "tickers": [],
                "popularity_text": "20.3K",
                "source": "saveticker",
                "collected_at": "2026-04-24T00:00:00+00:00",
            }
        )
        self.assertTrue(mapped["is_rumor"])
        self.assertIn("macro", mapped["mapped_themes"])

    def test_map_saveticker_item_expands_theme_keywords(self) -> None:
        mapped = map_saveticker_item(
            {
                "headline": "팔란티어, 국방 보안 클라우드 계약 확대",
                "kind": "속보",
                "published_text": "2시간 전",
                "tickers": ["PLTR"],
                "popularity_text": "8.1K",
                "source": "saveticker",
                "collected_at": "2026-04-24T00:00:00+00:00",
            }
        )
        self.assertIn("software", mapped["mapped_themes"])
        self.assertIn("security", mapped["mapped_themes"])
        self.assertIn("defense", mapped["mapped_themes"])

    def test_build_saveticker_brief_prioritizes_portfolio(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stock_agent.db"
            conn = get_connection(db_path)
            store_saveticker_items(
                conn,
                parse_saveticker_news_markdown(SAVETICKER_SAMPLE),
            )
            conn.commit()
            conn.close()

            text = build_saveticker_brief(db_path, portfolio_symbols={"TSLA"})
            self.assertIn("[SaveTicker 속보]", text)
            self.assertIn("TSLA", text)
            self.assertIn("구글, 앤트로픽", text)

    def test_select_important_breaking_prioritizes_portfolio_over_generic_macro(self) -> None:
        items = [
            {
                "headline": "백악관 협상 기대에 미국 증시 반등",
                "kind": "속보",
                "published_text": "5분 전",
                "tickers": [],
                "popularity_text": "42.0K",
                "source": "saveticker_api:reuters",
                "collected_at": "2026-04-30T00:00:00+00:00",
                "url": "https://www.saveticker.com/app/news/macro",
            },
            {
                "headline": "팔란티어, 국방 AI 클라우드 계약 확대",
                "kind": "정보",
                "published_text": "25분 전",
                "tickers": ["PLTR"],
                "popularity_text": "3.0K",
                "source": "saveticker_api:SAVE:오선",
                "collected_at": "2026-04-30T00:01:00+00:00",
                "url": "https://www.saveticker.com/app/news/pltr",
            },
        ]

        selected = select_important_saveticker_breaking(items, portfolio_symbols={"PLTR"}, watchlist_symbols=set(), limit=2)

        self.assertEqual(selected[0]["headline"], "팔란티어, 국방 AI 클라우드 계약 확대")
        self.assertGreater(selected[0]["importance_score"], selected[1]["importance_score"])
        self.assertEqual(selected[0]["relevance"], "portfolio")
        self.assertEqual(selected[0]["trust_label"], "보통")

    def test_select_important_breaking_keeps_rumor_but_labels_lower_trust(self) -> None:
        items = [
            {
                "headline": "(카더라) 엔비디아, 차세대 AI 칩 공급 차질 가능성",
                "kind": "속보",
                "published_text": "7분 전",
                "tickers": ["NVDA"],
                "popularity_text": "18.0K",
                "source": "saveticker_api:SAVE:오선",
                "collected_at": "2026-04-30T00:00:00+00:00",
                "url": "https://www.saveticker.com/app/news/rumor",
            }
        ]

        selected = select_important_saveticker_breaking(items, watchlist_symbols={"NVDA"}, limit=1, min_score=1)

        self.assertEqual(len(selected), 1)
        self.assertTrue(selected[0]["is_rumor"])
        self.assertEqual(selected[0]["trust_label"], "루머/검증필요")
        self.assertIn("추가 검증", selected[0]["action_hint"])

    def test_build_important_breaking_outputs_concise_actionable_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stock_agent.db"
            conn = get_connection(db_path)
            store_saveticker_items(
                conn,
                [
                    {
                        "headline": "엔비디아, AI 서버 주문 확대",
                        "kind": "속보",
                        "published_text": "12분 전",
                        "tickers": ["NVDA"],
                        "popularity_text": "9.2K",
                        "source": "saveticker_api:reuters",
                        "collected_at": "2026-04-30T00:00:00+00:00",
                        "url": "https://www.saveticker.com/app/news/nvda",
                    },
                    {
                        "headline": "유럽 통신주 분기 실적 발표",
                        "kind": "정보",
                        "published_text": "10분 전",
                        "tickers": [],
                        "popularity_text": "1.1K",
                        "source": "saveticker_api:reuters",
                        "collected_at": "2026-04-30T00:01:00+00:00",
                        "url": "https://www.saveticker.com/app/news/eu",
                    },
                ],
            )
            conn.commit()
            conn.close()

            text = build_saveticker_important_breaking(db_path, watchlist_symbols={"NVDA"}, limit=3)

            self.assertIn("[SaveTicker 중요 속보]", text)
            self.assertIn("중요도", text)
            self.assertIn("신뢰도: 보통", text)
            self.assertIn("관련: NVDA", text)
            self.assertIn("액션:", text)
            self.assertIn("엔비디아, AI 서버 주문 확대", text)
            self.assertNotIn("유럽 통신주", text)


if __name__ == "__main__":
    unittest.main()
