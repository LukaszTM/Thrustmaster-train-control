"""Keyboard output via Windows SendInput with hardware scancodes.

SimRail (like most games) reads keyboard state through DirectInput /
Raw Input, which ignores plain virtual-key events. Sending events with
KEYEVENTF_SCANCODE makes them look like real hardware key presses.

On non-Windows platforms (or with --dry-run) a printing stub is used so
the mapping logic can be developed and tested anywhere.
"""

from __future__ import annotations

import sys
import time

# Scan codes (set 1, "make" codes) for the keys SimRail typically uses.
# Names are what appears in config files.
SCANCODES = {
    "esc": 0x01,
    "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06,
    "6": 0x07, "7": 0x08, "8": 0x09, "9": 0x0A, "0": 0x0B,
    "minus": 0x0C, "equals": 0x0D, "backspace": 0x0E, "tab": 0x0F,
    "q": 0x10, "w": 0x11, "e": 0x12, "r": 0x13, "t": 0x14,
    "y": 0x15, "u": 0x16, "i": 0x17, "o": 0x18, "p": 0x19,
    "lbracket": 0x1A, "rbracket": 0x1B, "enter": 0x1C, "lctrl": 0x1D,
    "a": 0x1E, "s": 0x1F, "d": 0x20, "f": 0x21, "g": 0x22,
    "h": 0x23, "j": 0x24, "k": 0x25, "l": 0x26,
    "semicolon": 0x27, "apostrophe": 0x28, "grave": 0x29,
    "lshift": 0x2A, "backslash": 0x2B,
    "z": 0x2C, "x": 0x2D, "c": 0x2E, "v": 0x2F, "b": 0x30,
    "n": 0x31, "m": 0x32, "comma": 0x33, "period": 0x34, "slash": 0x35,
    "rshift": 0x36, "num_multiply": 0x37, "lalt": 0x38, "space": 0x39,
    "capslock": 0x3A,
    "f1": 0x3B, "f2": 0x3C, "f3": 0x3D, "f4": 0x3E, "f5": 0x3F,
    "f6": 0x40, "f7": 0x41, "f8": 0x42, "f9": 0x43, "f10": 0x44,
    "f11": 0x57, "f12": 0x58,
    "numlock": 0x45, "scrolllock": 0x46,
    "num7": 0x47, "num8": 0x48, "num9": 0x49, "num_subtract": 0x4A,
    "num4": 0x4B, "num5": 0x4C, "num6": 0x4D, "num_add": 0x4E,
    "num1": 0x4F, "num2": 0x50, "num3": 0x51, "num0": 0x52,
    "num_decimal": 0x53,
    # Extended keys (E0 prefix)
    "num_enter": 0x1C, "rctrl": 0x1D, "num_divide": 0x35, "ralt": 0x38,
    "home": 0x47, "up": 0x48, "pageup": 0x49,
    "left": 0x4B, "right": 0x4D,
    "end": 0x4F, "down": 0x50, "pagedown": 0x51,
    "insert": 0x52, "delete": 0x53,
}

EXTENDED_KEYS = {
    "num_enter", "rctrl", "num_divide", "ralt",
    "home", "up", "pageup", "left", "right",
    "end", "down", "pagedown", "insert", "delete",
}


def validate_key(name: str) -> None:
    if name not in SCANCODES:
        known = ", ".join(sorted(SCANCODES))
        raise ValueError(f"Unknown key name '{name}'. Known keys: {known}")


class BaseSender:
    """Interface: press/release keys by config name."""

    def press(self, key: str) -> None:
        raise NotImplementedError

    def release(self, key: str) -> None:
        raise NotImplementedError

    def tap(self, key: str, duration_s: float = 0.04) -> None:
        self.press(key)
        time.sleep(duration_s)
        self.release(key)

    def release_all(self) -> None:
        pass


class DryRunSender(BaseSender):
    """Prints key events instead of sending them (testing / non-Windows)."""

    def __init__(self, log=print) -> None:
        self.held: set[str] = set()
        self.log = log

    def press(self, key: str) -> None:
        validate_key(key)
        self.held.add(key)
        self.log(f"[dry-run] press   {key}")

    def release(self, key: str) -> None:
        self.held.discard(key)
        self.log(f"[dry-run] release {key}")

    def release_all(self) -> None:
        for key in list(self.held):
            self.release(key)


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    ULONG_PTR = ctypes.POINTER(ctypes.c_ulong)
    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008
    KEYEVENTF_EXTENDEDKEY = 0x0001

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = (
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        )

    class _INPUTUNION(ctypes.Union):
        _fields_ = (("ki", _KEYBDINPUT),)

    class _INPUT(ctypes.Structure):
        _fields_ = (
            ("type", wintypes.DWORD),
            ("union", _INPUTUNION),
        )

    class WindowsSender(BaseSender):
        def __init__(self) -> None:
            self._send_input = ctypes.windll.user32.SendInput
            self.held: set[str] = set()

        def _send(self, key: str, keyup: bool) -> None:
            validate_key(key)
            flags = KEYEVENTF_SCANCODE
            if key in EXTENDED_KEYS:
                flags |= KEYEVENTF_EXTENDEDKEY
            if keyup:
                flags |= KEYEVENTF_KEYUP
            ki = _KEYBDINPUT(0, SCANCODES[key], flags, 0, None)
            inp = _INPUT(INPUT_KEYBOARD, _INPUTUNION(ki))
            self._send_input(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))

        def press(self, key: str) -> None:
            self._send(key, keyup=False)
            self.held.add(key)

        def release(self, key: str) -> None:
            self._send(key, keyup=True)
            self.held.discard(key)

        def release_all(self) -> None:
            for key in list(self.held):
                self.release(key)


def make_sender(dry_run: bool = False, log=print) -> BaseSender:
    if dry_run or sys.platform != "win32":
        return DryRunSender(log=log)
    return WindowsSender()
