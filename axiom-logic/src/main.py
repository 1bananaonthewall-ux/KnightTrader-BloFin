from __future__ import annotations

import os
import sys
import uvicorn
from pathlib import Path

from .config import settings
from .loop import AxiomLoop

loop = AxiomLoop(mode=os.getenv("AXIOM_MODE", settings.mode))


def main() -> int:
    host = os.getenv("AXIOM_HOST", "0.0.0.0")
    port = int(os.getenv("AXIOM_PORT", "8080"))
    reload = os.getenv("AXIOM_RELOAD", "0") == "1"
    config = uvicorn.Config(
        "axiom_logic.src.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
    server = uvicorn.Server(config)
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
