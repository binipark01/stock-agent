import unittest

try:
    from tests.main_mode_core_brief import CoreBriefModeCases
    from tests.main_mode_krx import KrxModeCases
    from tests.main_mode_openbb import OpenBBModeCases
    from tests.main_mode_sector import SectorModeCases
    from tests.main_mode_news_brief import NewsBriefModeCases
    from tests.main_mode_portfolio_news import PortfolioNewsModeCases
    from tests.main_mode_social import SocialModeCases
    from tests.main_mode_toss_watchlist_options import TossWatchlistOptionsModeCases
except ImportError:  # pragma: no cover - unittest discover with tests/ on sys.path
    from main_mode_core_brief import CoreBriefModeCases
    from main_mode_krx import KrxModeCases
    from main_mode_openbb import OpenBBModeCases
    from main_mode_sector import SectorModeCases
    from main_mode_news_brief import NewsBriefModeCases
    from main_mode_portfolio_news import PortfolioNewsModeCases
    from main_mode_social import SocialModeCases
    from main_mode_toss_watchlist_options import TossWatchlistOptionsModeCases


class StockResearchAgentTest(
    SectorModeCases,
    TossWatchlistOptionsModeCases,
    SocialModeCases,
    NewsBriefModeCases,
    PortfolioNewsModeCases,
    CoreBriefModeCases,
    KrxModeCases,
    OpenBBModeCases,
    unittest.TestCase,
):
    """Backward-compatible aggregate for main-mode response tests."""


if __name__ == "__main__":
    unittest.main()
