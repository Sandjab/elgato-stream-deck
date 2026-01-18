"""Entry point for Claude Code Stream Deck daemon.

Run with: python -m claude_streamdeck
"""

import argparse
import sys

from .daemon import run_daemon


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Claude Code Stream Deck XL Daemon",
        prog="claude_streamdeck"
    )

    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    parser.add_argument(
        "-v", "--version",
        action="store_true",
        help="Show version and exit"
    )

    args = parser.parse_args()

    if args.version:
        from . import __version__
        print(f"claude_streamdeck {__version__}")
        return 0

    run_daemon(debug=args.debug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
