import unittest

from simrail_tca.mapping import Calibration
from simrail_tca.xboxmap import (
    STICK_MAX, STICK_MIN, TRIGGER_MAX,
    PadState, XboxAxis, XboxProfile,
)


class XboxAxisTest(unittest.TestCase):
    def test_stick_range(self):
        ax = XboxAxis(axis=0, target="left_stick_y",
                      calibration=Calibration(min=0.0, max=1.0))
        self.assertEqual(ax.value(0.0), STICK_MIN + 1)  # -32767
        self.assertEqual(ax.value(0.5), 0)
        self.assertEqual(ax.value(1.0), STICK_MAX)

    def test_trigger_range(self):
        ax = XboxAxis(axis=0, target="left_trigger",
                      calibration=Calibration(min=0.0, max=1.0))
        self.assertEqual(ax.value(0.0), 0)
        self.assertEqual(ax.value(1.0), TRIGGER_MAX)
        self.assertEqual(ax.value(0.5), round(0.5 * TRIGGER_MAX))

    def test_deadzone(self):
        ax = XboxAxis(axis=0, target="left_stick_x", deadzone=0.1,
                      calibration=Calibration(min=0.0, max=1.0))
        self.assertEqual(ax.value(0.5), 0)
        self.assertEqual(ax.value(0.52), 0)   # inside deadzone
        self.assertGreater(ax.value(0.6), 0)  # outside
        self.assertEqual(ax.value(1.0), STICK_MAX)  # still reaches max

    def test_invert(self):
        ax = XboxAxis(axis=0, target="left_stick_y",
                      calibration=Calibration(min=0.0, max=1.0, invert=True))
        self.assertEqual(ax.value(0.0), STICK_MAX)

    def test_bad_target_rejected(self):
        with self.assertRaises(ValueError):
            XboxProfile({"axes": [{"axis": 0, "target": "warp_drive"}]})
        with self.assertRaises(ValueError):
            XboxProfile({"buttons": [{"button": 0, "target": "zz"}]})


class XboxProfileTest(unittest.TestCase):
    def make(self):
        return XboxProfile({
            "axes": [
                {"axis": 0, "target": "left_stick_y",
                 "calibration": {"min": 0.0, "max": 1.0}},
                {"axis": 1, "target": "right_trigger",
                 "calibration": {"min": 0.0, "max": 1.0}},
            ],
            "buttons": [
                {"button": 0, "target": "a"},
                {"button": 1, "target": "dpad_up"},
            ],
            "axis_buttons": [
                {"axis": 0, "from": 0.0, "to": 0.05, "target": "lb",
                 "calibration": {"min": 0.0, "max": 1.0}},
            ],
        })

    def test_compute_full_state(self):
        profile = self.make()
        state = profile.compute(axes=[1.0, 0.5], buttons=[True, False])
        self.assertEqual(state.sticks["left_stick_y"], STICK_MAX)
        self.assertEqual(state.triggers["right_trigger"], round(0.5 * TRIGGER_MAX))
        self.assertEqual(state.buttons, {"a"})

    def test_axis_zone_presses_button(self):
        profile = self.make()
        state = profile.compute(axes=[0.02, 0.0], buttons=[False, False])
        self.assertIn("lb", state.buttons)
        state = profile.compute(axes=[0.5, 0.0], buttons=[False, False])
        self.assertNotIn("lb", state.buttons)

    def test_missing_inputs_ignored(self):
        profile = self.make()
        state = profile.compute(axes=[], buttons=[])
        self.assertEqual(state, PadState())


if __name__ == "__main__":
    unittest.main()
