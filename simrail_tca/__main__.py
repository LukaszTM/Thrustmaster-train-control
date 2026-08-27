"""Command line interface.

Usage:
    python -m simrail_tca gui
    python -m simrail_tca devices
    python -m simrail_tca monitor  [--config config/bez-ed.json]
    python -m simrail_tca calibrate --config config/bez-ed.json
    python -m simrail_tca run      --config config/z-ed.json [--dry-run] [-v]
"""

from __future__ import annotations

import argparse
import sys

from .config import ConfigError, load_profile, load_xbox_profile
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

    sub.add_parser("gui", help="Open the graphical interface")

    p_xbox = sub.add_parser(
        "xbox",
        help="Emulate a virtual Xbox 360 pad (ViGEmBus) fed by the TCA",
    )
    p_xbox.add_argument("--config", default="config/xbox.json")
    p_xbox.add_argument("--dry-run", action="store_true",
                        help="Print pad state instead of emulating a pad")

    args = parser.parse_args(argv)

    try:
        if args.command == "gui":
            from .gui import main as gui_main
            return gui_main()
        if args.command == "devices":
            from .joystick import list_devices
            devices = list_devices()
            if not devices:
                print("No game controllers detected.")
            for i, name in enumerate(devices):
                print(f"[{i}] {name}")
            return 0

        profile = (load_profile(args.config)
                   if args.command in ("monitor", "calibrate", "run") else None)

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
        elif args.command == "xbox":
            from .joystick import open_device
            from .xboxpad import make_pad, run_xbox_loop
            xprofile = load_xbox_profile(args.config)
            device = open_device(xprofile.device_name_contains,
                                 xprofile.device_index)
            if args.dry_run:
                print("DRY RUN: pad state is printed, no virtual pad created.")
            run_xbox_loop(xprofile, device, make_pad(dry_run=args.dry_run))
        return 0
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # joystick errors etc.
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
