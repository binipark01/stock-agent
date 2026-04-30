#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from threads_social import save_threads_seed_classification, search_threads_seed_accounts  # noqa: E402


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "classify":
        path = save_threads_seed_classification()
        print(json.dumps({"saved": str(path)}, ensure_ascii=False))
        return
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        print("usage: python3 scripts/threads_seed_search.py classify|<query>")
        return
    hits = search_threads_seed_accounts(query)
    print(json.dumps(hits, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
