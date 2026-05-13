from __future__ import annotations

# Backward-compatible facade.  The implementation lives in smaller modules:
# - krx_flow_common.py
# - krx_flow_snapshot.py
# - krx_flow_rank_scan.py

try:
    from .common import normalize_krx_code
    from .snapshot import (
        build_krx_flow_response,
        build_krx_flow_snapshot,
        build_krx_flow_watch_report,
        build_krx_flow_watch_response,
        format_krx_flow_focus,
        format_krx_flow_watch_focus,
    )
    from .rank_scan import (
        build_krx_flow_rank_response,
        build_krx_flow_rank_scan,
        build_krx_flow_rank_watch_report,
        build_krx_flow_rank_watch_response,
        build_krx_flow_trade_candidates,
        format_krx_flow_rank_focus,
        format_krx_flow_rank_watch_focus,
        format_krx_flow_trade_candidate_focus,
    )
except ImportError:  # direct script execution
    from kr.flow.common import normalize_krx_code
    from kr.flow.snapshot import (
        build_krx_flow_response,
        build_krx_flow_snapshot,
        build_krx_flow_watch_report,
        build_krx_flow_watch_response,
        format_krx_flow_focus,
        format_krx_flow_watch_focus,
    )
    from kr.flow.rank_scan import (
        build_krx_flow_rank_response,
        build_krx_flow_rank_scan,
        build_krx_flow_rank_watch_report,
        build_krx_flow_rank_watch_response,
        build_krx_flow_trade_candidates,
        format_krx_flow_rank_focus,
        format_krx_flow_rank_watch_focus,
        format_krx_flow_trade_candidate_focus,
    )

__all__ = [
    "normalize_krx_code",
    "build_krx_flow_snapshot",
    "format_krx_flow_focus",
    "build_krx_flow_response",
    "build_krx_flow_watch_report",
    "format_krx_flow_watch_focus",
    "build_krx_flow_watch_response",
    "build_krx_flow_rank_scan",
    "format_krx_flow_rank_focus",
    "build_krx_flow_trade_candidates",
    "format_krx_flow_trade_candidate_focus",
    "build_krx_flow_rank_watch_report",
    "build_krx_flow_rank_response",
    "format_krx_flow_rank_watch_focus",
    "build_krx_flow_rank_watch_response",
]
