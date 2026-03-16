#!/usr/bin/env python3
"""Start the FastAPI server."""
import uvicorn

from core.config.settings import settings
from core.shared_tools.structured_logging import configure_logging


def main() -> None:
    # Early init — captures Uvicorn startup logs before lifespan runs
    configure_logging(
        level=settings.log_level,
        log_format=settings.log_format,
        include_caller=settings.log_include_caller,
        database_echo=settings.database_echo,
    )

    uvicorn.run(
        "api.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_config=None,  # Disable Uvicorn's default logging — we own it
    )


if __name__ == "__main__":
    main()
