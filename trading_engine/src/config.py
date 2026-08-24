from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class TradingConfig(BaseModel):
    mode: str = "demo"
    loop_interval_seconds: int = 60
    loop_jitter_seconds: int = 3
    max_decisions_per_tick: int = 5


class ModelConfig(BaseModel):
    provider: str = "nous_portal"
    api_key: str = ""
    base_url: str = "https://portal.nousresearch.com/v1"
    model: str = "stepfun/step-3.7-flash"
    timeout_seconds: int = 45
    cheap_model: str = "stepfun/step-3.7-flash"


class RiskConfig(BaseModel):
    risk_per_trade_pct: float = 0.01
    leverage: int = 10
    stop_loss_pct: float = 0.03
    take_profit_pct: float = 0.25
    max_positions: int = 15
    max_margin_util_pct: float = 0.85


class BlofinConfig(BaseModel):
    api_key: str = ""
    secret_key: str = ""
    passphrase: str = ""
    credential_file: str = r"C:\Users\mknig\Downloads\1B Blofin API New.txt"
    rest_base: str = "https://api.blofin.com"
    broker_id: str = "5388cb1f"
    universe_refresh_minutes: int = 60


class JournalConfig(BaseModel):
    path: str = "data/journal.sqlite"
    summary_compress_every_n_ticks: int = 60
    summary_compress_after_ticks: int = 30


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080
    reload: bool = False


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    trading: TradingConfig = Field(default_factory=TradingConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    blofin: BlofinConfig = Field(default_factory=BlofinConfig)
    journal: JournalConfig = Field(default_factory=JournalConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)

    @classmethod
    def load(cls, yaml_path: str | Path = "config.yaml") -> AppConfig:
        data = _load_yaml(yaml_path)
        trading = TradingConfig(**data.get("trading", {}))
        model = ModelConfig(**data.get("model", {}))
        risk = RiskConfig(**data.get("risk", {}))
        blofin = BlofinConfig(**data.get("blofin", {}))
        journal = JournalConfig(**data.get("journal", {}))
        server = ServerConfig(**data.get("server", {}))
        return cls(
            trading=trading,
            model=model,
            risk=risk,
            blofin=blofin,
            journal=journal,
            server=server,
        )
