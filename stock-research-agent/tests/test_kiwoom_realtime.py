import unittest

from src.kiwoom_realtime import (
    build_register_message,
    build_remove_message,
    get_websocket_url,
    normalize_realtime_message,
)


class KiwoomRealtimeTest(unittest.TestCase):
    def test_websocket_url_selects_mock_and_prod(self):
        self.assertEqual(get_websocket_url("mock"), "wss://mockapi.kiwoom.com:10000/api/dostk/websocket")
        self.assertEqual(get_websocket_url("prod"), "wss://api.kiwoom.com:10000/api/dostk/websocket")

    def test_build_register_and_remove_messages_for_core_realtime_types(self):
        reg = build_register_message(["005930", "000660.KS"], types=["0B", "0D", "0w"], group_no="7")
        remove = build_remove_message(["005930"], types=["0w"], group_no="7")

        self.assertEqual(reg["trnm"], "REG")
        self.assertEqual(reg["grp_no"], "7")
        self.assertEqual(reg["refresh"], "1")
        self.assertEqual(reg["data"], [{"item": ["005930", "000660"], "type": ["0B", "0D", "0w"]}])
        self.assertEqual(remove["trnm"], "REMOVE")
        self.assertEqual(remove["data"], [{"item": ["005930"], "type": ["0w"]}])

    def test_normalize_tick_orderbook_and_program_realtime_messages(self):
        raw = {
            "trnm": "REAL",
            "data": [
                {
                    "item": "005930",
                    "type": "0B",
                    "values": {"20": "093001", "10": "+71500", "11": "+500", "12": "+0.70", "13": "1200000", "14": "85800000000", "228": "152.3", "1313": "250000000"},
                },
                {
                    "item": "005930",
                    "type": "0D",
                    "values": {"21": "093002", "41": "71600", "51": "71500", "61": "12000", "71": "15000", "121": "550000", "125": "610000", "128": "60000", "129": "52.6"},
                },
                {
                    "item": "005930",
                    "type": "0w",
                    "values": {"20": "093003", "10": "+71500", "202": "100000", "204": "10000", "206": "190000", "208": "15500", "210": "+90000", "212": "+5500"},
                },
            ],
        }

        events = normalize_realtime_message(raw, collected_at="2026-05-07T09:30:04+09:00")

        self.assertEqual(len(events), 3)
        tick, orderbook, program = events
        self.assertEqual(tick["event"], "stock_tick")
        self.assertEqual(tick["code"], "005930")
        self.assertEqual(tick["current_price"], 71500)
        self.assertEqual(tick["execution_strength"], 152.3)
        self.assertEqual(orderbook["event"], "orderbook")
        self.assertEqual(orderbook["best_ask"], 71600)
        self.assertEqual(orderbook["total_bid_volume"], 610000)
        self.assertEqual(program["event"], "program_trading")
        self.assertEqual(program["program_net_buy_quantity"], 90000)
        self.assertEqual(program["program_net_buy_amount"], 5500)
        self.assertEqual(program["source_type"], "0w")
        self.assertEqual(program["collected_at"], "2026-05-07T09:30:04+09:00")


if __name__ == "__main__":
    unittest.main()
