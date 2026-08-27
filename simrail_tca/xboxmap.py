"""Pure mapping logic for the Xbox-emulation mode.

Translates TCA axis/button readings into an abstract Xbox 360 gamepad
state. No vgamepad/pygame imports here so it is unit-testable anywhere.

Targets
-------
Axes may map to:  left_stick_x, left_stick_y, right_stick_x,
                  right_stick_y, left_trigger, right_trigger
Buttons (and axis zones) may map to any Xbox button:
    a, b, x, y, lb, rb, back, start, guide, ls, rs,
    dpad_up, dpad_down, dpad_left, dpad_right
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .mapping import Calibration, Zone, ZonesAxis

STICK_TARGETS = {"left_stick_x", "left_stick_y", "right_stick_x", "right_stick_y"}
TRIGGER_TARGETS = {"left_trigger", "right_trigger"}
AXIS_TARGETS = STICK_TARGETS | TRIGGER_TARGETS

BUTTON_TARGETS = {
    "a", "b", "x", "y", "lb", "rb", "back", "start", "guide", "ls", "rs",
    "dpad_up", "dpad_down", "dpad_left", "dpad_right",
}

STICK_MIN, STICK_MAX = -32768, 32767
TRIGGER_MIN, TRIGGER_MAX = 0, 255


def validate_axis_target(name: str) -> None:
    if name not in AXIS_TARGETS:
        raise ValueError(
            f"Unknown axis target '{name}'. Valid: {', '.join(sorted(AXIS_TARGETS))}"
        )


def validate_button_target(name: str) -> None:
    if name not in BUTTON_TARGETS:
        raise ValueError(
            f"Unknown button target '{name}'. Valid: {', '.join(sorted(BUTTON_TARGETS))}"
        )


@dataclass
class PadState:
    """Abstract Xbox pad state produced each tick."""

    sticks: dict = field(default_factory=lambda: {
        "left_stick_x": 0, "left_stick_y": 0,
        "right_stick_x": 0, "right_stick_y": 0,
    })
    triggers: dict = field(default_factory=lambda: {
        "left_trigger": 0, "right_trigger": 0,
    })
    buttons: set = field(default_factory=set)


@dataclass
class XboxAxis:
    """One TCA axis -> one Xbox analog target."""

    axis: int
    target: str
    calibration: Calibration = field(default_factory=Calibration)
    deadzone: float = 0.0  # centered deadzone, sticks only (0.0..0.5)

    def value(self, raw: float) -> int:
        v = self.calibration.normalize(raw)  # 0..1
        if self.target in TRIGGER_TARGETS:
            return round(v * TRIGGER_MAX)
        centered = v * 2.0 - 1.0  # -1..1
        if self.deadzone > 0:
            if abs(centered) < self.deadzone:
                centered = 0.0
            else:
                # Rescale so output still reaches +/-1 at the extremes.
                sign = 1.0 if centered > 0 else -1.0
                centered = sign * (abs(centered) - self.deadzone) / (1.0 - self.deadzone)
        return max(STICK_MIN, min(STICK_MAX, round(centered * STICK_MAX)))


@dataclass
class XboxButton:
    """One TCA button -> one Xbox button (held while held)."""

    button: int
    target: str


class XboxProfile:
    """Parsed config/xbox.json."""

    def __init__(self, data: dict) -> None:
        self.data = data
        self.device_name_contains: str = data.get("device", {}).get("name_contains", "")
        self.device_index = data.get("device", {}).get("index")
        self.poll_hz: float = float(data.get("poll_hz", 120))

        self.axes: list[XboxAxis] = []
        for entry in data.get("axes", []):
            target = entry["target"]
            validate_axis_target(target)
            cal = entry.get("calibration", {})
            self.axes.append(XboxAxis(
                axis=int(entry["axis"]),
                target=target,
                calibration=Calibration(
                    min=float(cal.get("min", -1.0)),
                    max=float(cal.get("max", 1.0)),
                    invert=bool(cal.get("invert", False)),
                ),
                deadzone=float(entry.get("deadzone", 0.0)),
            ))

        self.buttons: list[XboxButton] = []
        for entry in data.get("buttons", []):
            target = entry["target"]
            validate_button_target(target)
            self.buttons.append(XboxButton(
                button=int(entry["button"]),
                target=target,
            ))

        # Optional: axis ranges acting as held Xbox buttons (e.g. a lever
        # detent that should press LB). Reuses ZonesAxis; zone "key" is
        # the Xbox button name here.
        self.axis_zones: list[tuple[int, ZonesAxis]] = []
        for entry in data.get("axis_buttons", []):
            target = entry["target"]
            validate_button_target(target)
            cal = entry.get("calibration", {})
            zones_axis = ZonesAxis(
                name=entry.get("name", f"axis{entry['axis']}_zone"),
                zones=[Zone(float(entry["from"]), float(entry["to"]), target)],
                calibration=Calibration(
                    min=float(cal.get("min", -1.0)),
                    max=float(cal.get("max", 1.0)),
                    invert=bool(cal.get("invert", False)),
                ),
                margin=float(entry.get("margin", 0.02)),
            )
            self.axis_zones.append((int(entry["axis"]), zones_axis))

    def compute(self, axes: list[float], buttons: list[bool]) -> PadState:
        """Build the desired pad state from raw controller readings."""
        state = PadState()
        for mapping in self.axes:
            if mapping.axis >= len(axes):
                continue
            value = mapping.value(axes[mapping.axis])
            if mapping.target in TRIGGER_TARGETS:
                state.triggers[mapping.target] = value
            else:
                state.sticks[mapping.target] = value
        for mapping in self.buttons:
            if mapping.button < len(buttons) and buttons[mapping.button]:
                state.buttons.add(mapping.target)
        for axis_id, zones_axis in self.axis_zones:
            if axis_id >= len(axes):
                continue
            target = zones_axis.update(axes[axis_id])
            if target:
                state.buttons.add(target)
        return state
