import unittest
from unittest.mock import patch

from src import (
    market_data,
    openbb_provider,
    options_flow,
    sec_filings,
    sector_strength,
    sector_theme_config,
    technical_snapshot,
    threads_social,
    threads_view_miner,
    yfinance_data,
)
from src.us.market_data import openbb as us_openbb
from src.us.market_data import core as us_market_data_core
from src.us.market_data import yfinance as us_yfinance
from src.us.news import sec_filings as us_sec_filings
from src.us.options import flow as us_options_flow
from src.us.sector import strength as us_sector_strength
from src.us.sector import theme_config as us_sector_theme_config
from src.us.social import threads as us_threads
from src.us.social import threads_view_miner as us_threads_view_miner
from src.us.technical import snapshot as us_technical_snapshot


class UsDomainPackageLayoutTest(unittest.TestCase):
    def test_market_data_modules_moved_and_old_paths_alias(self) -> None:
        self.assertIs(yfinance_data.fetch_yfinance_market_pack, us_yfinance.fetch_yfinance_market_pack)
        self.assertIs(openbb_provider.build_openbb_quote, us_openbb.build_openbb_quote)
        self.assertIs(market_data.fetch_price_history, us_market_data_core.fetch_price_history)

    def test_news_social_options_sector_modules_moved_and_old_paths_alias(self) -> None:
        self.assertIs(sec_filings.fetch_sec_filings_pack, us_sec_filings.fetch_sec_filings_pack)
        self.assertIs(options_flow.build_options_flow_report, us_options_flow.build_options_flow_report)
        self.assertIs(threads_social.search_threads_seed_accounts, us_threads.search_threads_seed_accounts)
        self.assertIs(threads_view_miner.build_threads_view_scan_report, us_threads_view_miner.build_threads_view_scan_report)
        self.assertIs(sector_strength.build_sector_strength_report, us_sector_strength.build_sector_strength_report)
        self.assertIs(sector_theme_config.BENCHMARK_SYMBOLS, us_sector_theme_config.BENCHMARK_SYMBOLS)

    def test_technical_snapshot_old_patch_path_still_hits_implementation(self) -> None:
        records = []
        price_records = [float(i) for i in range(1, 230)]
        with patch('src.technical_snapshot.fetch_price_ohlcv_history', return_value=records), patch(
            'src.technical_snapshot.fetch_price_history', return_value=price_records
        ) as fallback_fetch:
            result = us_technical_snapshot.build_technical_snapshot('NVDA')
        self.assertEqual(result['symbol'], 'NVDA')
        fallback_fetch.assert_called_once_with('NVDA')


if __name__ == '__main__':
    unittest.main()
