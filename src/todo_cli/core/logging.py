"""Shared logging setup helpers."""

import logging


def configure_logging(verbose: bool = False) -> None:
    """Configure root logging level and format once for CLI/API entrypoints."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
