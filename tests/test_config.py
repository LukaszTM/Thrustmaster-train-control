import unittest
from pathlib import Path

from simrail_tca.config import ConfigError, load_profile

REPO = Path(__file__).resolve().parent.parent


class ProfileTest(unittest.TestCase):
    def test_shipped_profiles_load(self):
        for name in ("bez-ed.json", "z-ed.json"):
            profile = load_profile(REPO / "config" / name)
            self.assertTrue(profile.notched_axes or profile.zones_axes,
                            f"{name}: no axes configured")

    def test_missing_file(self):
        with self.assertRaises(ConfigError):
            load_profile(REPO / "config" / "nope.json")

    def test_bad_key_name_rejected(self):
        import json
        import tempfile
        data = {"axes": [{"axis": 0, "mode": "notched", "positions": 5,
                          "increase_key": "not_a_key", "decrease_key": "s"}]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        with self.assertRaises(ConfigError):
            load_profile(path)


if __name__ == "__main__":
    unittest.main()
