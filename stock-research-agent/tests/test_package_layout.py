import unittest

from src import krx_mode_handlers, us_mode_handlers
from src.kr import mode_handlers as kr_mode_handlers
from src.us import mode_handlers as us_package_mode_handlers
from src.us import core_helpers as us_core_helpers
from src.main import build_brief_from_db


class PackageLayoutCompatibilityTest(unittest.TestCase):
    def test_us_mode_handler_moved_to_package_and_old_wrapper_still_exports(self) -> None:
        self.assertIs(
            us_mode_handlers.build_us_mode_response,
            us_package_mode_handlers.build_us_mode_response,
        )

    def test_krx_mode_handler_moved_to_package_and_old_wrapper_still_exports(self) -> None:
        self.assertIs(
            krx_mode_handlers.build_krx_mode_response,
            kr_mode_handlers.build_krx_mode_response,
        )

    def test_main_reexports_core_helper_from_us_package(self) -> None:
        self.assertIs(build_brief_from_db, us_core_helpers.build_brief_from_db)


if __name__ == "__main__":
    unittest.main()
