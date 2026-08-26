import unittest

from simrail_tca.mapping import (
    ButtonMapping, Calibration, NotchedAxis, Zone, ZonesAxis,
)


class CalibrationTest(unittest.TestCase):
    def test_normalize_full_range(self):
        cal = Calibration(min=-1.0, max=1.0)
        self.assertAlmostEqual(cal.normalize(-1.0), 0.0)
        self.assertAlmostEqual(cal.normalize(0.0), 0.5)
        self.assertAlmostEqual(cal.normalize(1.0), 1.0)

    def test_normalize_clamps(self):
        cal = Calibration(min=-0.5, max=0.5)
        self.assertAlmostEqual(cal.normalize(-2.0), 0.0)
        self.assertAlmostEqual(cal.normalize(2.0), 1.0)

    def test_invert(self):
        cal = Calibration(min=-1.0, max=1.0, invert=True)
        self.assertAlmostEqual(cal.normalize(-1.0), 1.0)
        self.assertAlmostEqual(cal.normalize(1.0), 0.0)

    def test_zero_span(self):
        cal = Calibration(min=0.5, max=0.5)
        self.assertEqual(cal.normalize(0.5), 0.0)


class NotchedAxisTest(unittest.TestCase):
    def make(self, positions=5, hysteresis=0.15):
        return NotchedAxis(
            name="t", positions=positions,
            increase_key="num_add", decrease_key="num_subtract",
            calibration=Calibration(min=0.0, max=1.0),
            hysteresis=hysteresis,
        )

    def test_starts_at_zero_no_taps(self):
        ax = self.make()
        self.assertEqual(ax.update(0.0), [])
        self.assertEqual(ax.current_notch, 0)

    def test_full_sweep_up(self):
        ax = self.make(positions=5)
        taps = ax.update(1.0)
        self.assertEqual([t.key for t in taps], ["num_add"] * 4)
        self.assertEqual(ax.current_notch, 4)

    def test_full_sweep_down(self):
        ax = self.make(positions=5)
        ax.update(1.0)
        taps = ax.update(0.0)
        self.assertEqual([t.key for t in taps], ["num_subtract"] * 4)
        self.assertEqual(ax.current_notch, 0)

    def test_single_step(self):
        ax = self.make(positions=5)  # notch width 0.25
        taps = ax.update(0.25)
        self.assertEqual(len(taps), 1)
        self.assertEqual(ax.current_notch, 1)

    def test_hysteresis_blocks_jitter(self):
        ax = self.make(positions=5, hysteresis=0.15)
        ax.update(0.25)  # notch 1
        # Boundary between 1 and 2 is at 0.375; jitter just above it
        # must NOT advance because of hysteresis (0.375 + 0.15*0.25 = 0.4125).
        self.assertEqual(ax.update(0.38), [])
        self.assertEqual(ax.current_notch, 1)
        # A clear move beyond the hysteresis band advances.
        self.assertEqual(len(ax.update(0.45)), 1)
        self.assertEqual(ax.current_notch, 2)

    def test_initial_notch_mid_range(self):
        # Combined traction/ED lever: neutral in the middle of the range.
        ax = NotchedAxis(
            name="zadajnik", positions=21,
            increase_key="num_add", decrease_key="num_subtract",
            calibration=Calibration(min=0.0, max=1.0),
            current_notch=10,
        )
        self.assertEqual(ax.update(0.5), [])  # lever at neutral: nothing
        taps = ax.update(0.0)  # pull fully back into ED braking
        self.assertEqual([t.key for t in taps], ["num_subtract"] * 10)
        self.assertEqual(ax.current_notch, 0)

    def test_initial_notch_clamped(self):
        ax = NotchedAxis(
            name="t", positions=5,
            increase_key="num_add", decrease_key="num_subtract",
            current_notch=99,
        )
        self.assertEqual(ax.current_notch, 4)

    def test_resync(self):
        ax = self.make(positions=5)
        ax.update(1.0)
        ax.resync(0)
        self.assertEqual(ax.current_notch, 0)
        # After resync, the still-high axis generates taps again.
        self.assertEqual(len(ax.update(1.0)), 4)

    def test_clamped_at_edges(self):
        ax = self.make(positions=3)
        ax.update(1.0)
        self.assertEqual(ax.update(1.0), [])  # already at top
        ax.update(0.0)
        self.assertEqual(ax.update(0.0), [])  # already at bottom


class ZonesAxisTest(unittest.TestCase):
    def make(self):
        return ZonesAxis(
            name="brake",
            zones=[
                Zone(0.0, 0.35, "num9"),
                Zone(0.35, 0.65, None),
                Zone(0.65, 1.0, "num3"),
            ],
            calibration=Calibration(min=0.0, max=1.0),
            margin=0.02,
        )

    def test_zone_selection(self):
        ax = self.make()
        self.assertEqual(ax.update(0.1), "num9")
        self.assertIsNone(ax.update(0.5))
        self.assertEqual(ax.update(0.9), "num3")

    def test_edge_hysteresis(self):
        ax = self.make()
        ax.update(0.3)  # in num9 zone
        # Slightly past the edge but within margin: stays in the zone.
        self.assertEqual(ax.update(0.36), "num9")
        # Clearly past the margin: switches to the dead zone.
        self.assertIsNone(ax.update(0.5))


class ButtonMappingTest(unittest.TestCase):
    def test_tap_fires_once_on_rising_edge(self):
        b = ButtonMapping(name="shp", button=0, action="tap", key="space")
        self.assertEqual(b.update(True)["taps"], ["space"])
        self.assertEqual(b.update(True)["taps"], [])
        self.assertEqual(b.update(False)["taps"], [])
        self.assertEqual(b.update(True)["taps"], ["space"])

    def test_hold(self):
        b = ButtonMapping(name="horn", button=0, action="hold", key="q")
        self.assertEqual(b.update(True)["hold"], "q")
        self.assertEqual(b.update(True)["hold"], "q")
        self.assertIsNone(b.update(False)["hold"])

    def test_switch(self):
        b = ButtonMapping(name="pant", button=0, action="switch",
                          on_key="p", off_key="o")
        self.assertEqual(b.update(True)["taps"], ["p"])
        self.assertEqual(b.update(True)["taps"], [])
        self.assertEqual(b.update(False)["taps"], ["o"])

    def test_resync(self):
        b = ButtonMapping(name="rs", button=0, action="resync",
                          resync_axis="nastawnik", resync_notch=0)
        self.assertEqual(b.update(True)["resync"], ("nastawnik", 0))
        self.assertIsNone(b.update(True)["resync"])


if __name__ == "__main__":
    unittest.main()
