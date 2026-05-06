"""CLI entry: `python -m claude_streamdeck`."""

import argparse
import asyncio
import logging
import signal
from pathlib import Path

from .config import load_config
from .daemon import Daemon


def _setup_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("StreamDeck").setLevel(logging.WARNING)


async def _run(config_path: Path | None) -> None:
    cfg = load_config(config_path)
    daemon = Daemon(cfg)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await daemon.start()
    try:
        await stop.wait()
    finally:
        await daemon.stop()


def main() -> None:
    parser = argparse.ArgumentParser(prog="claude-streamdeck")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    _setup_logging(args.debug)
    asyncio.run(_run(args.config))


if __name__ == "__main__":
    main()
