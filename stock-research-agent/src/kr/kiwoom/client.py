from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TOKEN_CACHE = PROJECT_ROOT / "data" / "kiwoom_token.json"
DEFAULT_PROD_TOKEN_CACHE = PROJECT_ROOT / "data" / "kiwoom_token_prod.json"
DEFAULT_MOCK_TOKEN_CACHE = PROJECT_ROOT / "data" / "kiwoom_token_mock.json"
DEFAULT_ENV_PATH = PROJECT_ROOT / "config" / "kiwoom.env"


@dataclass(frozen=True, repr=False)
class KiwoomConfig:
    env: str = "mock"
    appkey: str = ""
    secretkey: str = ""
    token_cache: Path | None = DEFAULT_TOKEN_CACHE
    timeout: int = 15
    purpose: str = "default"

    @property
    def normalized_env(self) -> str:
        env = (self.env or "mock").strip().lower()
        if env in {"prod", "production", "real", "live"}:
            return "prod"
        return "mock"

    @property
    def rest_base_url(self) -> str:
        if self.normalized_env == "prod":
            return "https://api.kiwoom.com"
        return "https://mockapi.kiwoom.com"

    @property
    def websocket_url(self) -> str:
        if self.normalized_env == "prod":
            return "wss://api.kiwoom.com:10000/api/dostk/websocket"
        return "wss://mockapi.kiwoom.com:10000/api/dostk/websocket"

    def __repr__(self) -> str:
        cache = str(self.token_cache) if self.token_cache else "None"
        return f"KiwoomConfig(env={self.normalized_env!r}, purpose={self.purpose!r}, appkey='<redacted>', secretkey='<redacted>', token_cache={cache!r})"


@dataclass
class KiwoomTRResult:
    data: dict[str, Any]
    cont_yn: str = "N"
    next_key: str = ""
    status_code: int = 200
    headers: dict[str, str] | None = None


def _parse_env_file(path: str | Path) -> dict[str, str]:
    env: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return env
    for raw_line in p.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _env_get(file_env: dict[str, str], name: str, default: str = "") -> str:
    return os.environ.get(name) or file_env.get(name) or default


def _first_env(file_env: dict[str, str], *names: str, default: str = "") -> str:
    for name in names:
        value = _env_get(file_env, name)
        if value:
            return value
    return default


def _normalized_env_name(value: str) -> str:
    env = (value or "mock").strip().lower()
    if env in {"prod", "production", "real", "live"}:
        return "prod"
    return "mock"


def _role_credentials(file_env: dict[str, str], role: str, env: str) -> tuple[str, str]:
    role_key = role.upper()
    env_key = "PROD" if _normalized_env_name(env) == "prod" else "MOCK"
    appkey = _first_env(
        file_env,
        f"KIWOOM_{role_key}_APPKEY",
        f"KIWOOM_{env_key}_APPKEY",
        "KIWOOM_APPKEY",
    )
    secretkey = _first_env(
        file_env,
        f"KIWOOM_{role_key}_SECRETKEY",
        f"KIWOOM_{role_key}_SECRET",
        f"KIWOOM_{env_key}_SECRETKEY",
        f"KIWOOM_{env_key}_SECRET",
        "KIWOOM_SECRETKEY",
        "KIWOOM_SECRET",
    )
    return appkey, secretkey


def _role_token_cache(file_env: dict[str, str], role: str, env: str) -> Path | None:
    role_key = role.upper()
    env_name = _normalized_env_name(env)
    env_key = "PROD" if env_name == "prod" else "MOCK"
    default_cache = DEFAULT_PROD_TOKEN_CACHE if env_name == "prod" else DEFAULT_MOCK_TOKEN_CACHE
    token_cache = _first_env(
        file_env,
        f"KIWOOM_{role_key}_TOKEN_CACHE",
        f"KIWOOM_TOKEN_CACHE_{env_key}",
        f"KIWOOM_{env_key}_TOKEN_CACHE",
        default=str(default_cache),
    )
    return Path(token_cache) if token_cache else None


def load_kiwoom_env(path: str | Path | None = None) -> KiwoomConfig:
    """Load the legacy single Kiwoom environment.

    Backward-compatible path for existing callers. New read-only market data
    code should prefer load_kiwoom_data_env(); order/trading code should prefer
    load_kiwoom_trade_env().
    """
    file_env = _parse_env_file(path or DEFAULT_ENV_PATH)
    token_cache = _env_get(file_env, "KIWOOM_TOKEN_CACHE", str(DEFAULT_TOKEN_CACHE))
    return KiwoomConfig(
        env=_env_get(file_env, "KIWOOM_ENV", "mock"),
        appkey=_env_get(file_env, "KIWOOM_APPKEY"),
        secretkey=_first_env(file_env, "KIWOOM_SECRETKEY", "KIWOOM_SECRET"),
        token_cache=Path(token_cache) if token_cache else None,
        purpose="legacy",
    )


def load_kiwoom_data_env(path: str | Path | None = None) -> KiwoomConfig:
    """Load read-only market-data Kiwoom credentials.

    Intended for quotes, order book, investor/program flow, rankings, and
    condition scans. It supports a prod data domain while keeping trading/order
    APIs on a separate mock/paper config.
    """
    file_env = _parse_env_file(path or DEFAULT_ENV_PATH)
    env = _first_env(file_env, "KIWOOM_DATA_ENV", "KIWOOM_READ_ENV", "KIWOOM_ENV", default="prod")
    appkey, secretkey = _role_credentials(file_env, "DATA", env)
    return KiwoomConfig(
        env=env,
        appkey=appkey,
        secretkey=secretkey,
        token_cache=_role_token_cache(file_env, "DATA", env),
        purpose="data",
    )


def load_kiwoom_trade_env(path: str | Path | None = None) -> KiwoomConfig:
    """Load trading/order Kiwoom credentials.

    Defaults to mock regardless of legacy KIWOOM_ENV so accidental production
    order routing is avoided. Live order support must be implemented as a
    separate explicit opt-in.
    """
    file_env = _parse_env_file(path or DEFAULT_ENV_PATH)
    env = _first_env(file_env, "KIWOOM_TRADE_ENV", "KIWOOM_ORDER_ENV", "KIWOOM_PAPER_ENV", default="mock")
    appkey, secretkey = _role_credentials(file_env, "TRADE", env)
    return KiwoomConfig(
        env=env,
        appkey=appkey,
        secretkey=secretkey,
        token_cache=_role_token_cache(file_env, "TRADE", env),
        purpose="trade",
    )


def build_kiwoom_data_client(
    path: str | Path | None = None,
    session: Any | None = None,
    now: Callable[[], datetime] | None = None,
) -> "KiwoomRestClient":
    return KiwoomRestClient(load_kiwoom_data_env(path), session=session, now=now)


def build_kiwoom_trade_client(
    path: str | Path | None = None,
    session: Any | None = None,
    now: Callable[[], datetime] | None = None,
) -> "KiwoomRestClient":
    return KiwoomRestClient(load_kiwoom_trade_env(path), session=session, now=now)


def _parse_expires_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y%m%d%H%M%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = datetime.strptime(value, fmt)
            if parsed.tzinfo is not None:
                parsed = parsed.replace(tzinfo=None)
            return parsed
        except ValueError:
            continue
    return None


class KiwoomRestClient:
    def __init__(
        self,
        config: KiwoomConfig | None = None,
        session: Any | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.config = config or load_kiwoom_env()
        self.session = session or requests.Session()
        self.now = now or datetime.now
        self._token: str | None = None
        self._token_type: str = "Bearer"
        self._expires_dt: str | None = None

    def __repr__(self) -> str:
        return f"KiwoomRestClient(env={self.config.normalized_env!r}, token='<redacted>')"

    def _cache_path(self) -> Path | None:
        return self.config.token_cache

    def _load_cached_token(self) -> str | None:
        cache_path = self._cache_path()
        if not cache_path or not cache_path.exists():
            return None
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        cached_env = cached.get("env")
        if cached_env != self.config.normalized_env:
            return None
        token = cached.get("token")
        expires_dt = cached.get("expires_dt")
        expires = _parse_expires_dt(expires_dt)
        if not token or not expires:
            return None
        if expires <= self.now() + timedelta(minutes=5):
            return None
        self._token = str(token)
        self._token_type = str(cached.get("token_type") or "Bearer")
        self._expires_dt = str(expires_dt)
        return self._token

    def _write_cached_token(self, payload: dict[str, Any]) -> None:
        cache_path = self._cache_path()
        if not cache_path:
            return
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        safe_payload = {
            "env": self.config.normalized_env,
            "purpose": self.config.purpose,
            "token_type": payload.get("token_type") or "Bearer",
            "token": payload.get("token"),
            "expires_dt": payload.get("expires_dt"),
        }
        cache_path.write_text(json.dumps(safe_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def issue_token(self) -> dict[str, Any]:
        if not self.config.appkey or not self.config.secretkey:
            raise ValueError("KIWOOM_APPKEY and KIWOOM_SECRETKEY are required")
        response = self.session.post(
            f"{self.config.rest_base_url}/oauth2/token",
            json={
                "grant_type": "client_credentials",
                "appkey": self.config.appkey,
                "secretkey": self.config.secretkey,
            },
            headers={"Content-Type": "application/json;charset=UTF-8"},
            timeout=self.config.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("token"):
            safe_message = payload.get("return_msg") or payload.get("error_description") or payload.get("error") or "Kiwoom token response did not include token"
            safe_code = payload.get("return_code") or ""
            raise RuntimeError(f"Kiwoom token issue failed: {safe_code} {safe_message}".strip())
        self._write_cached_token(payload)
        self._token = str(payload.get("token"))
        self._token_type = str(payload.get("token_type") or "Bearer")
        self._expires_dt = str(payload.get("expires_dt") or "")
        return payload

    def get_token(self) -> str:
        if self._token:
            return self._token
        cached = self._load_cached_token()
        if cached:
            return cached
        self.issue_token()
        if not self._token:
            raise RuntimeError("failed to issue Kiwoom token")
        return self._token

    def post_tr(
        self,
        api_id: str,
        endpoint: str,
        body: dict[str, Any],
        cont_yn: str = "N",
        next_key: str = "",
    ) -> KiwoomTRResult:
        token = self.get_token()
        endpoint_path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        headers = {
            "authorization": f"{self._token_type} {token}",
            "Content-Type": "application/json;charset=UTF-8",
            "api-id": api_id,
            "cont-yn": cont_yn,
            "next-key": next_key,
        }
        response = self.session.post(
            f"{self.config.rest_base_url}{endpoint_path}",
            json=body,
            headers=headers,
            timeout=self.config.timeout,
        )
        response.raise_for_status()
        data = response.json()
        response_headers = dict(getattr(response, "headers", {}) or {})
        return KiwoomTRResult(
            data=data,
            cont_yn=response_headers.get("cont-yn") or response_headers.get("Cont-Yn") or "N",
            next_key=response_headers.get("next-key") or response_headers.get("Next-Key") or "",
            status_code=getattr(response, "status_code", 200),
            headers=response_headers,
        )

    def paginate_tr(self, api_id: str, endpoint: str, body: dict[str, Any], limit: int = 10) -> list[KiwoomTRResult]:
        results: list[KiwoomTRResult] = []
        cont_yn = "N"
        next_key = ""
        for _ in range(limit):
            result = self.post_tr(api_id, endpoint, body, cont_yn=cont_yn, next_key=next_key)
            results.append(result)
            if result.cont_yn != "Y" or not result.next_key:
                break
            cont_yn = "Y"
            next_key = result.next_key
        return results
