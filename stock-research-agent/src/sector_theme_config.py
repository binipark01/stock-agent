from __future__ import annotations

from typing import Any

CORE_SECTOR_ETFS: dict[str, str] = {
    "XLK": "기술",
    "XLY": "경기소비재",
    "XLC": "커뮤니케이션",
    "XLF": "금융",
    "XLV": "헬스케어",
    "XLI": "산업재",
    "XLE": "에너지",
    "XLU": "유틸리티",
    "XLP": "필수소비재",
    "XLB": "소재",
    "XLRE": "리츠/부동산",
}

THEME_ETFS: dict[str, str] = {
    "SMH": "반도체",
    "SOXX": "반도체",
    "IGV": "소프트웨어",
    "XBI": "바이오",
    "IBB": "바이오",
    "ARKK": "고베타 성장",
    "KWEB": "중국 인터넷",
    "TAN": "태양광",
    "URA": "우라늄",
    "ITA": "방산",
    "XAR": "항공/방산",
}

USER_THEME_BASKETS: dict[str, dict[str, Any]] = {
    "space_aerospace": {
        "name": "우주/항공우주",
        "symbols": ("RKLB", "RKLX", "RKLZ", "LUNR", "RDW", "ASTS", "ASTX", "PL", "BKSY", "RCAT", "JOBY", "ACHR", "SATS", "GSAT", "FLY", "SIDU", "VOY"),
        "excluded_from_score": ("RKLX", "RKLZ", "ASTX"),
    },
    "crypto_equities": {
        "name": "암호화/코인 관련주",
        "symbols": ("BMNR", "BMNU", "BMNZ", "MSTR", "MSTU", "CRCL", "CRCA", "HOOD", "HOOG", "COIN", "CONL", "CLSK", "SBET", "CIFR", "BLSH", "BTOG", "SOFI", "MARA", "ETHU", "SOLT", "RIOT", "IREN", "HUT", "BTBT", "BITF", "WULF"),
        "excluded_from_score": ("BMNU", "BMNZ", "MSTU", "CRCA", "HOOG", "CONL", "ETHU", "SOLT"),
    },
    "nuclear_power_uranium": {
        "name": "원전/우라늄/전력/에너지",
        "symbols": ("OKLO", "OKLL", "OKLS", "SMR", "SMU", "CCJ", "UEC", "URA", "REMX", "MP", "USAR", "URG", "UUUU", "CRML", "NB", "AREC", "GEV", "ASPI", "VST", "ETN", "NRG", "CEG", "TLN", "NXE", "BWXT", "PWR", "DNN", "OXY", "PLUG", "FLNC", "EOSE", "TE", "XOM"),
        "excluded_from_score": ("OKLL", "OKLS", "SMU"),
    },
    "ai_bigtech_infra": {
        "name": "AI/빅테크/인프라",
        "symbols": ("GOOG", "GGLL", "PLTR", "PLTU", "PLTZ", "TSLA", "TSLL", "TSLQ", "MSFT", "MSFU", "AMZN", "AMZU", "AAPL", "AAPU", "META", "FBL", "IBM", "DELL", "TEM", "TEMT", "PONY", "BBAI", "SOUN", "SES", "RZLV", "AI", "ORCL", "ORCX", "IREN", "IRE", "IREZ", "NBIS", "CRWV", "RDDT", "VRT", "RCT", "NET"),
        "excluded_from_score": ("GGLL", "PLTU", "PLTZ", "TSLL", "TSLQ", "MSFU", "AMZU", "AAPU", "FBL", "TEMT", "ORCX", "IRE", "IREZ"),
    },
    "semiconductors": {
        "name": "반도체/AI칩",
        "symbols": ("NVDA", "NVDL", "NVD", "AMD", "AMDL", "AVGO", "MRVL", "MVLL", "ARM", "QCOM", "INTC", "MU", "MUU", "SNDK", "SNXX", "STX", "TSM", "TSMX", "AMAT", "SNPS", "SMCI", "SMCX", "LRCX", "KLAC", "NVTS", "SOXX", "SOXL", "SOXS", "SMH"),
        "excluded_from_score": ("NVDL", "NVD", "AMDL", "MVLL", "MUU", "SNXX", "TSMX", "SMCX", "SOXL", "SOXS"),
    },
    "quantum": {
        "name": "양자/차세대컴퓨팅",
        "symbols": ("IONQ", "IONX", "IONZ", "RGTI", "RGTX", "QBTS", "LAES", "ARQQ", "BTQ", "QUBT", "QSI", "QS"),
        "excluded_from_score": ("IONX", "IONZ", "RGTX"),
    },
    "healthcare_glp1_digital": {
        "name": "헬스케어/GLP-1/디지털헬스",
        "symbols": ("HIMS", "HIMZ", "OSCR", "TDOC", "RXRX", "LLY", "NVO", "PFE", "UNH"),
        "excluded_from_score": ("HIMZ",),
    },
}

USER_SUB_THEME_BASKETS: dict[str, dict[str, Any]] = {
    "semis_ai_accelerators": {"parent": "semiconductors", "name": "AI 가속기/GPU", "symbols": ("NVDA", "AMD", "AVGO", "ARM"), "excluded_from_score": ()},
    "semis_cpu_server_pc": {"parent": "semiconductors", "name": "CPU/서버/PC칩", "symbols": ("AMD", "INTC", "ARM", "QCOM"), "excluded_from_score": ()},
    "semis_memory_storage": {"parent": "semiconductors", "name": "메모리/스토리지", "symbols": ("MU", "SNDK", "STX"), "excluded_from_score": ()},
    "semis_foundry_manufacturing": {"parent": "semiconductors", "name": "파운드리/제조", "symbols": ("TSM", "INTC"), "excluded_from_score": ()},
    "semis_equipment": {"parent": "semiconductors", "name": "반도체 장비", "symbols": ("AMAT", "LRCX", "KLAC"), "excluded_from_score": ()},
    "semis_eda_ip": {"parent": "semiconductors", "name": "EDA/IP/설계", "symbols": ("SNPS", "ARM"), "excluded_from_score": ()},
    "semis_ai_servers_power": {"parent": "semiconductors", "name": "AI 서버/전력반도체", "symbols": ("SMCI", "VRT", "DELL", "NVTS"), "excluded_from_score": ()},
    "power_smr": {"parent": "nuclear_power_uranium", "name": "SMR/차세대원전", "symbols": ("OKLO", "SMR"), "excluded_from_score": ()},
    "nuclear_smr": {"parent": "nuclear_power_uranium", "name": "SMR/차세대원전", "symbols": ("OKLO", "SMR"), "excluded_from_score": ()},
    "power_uranium_miners": {"parent": "nuclear_power_uranium", "name": "우라늄 채굴/연료", "symbols": ("CCJ", "UEC", "URG", "UUUU", "DNN", "NXE", "URA"), "excluded_from_score": ()},
    "power_critical_minerals": {"parent": "nuclear_power_uranium", "name": "희토류/핵심광물", "symbols": ("MP", "USAR", "REMX", "CRML", "NB", "AREC"), "excluded_from_score": ()},
    "power_utilities_generation": {"parent": "nuclear_power_uranium", "name": "전력/유틸리티/발전", "symbols": ("GEV", "VST", "NRG", "CEG", "TLN"), "excluded_from_score": ()},
    "power_grid_equipment": {"parent": "nuclear_power_uranium", "name": "전력 장비/인프라", "symbols": ("ETN", "BWXT", "PWR"), "excluded_from_score": ()},
    "crypto_platforms": {"parent": "crypto_equities", "name": "거래소/브로커/플랫폼", "symbols": ("COIN", "HOOD", "SOFI", "CRCL"), "excluded_from_score": ()},
    "crypto_miners_ai_power": {"parent": "crypto_equities", "name": "채굴/AI전력연계", "symbols": ("MARA", "RIOT", "CLSK", "IREN", "CIFR", "WULF", "HUT", "BTBT", "BITF"), "excluded_from_score": ()},
    "space_launch_infra": {"parent": "space_aerospace", "name": "발사체/우주인프라", "symbols": ("RKLB", "LUNR", "RDW"), "excluded_from_score": ()},
    "space_satellite_comms": {"parent": "space_aerospace", "name": "위성/통신", "symbols": ("ASTS", "SATS", "GSAT"), "excluded_from_score": ()},
    "space_drone_defense_airmobility": {"parent": "space_aerospace", "name": "드론/방산/항공", "symbols": ("RCAT", "JOBY", "ACHR", "FLY"), "excluded_from_score": ()},
    "ai_hyperscaler_cloud": {"parent": "ai_bigtech_infra", "name": "Hyperscaler/Cloud", "symbols": ("MSFT", "AMZN", "GOOG", "ORCL", "META"), "excluded_from_score": ()},
    "ai_software_data": {"parent": "ai_bigtech_infra", "name": "AI 소프트웨어/데이터", "symbols": ("PLTR", "AI", "BBAI", "RZLV", "SOUN"), "excluded_from_score": ()},
    "ai_datacenter_infra": {"parent": "ai_bigtech_infra", "name": "데이터센터/AI인프라", "symbols": ("DELL", "VRT", "NBIS", "CRWV"), "excluded_from_score": ()},
    "quantum_pureplay": {"parent": "quantum", "name": "순수 양자컴퓨팅", "symbols": ("IONQ", "RGTI", "QBTS", "QUBT"), "excluded_from_score": ()},
    "quantum_security_comms": {"parent": "quantum", "name": "양자보안/통신", "symbols": ("ARQQ", "LAES", "BTQ"), "excluded_from_score": ()},
    "health_digital_consumer": {"parent": "healthcare_glp1_digital", "name": "디지털헬스/소비자헬스", "symbols": ("HIMS", "TDOC", "OSCR"), "excluded_from_score": ()},
    "health_glp1_obesity": {"parent": "healthcare_glp1_digital", "name": "GLP-1/비만약", "symbols": ("LLY", "NVO"), "excluded_from_score": ()},
}

BENCHMARK_SYMBOLS = ("SPY", "QQQ")
REGIME_SYMBOLS = ("^VIX", "CL=F", "BZ=F", "^TNX", "DX-Y.NYB", "BTC-USD", "ETH-USD")
USER_THEME_SYMBOLS = tuple(symbol for basket in USER_THEME_BASKETS.values() for symbol in basket["symbols"])
USER_SUB_THEME_SYMBOLS = tuple(symbol for basket in USER_SUB_THEME_BASKETS.values() for symbol in basket["symbols"])
DEFAULT_SECTOR_STRENGTH_SYMBOLS = tuple(dict.fromkeys((*BENCHMARK_SYMBOLS, *CORE_SECTOR_ETFS, *THEME_ETFS, *USER_THEME_SYMBOLS, *USER_SUB_THEME_SYMBOLS, *REGIME_SYMBOLS)))
