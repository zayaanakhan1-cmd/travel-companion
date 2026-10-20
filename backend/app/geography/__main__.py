"""Build the open-dataset cache from the command line.

Usage:
    python -m app.geography.dataset_builder
"""

from __future__ import annotations

import sys

from app.config import get_settings
from app.geography.dataset_builder import build_cache
from app.logging_config import configure_logging


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level, settings.secret_values())
    destination = settings.cache_file
    print(f"Building open geography cache at {destination} ...")
    build_cache(
        url=settings.open_dataset_url,
        destination=destination,
        timeout=settings.open_dataset_download_timeout,
    )
    print(f"Done. Cache size: {destination.stat().st_size / 1_000_000:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
