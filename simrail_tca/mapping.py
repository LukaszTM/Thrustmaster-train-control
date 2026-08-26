"""Pure mapping logic: joystick axis/button values -> key actions.

No pygame or OS dependencies here so everything is unit-testable.

Axis modes
----------
notched:
    The axis is divided into N discrete positions (like a real train
    master controller). The mapper tracks the notch it believes the
    in-game lever is at and emits one key tap per notch of difference.
    SimRail gives no feedback, so this is open loop: start the session
    with the in-game lever at position 0 (or use a resync button).

zones:
    The axis is divided into ranges; while the axis sits inside a range
    its key is held down. Useful for "hold to apply brake / hold to
    release" style controls: the lever acts as a rate command.

Buttons
-------
tap:    press+release once per button press.
hold:   key held while the button is held (horn, sander).
switch: one key tapped when the switch turns on, another when it turns
        off (pantograph up/down on a TCA toggle switch).
resync: resets a notched axis' internal state to a given notch without
        sending keys (to re-align with the game).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Calibration:
    min: float = -1.0
    max: float = 1.0
    invert: bool = False

    def normalize(self, raw: float) -> float:
        """Map a raw axis reading to 0.0..1.0."""
        span = self.max - self.min
        if span <= 0:
            return 0.0
        value = (raw - self.min) / span
        value = min(1.0, max(0.0, value))
        return 1.0 - value if self.invert else value


@dataclass
class Tap:
    key: str


@dataclass
class NotchedAxis:
    """Open-loop notch follower with boundary hysteresis."""

    name: str
    positions: int
    increase_key: str
    decrease_key: str
    calibration: Calibration = field(default_factory=Calibration)
    hysteresis: float = 0.15  # fraction of one notch width
    current_notch: int = 0

    def resync(self, notch: int = 0) -> None:
        self.current_notch = max(0, min(self.positions - 1, notch))

    def update(self, raw: float) -> list[Tap]:
        """Feed a raw axis value, get the key taps needed to follow it."""
        if self.positions < 2:
            return []
        value = self.calibration.normalize(raw)
        notch_width = 1.0 / (self.positions - 1)
        taps: list[Tap] = []
        # Walk one notch at a time; hysteresis keeps jittery values from
        # bouncing across a boundary.
        while True:
            up_threshold = (self.current_notch + 0.5 + self.hysteresis) * notch_width
            down_threshold = (self.current_notch - 0.5 - self.hysteresis) * notch_width
            if value > up_threshold and self.current_notch < self.positions - 1:
                self.current_notch += 1
                taps.append(Tap(self.increase_key))
            elif value < down_threshold and self.current_notch > 0:
                self.current_notch -= 1
                taps.append(Tap(self.decrease_key))
            else:
                break
        return taps


@dataclass
class Zone:
    start: float
    end: float
    key: Optional[str]  # None = dead zone, no key held


@dataclass
class ZonesAxis:
    """While the axis is inside a zone, that zone's key is held."""

    name: str
    zones: list[Zone]
    calibration: Calibration = field(default_factory=Calibration)
    margin: float = 0.02  # hysteresis at zone edges

    _active: Optional[Zone] = field(default=None, init=False, repr=False)

    def update(self, raw: float) -> Optional[str]:
        """Feed a raw value, get the key that should be held (or None)."""
        value = self.calibration.normalize(raw)
        # Stay in the current zone while within its widened bounds.
        if self._active is not None:
            if (self._active.start - self.margin) <= value <= (self._active.end + self.margin):
                return self._active.key
        for zone in self.zones:
            if zone.start <= value <= zone.end:
                self._active = zone
                return zone.key
        self._active = None
        return None


@dataclass
class ButtonMapping:
    name: str
    button: int
    action: str  # tap | hold | switch | resync
    key: Optional[str] = None
    on_key: Optional[str] = None
    off_key: Optional[str] = None
    resync_axis: Optional[str] = None
    resync_notch: int = 0

    _was_pressed: bool = field(default=False, init=False, repr=False)

    def update(self, pressed: bool) -> dict:
        """Returns a dict describing what to do this tick:
        {"taps": [keys], "hold": key-or-None, "resync": (axis, notch)-or-None}
        """
        result = {"taps": [], "hold": None, "resync": None}
        rising = pressed and not self._was_pressed
        falling = (not pressed) and self._was_pressed
        self._was_pressed = pressed

        if self.action == "tap":
            if rising and self.key:
                result["taps"].append(self.key)
        elif self.action == "hold":
            if pressed and self.key:
                result["hold"] = self.key
        elif self.action == "switch":
            if rising and self.on_key:
                result["taps"].append(self.on_key)
            if falling and self.off_key:
                result["taps"].append(self.off_key)
        elif self.action == "resync":
            if rising and self.resync_axis is not None:
                result["resync"] = (self.resync_axis, self.resync_notch)
        return result
