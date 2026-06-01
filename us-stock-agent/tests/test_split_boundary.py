import unittest

class SplitBoundaryTests(unittest.TestCase):
    def test_us_main_does_not_import_kr_router(self):
        from src import main
        self.assertFalse(hasattr(main, "build_krx_mode_response"))

    def test_us_request_modes_do_not_route_krx(self):
        from src.request_modes import infer_mode
        self.assertNotEqual(infer_mode("국장 수급 확인"), "krx_flow_snapshot")

if __name__ == "__main__":
    unittest.main()
