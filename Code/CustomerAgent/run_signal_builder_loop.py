"""Run the signal builder on a continuous timer loop.

Usage:
    python run_signal_builder_loop.py [--interval 60]

Polls every --interval seconds (default: reads poll_interval_minutes from
config/monitoring_context.json). When signals activate, triggers the full
investigation pipeline.

Press Ctrl+C to stop.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("run_signal_builder_loop")


async def main(interval: int | None) -> None:
    from core.services.signals.signal_builder import run_signal_builder_loop
    from core.services.investigation.investigation_runner import on_group_chat_callback

    logger.info(
        "Starting signal builder loop%s. Press Ctrl+C to stop.",
        f" (interval={interval}s)" if interval else "",
    )

    await run_signal_builder_loop(
        on_group_chat=on_group_chat_callback,
        poll_override_seconds=interval,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run signal builder on a timer loop")
    parser.add_argument(
        "--interval", type=int, default=None,
        help="Poll interval in seconds (default: from monitoring_context.json)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(args.interval))
    except KeyboardInterrupt:
        logger.info("Signal builder loop stopped.")
