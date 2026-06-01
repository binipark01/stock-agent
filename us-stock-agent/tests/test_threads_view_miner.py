import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from src.main import build_response
from src.threads_view_miner import (
    analyze_threads_post,
    build_threads_slow_state,
    build_threads_view_scan_report,
    extract_threads_posts_from_markdown,
    load_threads_slow_state,
    save_threads_slow_state,
    save_threads_view_scan_artifacts,
)


class ThreadsViewMinerTest(unittest.TestCase):
    def test_extracts_public_threads_post_snippets_from_profile_markdown(self) -> None:
        markdown = """
장투대장(튽) (@jtdj_official2) on Threads

[05/05/26](https://www.threads.com/@jtdj_official2/post/ABC123)
원익홀딩스(030530). 우하향 마치고 추세 전환 초입.
32,300원대 손익비 타점. 우상향 상단 돌파 기대.

[05/05/26](https://www.threads.com/@jtdj_official2/post/ABC123)
중복 링크는 버려야 함.

[05/04/26](https://www.threads.com/@jtdj_official2/post/DEF456)
후성(093370) 장초 매수세. 14,050원대 지지가 있고 지키면 15층 중반 시도.
"""
        account = {"handle": "jtdj_official2", "display_name": "장투대장(튽)", "category": "korea_stocks", "priority": "high"}

        posts = extract_threads_posts_from_markdown(markdown, account, max_posts=10)

        self.assertEqual([post["post_id"] for post in posts], ["ABC123", "DEF456"])
        self.assertIn("원익홀딩스", posts[0]["text"])
        self.assertEqual(posts[0]["published_hint"], "05/05/26")
        self.assertEqual(posts[1]["author_handle"], "jtdj_official2")

    def test_analyzes_krx_chart_setup_with_levels_direction_and_validation_rules(self) -> None:
        post = {
            "author_handle": "jtdj_official2",
            "author_name": "장투대장(튽)",
            "category": "korea_stocks",
            "priority": "high",
            "post_url": "https://www.threads.com/@jtdj_official2/post/ABC123",
            "post_id": "ABC123",
            "text": "원익홀딩스(030530). 우하향 마치고 추세 전환 초입. 32,300원대 손익비 타점. 지지 지키면 우상향 상단 돌파 기대.",
        }

        claim = analyze_threads_post(post)

        self.assertEqual(claim["symbols"], ["030530.KQ"])
        self.assertEqual(claim["direction"], "bullish")
        self.assertEqual(claim["evidence_type"], "chart")
        self.assertIn("KRX", claim["themes"])
        self.assertIn(32300, claim["key_levels_krw"])
        self.assertTrue(claim["requires_price_validation"])
        self.assertGreaterEqual(claim["relevance_score"], 80)

    def test_builds_scan_report_from_seed_accounts_and_runtime_markdown_without_network(self) -> None:
        accounts = [
            {"handle": "jtdj_official2", "display_name": "장투대장(튽)", "category": "korea_stocks", "priority": "high"},
            {"handle": "bullish_bee", "display_name": "양봉업자", "category": "trader", "priority": "high"},
        ]
        markdown_by_handle = {
            "jtdj_official2": """
[05/05/26](https://www.threads.com/@jtdj_official2/post/ABC123)
원익홀딩스(030530). 우하향 마치고 추세 전환 초입. 32,300원대 손익비 타점.
""",
            "bullish_bee": """
[05/05/26](https://www.threads.com/@bullish_bee/post/BEE123)
SOXX 아직 숏각 아님. 반도체 내부 주도주 순환이 살아있고 조정 나오면 1순위.
""",
        }

        report = build_threads_view_scan_report(
            accounts=accounts,
            profile_markdown_by_handle=markdown_by_handle,
            max_accounts=0,
            max_posts_per_account=5,
            fetch_live=False,
        )

        self.assertEqual(report["account_count"], 2)
        self.assertEqual(report["post_count"], 2)
        self.assertEqual(report["actionable_count"], 2)
        self.assertEqual(report["symbol_clusters"][0]["symbol"], "030530.KQ")
        self.assertTrue(any("@jtdj_official2" in line and "030530.KQ" in line for line in report["focus_lines"]))
        self.assertTrue(any("테마 클러스터" in line and "semiconductors" in line for line in report["focus_lines"]))

    def test_main_threads_view_scan_mode_returns_structured_data(self) -> None:
        request = json.dumps({"request": "내 스레더들 올라온 글 싹 분석", "mode": "threads_view_scan"}, ensure_ascii=False)
        payload = build_response(
            request,
            runtime_context={
                "threads_accounts": [
                    {"handle": "bullish_bee", "display_name": "양봉업자", "category": "trader", "priority": "high"}
                ],
                "threads_profile_markdown": {
                    "bullish_bee": """
[05/05/26](https://www.threads.com/@bullish_bee/post/BEE123)
SNDK 급락하면 반도체도 조심. SOXX는 조정 나오면 1순위.
"""
                },
                "threads_fetch_live": False,
                "threads_delay_seconds": 0.5,
                "threads_cache_ttl_seconds": 86400,
            },
        )

        self.assertEqual(payload["mode"], "threads_view_scan")
        self.assertIn("Threads view scan", payload["summary"])
        self.assertEqual(payload["data"]["threads_view_scan"]["claims"][0]["author_handle"], "bullish_bee")
        self.assertEqual(payload["data"]["threads_view_scan"]["delay_seconds"], 0.5)
        self.assertIn("threads_view_scan", payload["features"])

    def test_main_threads_view_scan_can_save_artifacts_and_slow_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "data"
            slow_state_path = Path(tmpdir) / "cache" / "slow_state.json"
            request = json.dumps(
                {
                    "request": "내 스레더들 분석",
                    "mode": "threads_view_scan",
                    "threads_accounts": [
                        {"handle": "first", "display_name": "first", "category": "trader", "priority": "high"},
                        {"handle": "second", "display_name": "second", "category": "trader", "priority": "high"},
                    ],
                    "threads_profile_markdown": {
                        "first": "[05/06/26](https://www.threads.com/@first/post/FIRST1)\\nPLTR 돌파",
                        "second": "[05/06/26](https://www.threads.com/@second/post/SECOND1)\\nSOXX 반도체 돌파",
                    },
                    "fetch_live": False,
                    "account_offset": 20,
                    "max_accounts": 2,
                    "save_artifacts": True,
                    "save_slow_state": True,
                    "output_dir": str(output_dir),
                    "slow_state_path": str(slow_state_path),
                    "date_label": "unit-slow-batch",
                    "accounts_total": 85,
                },
                ensure_ascii=False,
            )
            payload = build_response(request, explicit_mode="threads_view_scan")
            state = json.loads(slow_state_path.read_text(encoding="utf-8"))
            scan = payload["data"]["threads_view_scan"]

        self.assertTrue(Path(scan["artifact_paths"]["json"]).name.endswith("unit-slow-batch.json"))
        self.assertEqual(scan["slow_state_path"], str(slow_state_path))
        self.assertEqual(state["next_offset"], 22)
        self.assertEqual(state["last_batch"]["accounts"], ["first", "second"])
        self.assertEqual(state["accounts_total"], 85)

    def test_saves_scan_artifacts_as_json_and_markdown(self) -> None:
        report = {
            "generated_at": "2026-05-06T12:00:00+00:00",
            "summary": "Threads view scan: 1계정 / 1글 / actionable 1건",
            "focus_lines": ["1) 030530.KQ bullish @jtdj_official2 / 원익홀딩스 셋업"],
            "next_actions": ["가격 검증"],
            "claims": [{"author_handle": "jtdj_official2", "symbols": ["030530.KQ"], "claim_text": "원익홀딩스 셋업"}],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = save_threads_view_scan_artifacts(report, output_dir=Path(tmpdir), date_label="2026-05-06")
            json_payload = json.loads(paths["json"].read_text(encoding="utf-8"))
            markdown = paths["markdown"].read_text(encoding="utf-8")

        self.assertEqual(json_payload["summary"], report["summary"])
        self.assertIn("Threads View Scan", markdown)
        self.assertIn("030530.KQ", markdown)
    def test_slow_scan_uses_cache_and_delay_between_live_fetches(self) -> None:
        accounts = [
            {"handle": "bullish_bee", "display_name": "양봉업자", "category": "trader", "priority": "high"},
            {"handle": "jtdj_official2", "display_name": "장투대장", "category": "korea_stocks", "priority": "high"},
        ]
        fetched: list[str] = []
        slept: list[float] = []

        def fake_fetcher(handle: str, timeout: int = 30) -> str:
            fetched.append(handle)
            return f"[05/06/26](https://www.threads.com/@{handle}/post/POST{len(fetched)})\nSOXX 반도체 돌파"

        with tempfile.TemporaryDirectory() as tmpdir:
            report = build_threads_view_scan_report(
                accounts=accounts,
                max_posts_per_account=2,
                fetch_live=True,
                cache_dir=Path(tmpdir),
                cache_ttl_seconds=3600,
                delay_seconds=0.25,
                fetcher=fake_fetcher,
                sleeper=slept.append,
            )
            cache_files = sorted(path.name for path in Path(tmpdir).glob("*.md"))

        self.assertEqual(fetched, ["bullish_bee", "jtdj_official2"])
        self.assertEqual(slept, [0.25])
        self.assertEqual(cache_files, ["bullish_bee.md", "jtdj_official2.md"])
        self.assertEqual(report["cache_hits"], 0)
        self.assertEqual(report["live_fetch_count"], 2)
        self.assertFalse(report["stopped_early"])

    def test_slow_scan_reuses_fresh_cache_without_fetching(self) -> None:
        accounts = [{"handle": "bullish_bee", "display_name": "양봉업자", "category": "trader", "priority": "high"}]

        def forbidden_fetcher(handle: str, timeout: int = 30) -> str:
            raise AssertionError("fresh cache should avoid live fetch")

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "bullish_bee.md"
            cache_path.write_text(
                "[05/06/26](https://www.threads.com/@bullish_bee/post/BEE123)\nSOXX 반도체 돌파",
                encoding="utf-8",
            )
            report = build_threads_view_scan_report(
                accounts=accounts,
                fetch_live=True,
                cache_dir=Path(tmpdir),
                cache_ttl_seconds=3600,
                fetcher=forbidden_fetcher,
            )

        self.assertEqual(report["cache_hits"], 1)
        self.assertEqual(report["live_fetch_count"], 0)
        self.assertEqual(report["post_count"], 1)

    def test_slow_scan_can_run_small_offset_batches(self) -> None:
        accounts = [
            {"handle": "first", "display_name": "first", "category": "trader", "priority": "high"},
            {"handle": "second", "display_name": "second", "category": "trader", "priority": "high"},
            {"handle": "third", "display_name": "third", "category": "trader", "priority": "high"},
        ]
        markdown_by_handle = {
            "second": "[05/06/26](https://www.threads.com/@second/post/SECOND1)\nPLTR 실적 좋고 돌파",
        }

        report = build_threads_view_scan_report(
            accounts=accounts,
            profile_markdown_by_handle=markdown_by_handle,
            account_offset=1,
            max_accounts=1,
            fetch_live=False,
        )

        self.assertEqual(report["account_offset"], 1)
        self.assertEqual([account["handle"] for account in report["accounts"]], ["second"])
        self.assertEqual(report["post_count"], 1)

    def test_slow_scan_stops_after_rate_limit_threshold_and_records_skipped_accounts(self) -> None:
        accounts = [
            {"handle": "first", "display_name": "first", "category": "trader", "priority": "high"},
            {"handle": "second", "display_name": "second", "category": "trader", "priority": "high"},
        ]

        def rate_limited_fetcher(handle: str, timeout: int = 30) -> str:
            raise urllib.error.HTTPError(
                url=f"https://example.com/{handle}",
                code=429,
                msg="Too Many Requests",
                hdrs=None,
                fp=None,
            )

        report = build_threads_view_scan_report(
            accounts=accounts,
            fetch_live=True,
            fetcher=rate_limited_fetcher,
            max_consecutive_rate_limits=1,
        )

        self.assertTrue(report["stopped_early"])
        self.assertEqual(report["stop_reason"], "rate_limited")
        self.assertEqual(report["skipped_accounts"], ["second"])
        self.assertEqual(report["fetch_errors"][0]["status"], "429")

    def test_slow_state_records_next_offset_and_last_batch_for_resume(self) -> None:
        accounts = [
            {"handle": "first", "display_name": "first", "category": "trader", "priority": "high"},
            {"handle": "second", "display_name": "second", "category": "trader", "priority": "high"},
        ]
        report = build_threads_view_scan_report(
            accounts=accounts,
            profile_markdown_by_handle={
                "first": "[05/06/26](https://www.threads.com/@first/post/FIRST1)\nPLTR 돌파",
                "second": "[05/06/26](https://www.threads.com/@second/post/SECOND1)\nSOXX 반도체 돌파",
            },
            account_offset=7,
            max_accounts=2,
            fetch_live=False,
            cache_ttl_seconds=21600,
            delay_seconds=15,
            account_source="seed_all",
        )
        report["artifact_paths"] = {"json": Path("data/demo.json")}

        state = build_threads_slow_state(report, batch_size=2, accounts_total=85, note="resume test")

        self.assertEqual(state["last_completed_offset"], 8)
        self.assertEqual(state["next_offset"], 9)
        self.assertEqual(state["batch_size"], 2)
        self.assertEqual(state["recommended_delay_seconds"], 15.0)
        self.assertEqual(state["cache_ttl_seconds"], 21600)
        self.assertEqual(state["account_source"], "seed_all")
        self.assertEqual(state["accounts_total"], 85)
        self.assertEqual(state["last_batch"]["accounts"], ["first", "second"])
        self.assertEqual(state["last_batch"]["artifact_paths"]["json"], "data/demo.json")
        self.assertIn("resume test", state["note"])

    def test_slow_state_advances_only_attempted_accounts_when_rate_limited(self) -> None:
        accounts = [
            {"handle": "first", "display_name": "first", "category": "trader", "priority": "high"},
            {"handle": "second", "display_name": "second", "category": "trader", "priority": "high"},
            {"handle": "third", "display_name": "third", "category": "trader", "priority": "high"},
        ]

        def rate_limited_fetcher(handle: str, timeout: int = 30) -> str:
            raise urllib.error.HTTPError(url=f"https://example.com/{handle}", code=429, msg="Too Many Requests", hdrs=None, fp=None)

        report = build_threads_view_scan_report(
            accounts=accounts,
            account_offset=11,
            fetch_live=True,
            fetcher=rate_limited_fetcher,
            max_consecutive_rate_limits=1,
        )
        state = build_threads_slow_state(report, batch_size=3)

        self.assertEqual(report["skipped_accounts"], ["second", "third"])
        self.assertEqual(state["last_completed_offset"], 11)
        self.assertEqual(state["next_offset"], 12)
        self.assertEqual(state["last_batch"]["accounts"], ["first"])
        self.assertTrue(state["last_batch"]["stopped_early"])

    def test_slow_state_can_be_saved_and_loaded(self) -> None:
        report = {
            "summary": "Threads view scan: 1계정 / 0글 / actionable 0건",
            "account_source": "seed_all",
            "account_offset": 3,
            "account_count": 1,
            "accounts": [{"handle": "bullish_bee"}],
            "cache_ttl_seconds": 21600,
            "delay_seconds": 15,
            "fetch_errors": [],
            "stopped_early": False,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "slow_state.json"
            saved = save_threads_slow_state(report, state_path=state_path, batch_size=1, accounts_total=85)
            loaded = load_threads_slow_state(saved)

        self.assertEqual(loaded["next_offset"], 4)
        self.assertEqual(loaded["last_batch"]["accounts"], ["bullish_bee"])


if __name__ == "__main__":
    unittest.main()
