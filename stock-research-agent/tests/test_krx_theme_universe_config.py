import json
import unittest
from collections import defaultdict
from pathlib import Path


CONFIG = Path(__file__).resolve().parents[1] / "config" / "krx_theme_universe.json"


def load_config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


class KrxThemeUniverseConfigTest(unittest.TestCase):
    def test_theme_universe_json_shape_and_codes(self):
        data = load_config()

        self.assertEqual(data["schema_version"], 1)
        self.assertTrue(data["membership_policy"]["allow_duplicate_codes_across_themes"])
        self.assertTrue(data["membership_policy"]["dedupe_within_theme_by_code"])
        self.assertGreaterEqual(len(data["themes"]), 20)

        for theme in data["themes"]:
            self.assertIn("id", theme)
            self.assertIn("name", theme)
            self.assertIn("members", theme)
            self.assertGreaterEqual(len(theme["members"]), 3, theme["name"])
            seen_in_theme = set()
            for member in theme["members"]:
                self.assertRegex(member["code"], r"^\d{6}$", member)
                self.assertTrue(member["name"].strip(), member)
                self.assertNotIn(member["code"], seen_in_theme, theme["name"])
                seen_in_theme.add(member["code"])

    def test_cross_theme_memberships_are_intentional(self):
        data = load_config()
        themes_by_code = defaultdict(set)
        names_by_code = {}
        for theme in data["themes"]:
            for member in theme["members"]:
                themes_by_code[member["code"]].add(theme["name"])
                names_by_code[member["code"]] = member["name"]

        duplicated_codes = {code: themes for code, themes in themes_by_code.items() if len(themes) > 1}
        self.assertGreaterEqual(len(duplicated_codes), 40)

        expected = {
            "051910": {"2차전지", "화학/정유"},  # LG화학
            "096770": {"2차전지", "화학/정유"},  # SK이노베이션
            "035420": {"인터넷/플랫폼", "AI/소프트웨어/보안", "통신/IDC"},  # NAVER
            "035720": {"인터넷/플랫폼", "AI/소프트웨어/보안", "통신/IDC"},  # 카카오
            "034020": {"전력기기/전선", "원전", "건설/기계"},  # 두산에너빌리티
            "272210": {"방산", "AI/소프트웨어/보안"},  # 한화시스템
            "086280": {"자동차", "해운/항공/물류"},  # 현대글로비스
            "237690": {"바이오대형/CDMO", "바이오플랫폼/신약"},  # 에스티팜
        }
        for code, expected_themes in expected.items():
            self.assertTrue(
                expected_themes.issubset(themes_by_code[code]),
                f"{names_by_code.get(code, code)} themes={sorted(themes_by_code[code])}",
            )

    def test_majority_threshold_uses_theme_membership_count(self):
        data = load_config()
        theme_sizes = {theme["name"]: len(theme["members"]) for theme in data["themes"]}

        self.assertEqual(theme_sizes["AI/소프트웨어/보안"], 28)
        self.assertEqual(theme_sizes["AI/소프트웨어/보안"] // 2 + 1, 15)
        self.assertEqual(theme_sizes["반도체/소재"], 22)
        self.assertEqual(theme_sizes["반도체/소재"] // 2 + 1, 12)
        self.assertEqual(theme_sizes["반도체/설계"], 7)
        self.assertEqual(theme_sizes["반도체/설계"] // 2 + 1, 4)
        self.assertEqual(theme_sizes["반도체/후공정"], 12)
        self.assertEqual(theme_sizes["반도체/후공정"] // 2 + 1, 7)
        self.assertEqual(theme_sizes["인터넷/플랫폼"], 7)
        self.assertEqual(theme_sizes["인터넷/플랫폼"] // 2 + 1, 4)

    def test_semiconductor_subthemes_are_nested_under_semiconductor_parent(self):
        data = load_config()
        semiconductor_themes = [
            theme for theme in data["themes"]
            if theme["id"].startswith("semiconductor_")
        ]
        self.assertGreaterEqual(len(semiconductor_themes), 7)
        for theme in semiconductor_themes:
            self.assertEqual(theme.get("parent_theme"), "반도체", theme)
            self.assertTrue(theme["name"].startswith("반도체/"), theme["name"])
            self.assertEqual(theme["name"].count("/"), 1, theme["name"])
        self.assertNotIn("반도체/소재/가스/케미칼", {theme["name"] for theme in data["themes"]})

    def test_user_semiconductor_watchlist_screen_is_covered_by_subthemes(self):
        data = load_config()
        semiconductor_theme_names = {
            "반도체/HBM",
            "반도체/장비",
            "반도체/소재",
            "반도체/제조",
            "반도체/설계",
            "반도체/후공정",
            "반도체/기판",
        }
        covered = {
            member["name"]
            for theme in data["themes"]
            if theme["name"] in semiconductor_theme_names
            for member in theme["members"]
        }

        screenshot_names = {
            "삼성전자", "SK하이닉스", "DB하이텍", "원익IPS", "한미반도체",
            "제주반도체", "리노공업", "하나마이크론", "LX세미콘", "오픈엣지테크놀로지",
            "가온칩스", "에이디테크놀로지", "두산테스나", "SFA반도체", "솔브레인",
            "동진쎄미켐", "SKC", "하나머티리얼즈", "티씨케이", "후성",
            "어보브반도체", "유진테크", "RFHIC", "PI첨단소재", "원익",
            "삼양엔씨켐", "싸이맥스", "주성엔지니어링", "네패스", "디아이",
            "태성", "와이씨", "오킨스전자", "프로텍",
        }
        self.assertTrue(screenshot_names.issubset(covered), sorted(screenshot_names - covered))

        theme_sizes = {theme["name"]: len(theme["members"]) for theme in data["themes"]}
        self.assertEqual(theme_sizes["반도체/제조"], 3)
        self.assertEqual(theme_sizes["반도체/소재"], 22)
        self.assertEqual(theme_sizes["반도체/기판"], 5)

    def test_user_electric_watchlist_screen_is_covered_by_subthemes(self):
        data = load_config()
        electric_theme_names = {
            "전력기기/전선",
            "전력기기/변압기",
            "전선/전력망",
            "스마트그리드/전력제어",
            "전기부품/콘덴서",
        }
        covered = {
            member["name"]
            for theme in data["themes"]
            if theme["name"] in electric_theme_names
            for member in theme["members"]
        }

        screenshot_names = {
            "HD현대일렉트릭", "효성중공업", "LS ELECTRIC", "대한전선", "가온전선",
            "일진전기", "제룡전기", "세명전기", "제룡산업", "대원전선",
            "비츠로테크", "누리플렉스", "옴니시스템", "삼화콘덴서", "신성이엔지",
            "삼화전기", "산일전기", "삼성전기", "비츠로시스",
        }
        self.assertTrue(screenshot_names.issubset(covered), sorted(screenshot_names - covered))

        theme_sizes = {theme["name"]: len(theme["members"]) for theme in data["themes"]}
        self.assertEqual(theme_sizes["전력기기/변압기"], 6)
        self.assertEqual(theme_sizes["전력기기/변압기"] // 2 + 1, 4)
        self.assertEqual(theme_sizes["전선/전력망"], 8)
        self.assertEqual(theme_sizes["전선/전력망"] // 2 + 1, 5)
        self.assertEqual(theme_sizes["스마트그리드/전력제어"], 6)
        self.assertEqual(theme_sizes["스마트그리드/전력제어"] // 2 + 1, 4)
        self.assertEqual(theme_sizes["전기부품/콘덴서"], 5)
        self.assertEqual(theme_sizes["전기부품/콘덴서"] // 2 + 1, 3)

    def test_user_battery_and_shipbuilding_watchlist_screens_are_covered(self):
        data = load_config()
        members_by_theme = {
            theme["name"]: {member["name"] for member in theme["members"]}
            for theme in data["themes"]
        }

        battery_names = {
            "LG에너지솔루션", "삼성SDI", "에코프로", "에코프로비엠", "에코프로머티",
            "엘앤에프", "포스코퓨처엠", "대주전자재료", "엔켐", "SKC",
            "이수스페셜티케미컬", "강원에너지", "레이크머티리얼즈", "롯데에너지머티리얼즈", "코스모신소재",
        }
        self.assertTrue(
            battery_names.issubset(members_by_theme["2차전지"]),
            sorted(battery_names - members_by_theme["2차전지"]),
        )

        shipbuilding_names = {
            "HD현대중공업", "HD한국조선해양", "삼성중공업", "한화오션", "HJ중공업",
            "삼영엠텍", "한화엔진", "HD현대마린엔진", "세진중공업", "오리엔탈정공",
            "현대힘스", "STX엔진", "한국카본", "동방선기", "태광",
            "일승", "케이에스피", "케이프", "성광벤드", "대창솔루션",
            "에스앤더블류", "하이록코리아", "한라IMS", "엔케이", "대한조선", "동성화인텍",
        }
        self.assertTrue(
            shipbuilding_names.issubset(members_by_theme["조선"]),
            sorted(shipbuilding_names - members_by_theme["조선"]),
        )

        self.assertEqual(len(members_by_theme["2차전지"]), 18)
        self.assertEqual(len(members_by_theme["2차전지"]) // 2 + 1, 10)
        self.assertEqual(len(members_by_theme["조선"]), 28)
        self.assertEqual(len(members_by_theme["조선"]) // 2 + 1, 15)

    def test_user_defense_and_nuclear_watchlist_screens_are_covered(self):
        data = load_config()
        members_by_theme = {
            theme["name"]: {member["name"] for member in theme["members"]}
            for theme in data["themes"]
        }

        defense_names = {
            "한화오션", "한화에어로스페이스", "한화시스템", "현대로템", "LIG넥스원",
            "한국항공우주", "HD현대중공업", "제노코", "풍산", "휴니드",
            "켄코아에어로스페이스", "쎄트렉아이", "SNT다이내믹스", "한일단조", "포메탈",
            "스페코", "빅텍", "퍼스텍", "코츠테크놀로지", "STX엔진",
            "웰크론", "한화", "현대위아", "신화프리텍", "한국카본", "삼영",
        }
        self.assertTrue(
            defense_names.issubset(members_by_theme["방산"]),
            sorted(defense_names - members_by_theme["방산"]),
        )

        nuclear_names = {
            "두산에너빌리티", "한전KPS", "한전기술", "우진", "우진엔텍",
            "우리기술", "일진파워", "오르비텍", "SNT에너지", "비에이치아이", "현대건설",
        }
        self.assertTrue(
            nuclear_names.issubset(members_by_theme["원전"]),
            sorted(nuclear_names - members_by_theme["원전"]),
        )

        self.assertEqual(len(members_by_theme["방산"]), 26)
        self.assertEqual(len(members_by_theme["방산"]) // 2 + 1, 14)
        self.assertEqual(len(members_by_theme["원전"]), 13)
        self.assertEqual(len(members_by_theme["원전"]) // 2 + 1, 7)


    def test_user_robot_bio_finance_ai_space_auto_watchlist_screens_are_covered(self):
        data = load_config()
        members_by_theme = {
            theme["name"]: {member["name"] for member in theme["members"]}
            for theme in data["themes"]
        }

        robot_names = {
            "레인보우로보틱스", "두산로보틱스", "로보티즈", "하이젠알앤엠", "고영",
            "에스피지", "클로봇", "유일로보틱스", "로보스타", "휴림로봇",
            "현대오토에버", "이랜시스", "에스비비테크", "우림피티에스", "아진엑스텍",
            "인탑스", "이삭엔지니어링", "에브리봇", "엔젤로보틱스", "로보로보",
            "뉴로메카", "포스코DX", "에스에프에이", "유진로봇", "삼익THK",
            "큐렉소", "티로보틱스", "푸른기술", "마음AI", "라온텍", "라온피플",
        }
        self.assertTrue(
            robot_names.issubset(members_by_theme["로봇/자동화"]),
            sorted(robot_names - members_by_theme["로봇/자동화"]),
        )

        bio_theme_names = {
            "바이오대형/CDMO",
            "바이오플랫폼/신약",
            "바이오/의료AI·디지털헬스",
            "바이오/세포·재생",
            "바이오/미용·헬스케어",
        }
        bio_covered = set().union(*(members_by_theme[name] for name in bio_theme_names))
        bio_names = {
            "삼성바이오로직스", "셀트리온", "SK바이오사이언스", "셀트리온제약", "알테오젠",
            "한미약품", "유한양행", "SK바이오팜", "리가켐바이오", "녹십자",
            "HLB", "에이비엘바이오", "딥노이드", "차바이오텍", "메디포스트",
            "루닛", "코아스템켐온", "아이센스", "일동제약", "파마리서치",
            "대웅제약", "펩트론", "한올바이오파마", "메디톡스", "휴젤",
            "지투지바이오", "광동제약", "대화제약", "뉴로핏", "에스티팜",
            "HK이노엔", "바이넥스", "삼천당제약",
        }
        self.assertTrue(bio_names.issubset(bio_covered), sorted(bio_names - bio_covered))

        finance_names = {
            "삼성증권", "미래에셋증권", "키움증권", "NH투자증권", "한국금융지주",
            "한화투자증권", "대신증권", "유화증권", "유안타증권", "부국증권",
            "SK증권", "교보증권", "유진투자증권", "메리츠금융지주", "KB금융",
        }
        self.assertTrue(
            finance_names.issubset(members_by_theme["보험/증권"]),
            sorted(finance_names - members_by_theme["보험/증권"]),
        )

        ai_names = {
            "NAVER", "카카오", "솔트룩스", "코난테크놀로지", "이스트소프트",
            "마음AI", "씨씨에스", "루닛", "뷰노", "알체라", "폴라리스AI",
            "한글과컴퓨터", "뉴엔AI", "셀바스AI", "와이즈넛", "심플랫폼",
            "딥노이드", "폴라리스오피스", "LG씨엔에스", "SKAI", "SK", "SK텔레콤", "노타",
        }
        self.assertTrue(
            ai_names.issubset(members_by_theme["AI/소프트웨어/보안"]),
            sorted(ai_names - members_by_theme["AI/소프트웨어/보안"]),
        )

        space_names = {"루미르", "쎄트렉아이", "인텔리안테크", "아주IB투자", "이노스페이스"}
        self.assertTrue(space_names.issubset(members_by_theme["우주"]), sorted(space_names - members_by_theme["우주"]))

        auto_names = {
            "현대차", "기아", "KG모빌리티", "현대모비스", "현대위아",
            "한온시스템", "현대오토에버", "삼현", "PS일렉트로닉스", "에스오에스랩",
        }
        self.assertTrue(
            auto_names.issubset(members_by_theme["자동차"]),
            sorted(auto_names - members_by_theme["자동차"]),
        )

        self.assertEqual(len(members_by_theme["로봇/자동화"]), 32)
        self.assertEqual(len(members_by_theme["로봇/자동화"]) // 2 + 1, 17)
        self.assertEqual(len(members_by_theme["보험/증권"]), 21)
        self.assertEqual(len(members_by_theme["보험/증권"]) // 2 + 1, 11)
        self.assertEqual(len(members_by_theme["AI/소프트웨어/보안"]), 28)
        self.assertEqual(len(members_by_theme["AI/소프트웨어/보안"]) // 2 + 1, 15)
        self.assertEqual(len(members_by_theme["우주"]), 5)
        self.assertEqual(len(members_by_theme["우주"]) // 2 + 1, 3)
        self.assertEqual(len(members_by_theme["자동차"]), 16)
        self.assertEqual(len(members_by_theme["자동차"]) // 2 + 1, 9)


if __name__ == "__main__":
    unittest.main()
