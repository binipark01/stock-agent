import unittest

from src import us_core_helpers
from src.main import build_brief_from_db, build_symbol_summary


class USCoreHelpersExtractionTest(unittest.TestCase):
    def test_core_helpers_live_in_dedicated_module_and_stay_reexported(self) -> None:
        self.assertIs(build_brief_from_db, us_core_helpers.build_brief_from_db)
        self.assertIs(build_symbol_summary, us_core_helpers.build_symbol_summary)
        self.assertTrue(callable(us_core_helpers.build_market_summary))


if __name__ == "__main__":
    unittest.main()
