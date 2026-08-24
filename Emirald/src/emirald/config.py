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
    nous_portal_keys: list[str] = Field(default_factory=list, alias="NOUS_PORTAL_KEYS")

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
    file: str = "./data/emirald.log"


class BlofinConfig(BaseModel):
    credential_file: str = r"C:\Users\mknig\Downloads\1B Blofin API New.txt"


class AppConfig(BaseModel):
    exchange: Literal["blofin"] = "blofin"
    mode: Literal["isolated", "cross", "cash"] = "isolated"
    position_mode: Literal["net", "hedge"] = "net"
    universe: str = "all_usdt_perps"
    trading_mode: Literal["live", "demo"] = "demo"

    blofin: BlofinConfig = Field(default_factory=BlofinConfig)
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
    root = Path(yaml_path).resolve().parent
    dotenv_path = root / ".env"
    if dotenv_path.is_file():
        try:
            from dotenv import load_dotenv

            load_dotenv(dotenv_path, override=True)
        except Exception:
            pass
    secrets = Secrets()  # type: ignore[call-arg]

    extra_key_files = [
        Path("C:/Users/mknig/OneDrive/Documents/Nous API Key 2.txt"),
        Path("C:/Users/mknig/OneDrive/Documents/Nous API Key 3.txt"),
        Path("C:/Users/mknig/OneDrive/Documents/Nous API Key 4.txt"),
        Path("C:/Users/mknig/OneDrive/Documents/Nous API Key Stepfun.txt"),
    ]
    extra_keys: list[str] = []
    for p in extra_key_files:
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("sk-nous-"):
                extra_keys.append(line)
    seen: set[str] = {secrets.nous_portal_key}
    deduped: list[str] = [secrets.nous_portal_key]
    for k in extra_keys:
        if k not in seen:
            seen.add(k)
            deduped.append(k)
    if deduped:
        secrets = secrets.model_copy(update={"nous_portal_keys": deduped})

    config = AppConfig.from_yaml(yaml_path)
    return secrets, config
