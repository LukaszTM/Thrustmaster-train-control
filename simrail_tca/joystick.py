"""Thin wrapper around pygame's joystick module."""

from __future__ import annotations

import os
from typing import Optional

# Allow pygame to see joysticks without an open window / while the game
# window has focus.
os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402


class JoystickError(Exception):
    pass


def _init() -> None:
    if not pygame.get_init():
        pygame.init()
    if not pygame.joystick.get_init():
        pygame.joystick.init()


def list_devices() -> list[str]:
    _init()
    names = []
    for i in range(pygame.joystick.get_count()):
        names.append(pygame.joystick.Joystick(i).get_name())
    return names


class Device:
    def __init__(self, joystick: "pygame.joystick.JoystickType") -> None:
        self.js = joystick
        self.js.init()
        self.name = self.js.get_name()
        self.num_axes = self.js.get_numaxes()
        self.num_buttons = self.js.get_numbuttons()

    def poll(self) -> tuple[list[float], list[bool]]:
        """Pump events and return (axes, buttons) snapshots."""
        pygame.event.pump()
        axes = [self.js.get_axis(i) for i in range(self.num_axes)]
        buttons = [bool(self.js.get_button(i)) for i in range(self.num_buttons)]
        return axes, buttons


def open_device(name_contains: str = "", index: Optional[int] = None) -> Device:
    _init()
    count = pygame.joystick.get_count()
    if count == 0:
        raise JoystickError(
            "No joystick detected. Connect the Thrustmaster TCA and try again."
        )
    if index is not None:
        if not 0 <= index < count:
            raise JoystickError(f"Device index {index} out of range (found {count}).")
        return Device(pygame.joystick.Joystick(index))
    if name_contains:
        needle = name_contains.lower()
        for i in range(count):
            js = pygame.joystick.Joystick(i)
            if needle in js.get_name().lower():
                return Device(js)
        names = ", ".join(f"[{i}] {n}" for i, n in enumerate(list_devices()))
        raise JoystickError(
            f"No device matching '{name_contains}'. Detected: {names}. "
            "Set device.name_contains or device.index in the config."
        )
    return Device(pygame.joystick.Joystick(0))
