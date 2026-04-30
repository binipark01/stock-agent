import unittest

from src import sector_theme_config as config
from src.sector_strength import DEFAULT_SECTOR_STRENGTH_SYMBOLS


class SectorThemeConfigTest(unittest.TestCase):
    def test_default_symbol_universe_is_assembled_from_config_module(self):
        self.assertIn("SPY", config.BENCHMARK_SYMBOLS)
        self.assertIn("XLK", config.CORE_SECTOR_ETFS)
        self.assertIn("SMH", config.THEME_ETFS)
        self.assertIn("space_aerospace", config.USER_THEME_BASKETS)
        self.assertIn("semis_ai_accelerators", config.USER_SUB_THEME_BASKETS)
        self.assertIn("RKLB", config.DEFAULT_SECTOR_STRENGTH_SYMBOLS)
        self.assertIn("^VIX", config.DEFAULT_SECTOR_STRENGTH_SYMBOLS)
        self.assertEqual(config.DEFAULT_SECTOR_STRENGTH_SYMBOLS, DEFAULT_SECTOR_STRENGTH_SYMBOLS)
        self.assertEqual(len(config.DEFAULT_SECTOR_STRENGTH_SYMBOLS), len(set(config.DEFAULT_SECTOR_STRENGTH_SYMBOLS)))


if __name__ == "__main__":
    unittest.main()
