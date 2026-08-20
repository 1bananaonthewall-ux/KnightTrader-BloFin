"""Configuration loading: .env for secrets, config.yaml for behavior."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# --- Secrets (loaded from .env) --------------------------------------------- #


class Secrets(BaseSettings):
    """API credentials. Loaded from .env. Never logged.

    Project `.env` wins over ambient Windows/user environment variables so a
    leftover BLOFIN_* in the user profile cannot silently override the
    credentials file we just wrote for this stack.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    blofin_api_key: str = Field(..., alias="BLOFIN_API_KEY")
    blofin_api_secret: str = Field(..., alias="BLOFIN_API_SECRET")
    blofin_passphrase: str = Field(default="", alias="BLOFIN_PASSPHRASE")
    # Required when the API key is bound to a BloFin third-party application.
    blofin_broker_id: str = Field(default="", alias="BLOFIN_BROKER_ID")
    nous_portal_key: str = Field(..., alias="NOUS_PORTAL_KEY")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # Prefer .env over process environment.
        return init_settings, dotenv_settings, env_settings, file_secret_settings


# --- Behavior (loaded from config.yaml) ------------------------------------- #


class LoopConfig(BaseModel):
    interval_seconds: int = 60
    jitter_seconds: int = 5


class LLMConfig(BaseModel):
    model: str = "stepfun/step-3.7-flash:free"
    base_url: str = "https://inference-api.nousresearch.com/v1"
    timeout_seconds: int = 45
    reasoning_effort: Literal["low", "medium", "high"] = "medium"
    max_output_tokens: int = 2000


class JournalConfig(BaseModel):
    verbatim_window: int = 30
    summary_refresh_every_ticks: int = 60
    db_path: str = "./data/journal.sqlite"


class RiskConfig(BaseModel):
    """Per user decision: enabled is false and the risk_none module is wired
    in. This struct exists so swapping in a real risk.py is a one-line change.
    """

    enabled: bool = False


class PaperConfig(BaseModel):
    starting_equity: float = 40.0
    state_path: str = "./data/paper_state.json"
    reset_on_start: bool = True
    top_n: int = 40  # candles in prompt; tickers still cover full universe


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: str = "./data/hermes.log"


class AppConfig(BaseModel):
    exchange: Literal["blofin"] = "blofin"
    mode: Literal["isolated", "cross", "cash"] = "isolated"
    universe: str = "all_usdt_perps"
    trading_mode: Literal["live", "demo"] = "demo"

    loop: LoopConfig = LoopConfig()
    llm: LLMConfig = LLMConfig()
    journal: JournalConfig = JournalConfig()
    risk: RiskConfig = RiskConfig()
    paper: PaperConfig = PaperConfig()
    logging: LoggingConfig = LoggingConfig()

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AppConfig":
        import yaml

        text = Path(path).read_text(encoding="utf-8")
        data = yaml.safe_load(text) or {}
        return cls.model_validate(data)


def load_all(yaml_path: str | Path = "config.yaml") -> tuple[Secrets, AppConfig]:
    """Load both. Secrets come from .env, behavior from yaml."""
    secrets = Secrets()  # type: ignore[call-arg]
    config = AppConfig.from_yaml(yaml_path)
    return secrets, config
