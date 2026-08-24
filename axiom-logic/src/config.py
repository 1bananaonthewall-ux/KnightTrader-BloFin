from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
import yaml
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Credentials(BaseModel):
    api_key: str
    secret: str
    passphrase: str

    model_config = ConfigDict(frozen=True)

    @classmethod
    def from_text(cls, path: str | Path) -> Credentials:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Blofin credential file not found: {p}")
        text = p.read_text(encoding="utf-8")
        data: dict[str, str] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                k, v = line.split(":", 1)
                data[k.strip().lower()] = v.strip()
        required = {"api key", "secret key", "passphrase"}
        if not required.issubset(data.keys()):
            raise ValueError(f"Credential file missing fields. Found: {sorted(data)}")
        return cls(
            api_key=data["api key"],
            secret=data["secret key"],
            passphrase=data["passphrase"],
        )


class LoopConfig(BaseModel):
    interval_seconds: int = 60
    jitter_seconds: int = 3
    universe_refresh_seconds: int = 3600


class ModelConfig(BaseModel):
    provider: str = "nous"
    base_url: str = "https://portal.nousresearch.com/v1"
    api_key_env: str = "NOUS_API_KEY"
    model: str = "stepfun/step-3.7-flash"
    timeout_seconds: int = 45
    summary_model: str = "stepfun/step-3.7-flash"


class BlofinRestConfig(BaseModel):
    tickers: str = "/api/v1/market/tickers"
    candles: str = "/api/v1/market/candles"
    balances: str = "/api/v1/asset/balances"
    positions: str = "/api/v1/account/positions"
    order: str = "/api/v1/trade/order"


class BlofinConfig(BaseModel):
    credential_file: str = Field(default=r"C:\Users\mknig\Downloads\1B Blofin API New.txt")
    base_url: str = "https://api.blofin.com"
    broker_id: str = "5388cb1f"
    rest: BlofinRestConfig = Field(default_factory=BlofinRestConfig)


class RiskConfig(BaseModel):
    risk_per_trade_pct: float = 0.01
    leverage: int = 10
    stop_loss_pct: float = 0.03
    take_profit_pct: float = 0.25
    max_positions: int = 15
    max_margin_util_pct: float = 0.85


class JournalConfig(BaseModel):
    path: str = "data/journal.sqlite"
    summary_refresh_ticks: int = 60
    summary_window_trades: int = 30


class AxiomSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
    )
    mode: str = "demo"
    loop: LoopConfig = Field(default_factory=LoopConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    blofin: BlofinConfig = Field(default_factory=BlofinConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    journal: JournalConfig = Field(default_factory=JournalConfig)

    @classmethod
    def from_yaml(cls, path: str | Path, dotenv_path: str | Path = Path(".env")) -> AxiomSettings:
        raw = _load_yaml(path)
        return cls(**raw)

    def api_key(self) -> str:
        key = os.getenv(self.model.api_key_env)
        if not key:
            raise ValueError(f"Missing {self.model.api_key_env}")
        return key

    def credentials(self) -> Credentials:
        return Credentials.from_text(self.blofin.credential_file)


def blofin_sign(secret: str, timestamp: str, method: str, path: str, body: str = "") -> str:
    message = f"{timestamp}{method.upper()}{path}{body}"
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


class BlofinRequest(BaseModel):
    method: str = "GET"
    path: str = "/api/v1/market/tickers"
    params: dict[str, Any] | None = None
    body: dict[str, Any] | None = None
    sign: bool = True


settings = AxiomSettings.from_yaml(Path(__file__).resolve().parents[1] / "config.yaml")
