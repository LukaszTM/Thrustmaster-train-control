"""Loading and saving JSON profiles (config/*.json)."""

from __future__ import annotations

import json
from pathlib import Path

from .keysender import validate_key
from .mapping import ButtonMapping, Calibration, NotchedAxis, Zone, ZonesAxis


class ConfigError(Exception):
    pass


class Profile:
    def __init__(self, data: dict, path: Path) -> None:
        self.path = path
        self.data = data
        self.device_name_contains: str = data.get("device", {}).get("name_contains", "")
        self.device_index = data.get("device", {}).get("index")
        self.poll_hz: float = float(data.get("poll_hz", 60))
        self.key_tap_ms: int = int(data.get("key_tap_ms", 40))
        self.key_gap_ms: int = int(data.get("key_gap_ms", 60))

        self.notched_axes: dict[int, NotchedAxis] = {}
        self.zones_axes: dict[int, ZonesAxis] = {}
        self.buttons: list[ButtonMapping] = []
        self._parse_axes(data.get("axes", []))
        self._parse_buttons(data.get("buttons", []))

    @staticmethod
    def _parse_calibration(entry: dict) -> Calibration:
        cal = entry.get("calibration", {})
        return Calibration(
            min=float(cal.get("min", -1.0)),
            max=float(cal.get("max", 1.0)),
            invert=bool(cal.get("invert", False)),
        )

    def _parse_axes(self, entries: list) -> None:
        for entry in entries:
            try:
                axis_id = int(entry["axis"])
                mode = entry.get("mode", "notched")
                name = entry.get("name", f"axis{axis_id}")
                calibration = self._parse_calibration(entry)
                if mode == "notched":
                    validate_key(entry["increase_key"])
                    validate_key(entry["decrease_key"])
                    self.notched_axes[axis_id] = NotchedAxis(
                        name=name,
                        positions=int(entry["positions"]),
                        increase_key=entry["increase_key"],
                        decrease_key=entry["decrease_key"],
                        calibration=calibration,
                        hysteresis=float(entry.get("hysteresis", 0.15)),
                        current_notch=int(entry.get("initial_notch", 0)),
                    )
                elif mode == "zones":
                    zones = []
                    for z in entry["zones"]:
                        key = z.get("key")
                        if key is not None:
                            validate_key(key)
                        zones.append(Zone(float(z["from"]), float(z["to"]), key))
                    self.zones_axes[axis_id] = ZonesAxis(
                        name=name,
                        zones=zones,
                        calibration=calibration,
                        margin=float(entry.get("margin", 0.02)),
                    )
                else:
                    raise ConfigError(f"Axis {axis_id}: unknown mode '{mode}'")
            except (KeyError, ValueError, TypeError) as exc:
                raise ConfigError(f"Bad axis entry {entry!r}: {exc}") from exc

    def _parse_buttons(self, entries: list) -> None:
        for entry in entries:
            try:
                action = entry.get("action", "tap")
                for key_field in ("key", "on_key", "off_key"):
                    if entry.get(key_field):
                        validate_key(entry[key_field])
                self.buttons.append(ButtonMapping(
                    name=entry.get("name", f"button{entry['button']}"),
                    button=int(entry["button"]),
                    action=action,
                    key=entry.get("key"),
                    on_key=entry.get("on_key"),
                    off_key=entry.get("off_key"),
                    resync_axis=entry.get("resync_axis"),
                    resync_notch=int(entry.get("resync_notch", 0)),
                ))
            except (KeyError, ValueError, TypeError) as exc:
                raise ConfigError(f"Bad button entry {entry!r}: {exc}") from exc

    def save_calibration(self, axis_calibrations: dict[int, Calibration]) -> None:
        """Write measured calibration values back into the profile file."""
        for entry in self.data.get("axes", []):
            axis_id = int(entry["axis"])
            if axis_id in axis_calibrations:
                cal = axis_calibrations[axis_id]
                entry["calibration"] = {
                    "min": round(cal.min, 4),
                    "max": round(cal.max, 4),
                    "invert": cal.invert,
                }
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")


def _read_json(path: str | Path) -> tuple[dict, Path]:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8")), path
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc


def load_profile(path: str | Path) -> Profile:
    data, path = _read_json(path)
    return Profile(data, path)


def load_xbox_profile(path: str | Path):
    """Load a profile for the Xbox-emulation mode (see xboxmap.py)."""
    from .xboxmap import XboxProfile
    data, path = _read_json(path)
    try:
        return XboxProfile(data)
    except (KeyError, ValueError, TypeError) as exc:
        raise ConfigError(f"Bad xbox profile {path}: {exc}") from exc
