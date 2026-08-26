"""Main run loop: joystick -> mapping -> key events."""

from __future__ import annotations

import time
from collections import deque
from typing import TYPE_CHECKING

from .config import Profile
from .keysender import BaseSender

if TYPE_CHECKING:  # pygame is only needed at runtime by joystick.py
    from .joystick import Device


class TapQueue:
    """Paces key taps so the game registers each one separately."""

    def __init__(self, sender: BaseSender, tap_ms: int, gap_ms: int) -> None:
        self.sender = sender
        self.tap_s = tap_ms / 1000.0
        self.gap_s = gap_ms / 1000.0
        self.queue: deque[str] = deque()
        self._pressed_key: str | None = None
        self._next_action_at = 0.0

    def add(self, key: str) -> None:
        self.queue.append(key)

    def tick(self, now: float) -> None:
        if now < self._next_action_at:
            return
        if self._pressed_key is not None:
            self.sender.release(self._pressed_key)
            self._pressed_key = None
            self._next_action_at = now + self.gap_s
            return
        if self.queue:
            key = self.queue.popleft()
            self.sender.press(key)
            self._pressed_key = key
            self._next_action_at = now + self.tap_s

    @property
    def busy(self) -> bool:
        return bool(self.queue) or self._pressed_key is not None


class HoldManager:
    """Keeps the set of held keys in sync with what mappings request."""

    def __init__(self, sender: BaseSender) -> None:
        self.sender = sender
        self.held: set[str] = set()

    def apply(self, wanted: set[str]) -> None:
        for key in self.held - wanted:
            self.sender.release(key)
        for key in wanted - self.held:
            self.sender.press(key)
        self.held = set(wanted)

    def release_all(self) -> None:
        self.apply(set())


def run_loop(profile: Profile, device: Device, sender: BaseSender,
             verbose: bool = False) -> None:
    taps = TapQueue(sender, profile.key_tap_ms, profile.key_gap_ms)
    holds = HoldManager(sender)
    notched_by_name = {ax.name: ax for ax in profile.notched_axes.values()}
    interval = 1.0 / profile.poll_hz

    print(f"Connected: {device.name} "
          f"({device.num_axes} axes, {device.num_buttons} buttons)")
    print("Mapping active. Ctrl+C to stop.")
    try:
        while True:
            now = time.monotonic()
            axes, buttons = device.poll()

            wanted_holds: set[str] = set()

            for axis_id, mapper in profile.notched_axes.items():
                if axis_id >= len(axes):
                    continue
                for tap in mapper.update(axes[axis_id]):
                    taps.add(tap.key)
                    if verbose:
                        print(f"{mapper.name}: notch -> {mapper.current_notch} "
                              f"(tap {tap.key})")

            for axis_id, mapper in profile.zones_axes.items():
                if axis_id >= len(axes):
                    continue
                key = mapper.update(axes[axis_id])
                if key:
                    wanted_holds.add(key)

            for mapping in profile.buttons:
                if mapping.button >= len(buttons):
                    continue
                result = mapping.update(buttons[mapping.button])
                for key in result["taps"]:
                    taps.add(key)
                    if verbose:
                        print(f"{mapping.name}: tap {key}")
                if result["hold"]:
                    wanted_holds.add(result["hold"])
                if result["resync"]:
                    axis_name, notch = result["resync"]
                    target = notched_by_name.get(axis_name)
                    if target:
                        target.resync(notch)
                        print(f"{mapping.name}: resync '{axis_name}' -> notch {notch}")

            holds.apply(wanted_holds)
            taps.tick(now)

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        holds.release_all()
        sender.release_all()


def monitor_loop(device: Device) -> None:
    """Live view of axes and buttons (the 'list' command)."""
    print(f"Device: {device.name}")
    print("Move levers / press buttons to identify their numbers. Ctrl+C to stop.\n")
    try:
        while True:
            axes, buttons = device.poll()
            axes_str = "  ".join(f"a{i}:{v:+.2f}" for i, v in enumerate(axes))
            pressed = [str(i) for i, b in enumerate(buttons) if b]
            buttons_str = ",".join(pressed) if pressed else "-"
            print(f"\r{axes_str}  |  buttons: {buttons_str}   ", end="", flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nDone.")


def calibrate(profile: Profile, device: Device) -> None:
    """Interactive calibration wizard; writes results back to the profile."""
    from .mapping import Calibration

    axis_ids = sorted(set(profile.notched_axes) | set(profile.zones_axes))
    if not axis_ids:
        print("No axes configured in this profile - nothing to calibrate.")
        return

    names = {**{i: m.name for i, m in profile.notched_axes.items()},
             **{i: m.name for i, m in profile.zones_axes.items()}}
    results: dict[int, Calibration] = {}

    print(f"Device: {device.name}")
    print("Calibration: for each axis, move the lever through its FULL range,")
    print("then leave it at the MINIMUM position (idle / released) and press Enter.\n")

    for axis_id in axis_ids:
        input(f"Axis {axis_id} ({names[axis_id]}): press Enter to start recording...")
        print("  Recording for 5 seconds - move the lever fully both ways,")
        print("  then hold it at the MINIMUM (idle) position.")
        lo, hi = 1.0, -1.0
        end = time.monotonic() + 5.0
        last = 0.0
        while time.monotonic() < end:
            axes, _ = device.poll()
            if axis_id < len(axes):
                last = axes[axis_id]
                lo = min(lo, last)
                hi = max(hi, last)
            time.sleep(0.01)
        if hi - lo < 0.1:
            print(f"  WARNING: axis {axis_id} barely moved ({lo:+.2f}..{hi:+.2f}); "
                  "skipping.")
            continue
        # If the resting (minimum) position reads near the recorded high end,
        # the axis is inverted.
        invert = abs(last - hi) < abs(last - lo)
        results[axis_id] = Calibration(min=lo, max=hi, invert=invert)
        print(f"  OK: min={lo:+.3f} max={hi:+.3f} invert={invert}\n")

    if results:
        profile.save_calibration(results)
        print(f"Calibration saved to {profile.path}")
    else:
        print("Nothing recorded; profile unchanged.")
