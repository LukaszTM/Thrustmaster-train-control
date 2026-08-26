"""Command line interface.

Usage:
    python -m simrail_tca devices
    python -m simrail_tca monitor  [--config config/bez-ed.json]
    python -m simrail_tca calibrate --config config/bez-ed.json
    python -m simrail_tca run      --config config/z-ed.json [--dry-run] [-v]
"""

from __future__ import annotations

import argparse
import sys

from .config import ConfigError, load_profile
from .keysender import make_sender

DEFAULT_CONFIG = "config/bez-ed.json"


def _open_from_profile(profile) -> "object":
    from .joystick import open_device
    return open_device(profile.device_name_contains, profile.device_index)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="simrail_tca",
        description="Drive SimRail trains with a Thrustmaster TCA throttle.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("devices", help="List connected game controllers")

    p_monitor = sub.add_parser("monitor", help="Live view of axes and buttons")
    p_monitor.add_argument("--config", default=DEFAULT_CONFIG)

    p_cal = sub.add_parser("calibrate", help="Record axis ranges into the profile")
    p_cal.add_argument("--config", default=DEFAULT_CONFIG)

    p_run = sub.add_parser("run", help="Start mapping joystick to SimRail keys")
    p_run.add_argument("--config", default=DEFAULT_CONFIG)
    p_run.add_argument("--dry-run", action="store_true",
                       help="Print key events instead of sending them")
    p_run.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args(argv)

    try:
        if args.command == "devices":
            from .joystick import list_devices
            devices = list_devices()
            if not devices:
                print("No game controllers detected.")
            for i, name in enumerate(devices):
                print(f"[{i}] {name}")
            return 0

        profile = load_profile(args.config) if args.command != "devices" else None

        if args.command == "monitor":
            from .app import monitor_loop
            monitor_loop(_open_from_profile(profile))
        elif args.command == "calibrate":
            from .app import calibrate
            calibrate(profile, _open_from_profile(profile))
        elif args.command == "run":
            from .app import run_loop
            sender = make_sender(dry_run=args.dry_run)
            if args.dry_run:
                print("DRY RUN: key events are printed, not sent.")
            run_loop(profile, _open_from_profile(profile), sender,
                     verbose=args.verbose)
        return 0
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # joystick errors etc.
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
