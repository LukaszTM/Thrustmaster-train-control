"""Runtime side of the Xbox-emulation mode.

Feeds PadState (from xboxmap) into a virtual Xbox 360 controller
created by the ViGEmBus driver via the `vgamepad` library.

Requirements (Windows only):
  1. ViGEmBus driver: https://github.com/nefarius/ViGEmBus/releases
  2. pip install vgamepad
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from .xboxmap import PadState, XboxProfile

if TYPE_CHECKING:
    from .joystick import Device


class BasePad:
    def apply(self, state: PadState) -> None:
        raise NotImplementedError

    def reset(self) -> None:
        self.apply(PadState())


class DryRunPad(BasePad):
    """Prints state changes instead of emulating a pad."""

    def __init__(self) -> None:
        self._last: PadState | None = None

    def apply(self, state: PadState) -> None:
        if self._last is not None and state == self._last:
            return
        sticks = "  ".join(f"{k}:{v:+6d}" for k, v in state.sticks.items())
        triggers = "  ".join(f"{k}:{v:3d}" for k, v in state.triggers.items())
        buttons = ",".join(sorted(state.buttons)) or "-"
        print(f"[dry-run] {sticks}  {triggers}  buttons: {buttons}")
        self._last = PadState(dict(state.sticks), dict(state.triggers),
                              set(state.buttons))


class VigemPad(BasePad):
    """Real virtual Xbox 360 pad through ViGEmBus."""

    def __init__(self) -> None:
        try:
            import vgamepad as vg
        except ImportError as exc:
            raise RuntimeError(
                "The 'vgamepad' package is not installed. Run: pip install vgamepad "
                "(and install the ViGEmBus driver: "
                "https://github.com/nefarius/ViGEmBus/releases)"
            ) from exc
        self.vg = vg
        try:
            self.pad = vg.VX360Gamepad()
        except Exception as exc:
            raise RuntimeError(
                f"Could not create a virtual Xbox pad ({exc}). "
                "Is the ViGEmBus driver installed?"
            ) from exc
        B = vg.XUSB_BUTTON
        self.button_codes = {
            "a": B.XUSB_GAMEPAD_A, "b": B.XUSB_GAMEPAD_B,
            "x": B.XUSB_GAMEPAD_X, "y": B.XUSB_GAMEPAD_Y,
            "lb": B.XUSB_GAMEPAD_LEFT_SHOULDER,
            "rb": B.XUSB_GAMEPAD_RIGHT_SHOULDER,
            "back": B.XUSB_GAMEPAD_BACK, "start": B.XUSB_GAMEPAD_START,
            "guide": B.XUSB_GAMEPAD_GUIDE,
            "ls": B.XUSB_GAMEPAD_LEFT_THUMB, "rs": B.XUSB_GAMEPAD_RIGHT_THUMB,
            "dpad_up": B.XUSB_GAMEPAD_DPAD_UP,
            "dpad_down": B.XUSB_GAMEPAD_DPAD_DOWN,
            "dpad_left": B.XUSB_GAMEPAD_DPAD_LEFT,
            "dpad_right": B.XUSB_GAMEPAD_DPAD_RIGHT,
        }
        self._pressed: set[str] = set()

    def apply(self, state: PadState) -> None:
        self.pad.left_joystick(x_value=state.sticks["left_stick_x"],
                               y_value=state.sticks["left_stick_y"])
        self.pad.right_joystick(x_value=state.sticks["right_stick_x"],
                                y_value=state.sticks["right_stick_y"])
        self.pad.left_trigger(value=state.triggers["left_trigger"])
        self.pad.right_trigger(value=state.triggers["right_trigger"])
        for name in state.buttons - self._pressed:
            self.pad.press_button(button=self.button_codes[name])
        for name in self._pressed - state.buttons:
            self.pad.release_button(button=self.button_codes[name])
        self._pressed = set(state.buttons)
        self.pad.update()


def make_pad(dry_run: bool = False) -> BasePad:
    if dry_run:
        return DryRunPad()
    return VigemPad()


def run_xbox_loop(profile: XboxProfile, device: "Device", pad: BasePad) -> None:
    interval = 1.0 / profile.poll_hz
    print(f"Connected: {device.name} "
          f"({device.num_axes} axes, {device.num_buttons} buttons)")
    print("Virtual Xbox 360 pad active. Ctrl+C to stop.")
    try:
        while True:
            axes, buttons = device.poll()
            pad.apply(profile.compute(axes, buttons))
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        pad.reset()
