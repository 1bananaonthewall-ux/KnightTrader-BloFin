"""`python -m emirald` entrypoint.

Wires up logging from config.yaml, loads secrets + config, starts the loop.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from rich.logging import RichHandler

from .config import LoggingConfig, load_all
from .loop import EmiraldLoop


def _setup_logging(cfg: LoggingConfig) -> None:
    log_path = Path(cfg.file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handlers: list[logging.Handler] = [
        RichHandler(rich_tracebacks=True, show_path=False, show_time=True),
        logging.FileHandler(log_path, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=getattr(logging, cfg.level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
    # Quiet noisy third-party libs.
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.INFO)


def main() -> int:
    # Windows consoles default to cp1252; force UTF-8 so playbook text can't crash Rich.
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    try:
        secrets, config = load_all("config.yaml")
    except Exception as e:  # noqa: BLE001
        print(f"Failed to load config: {e}", file=sys.stderr)
        print("Did you copy .env.example to .env and fill in the keys?", file=sys.stderr)
        return 2

    _setup_logging(config.logging)

    loop = EmiraldLoop(secrets, config)
    try:
        loop.startup()
    except Exception as e:  # noqa: BLE001
        logging.getLogger(__name__).exception("startup failed: %s", e)
        return 1

    loop.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
