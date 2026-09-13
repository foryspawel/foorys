import importlib
import os
import tempfile
import unittest

from plugin_loader import load_core


load_core()
compat = importlib.import_module("E2Foorys_test_package.compat")
layout = importlib.import_module("E2Foorys_test_package.layout")


class CompatibilityTests(unittest.TestCase):
    def test_ensure_dir_and_replace_file(self):
        with tempfile.TemporaryDirectory() as directory:
            nested = os.path.join(directory, "one", "two")
            compat.ensure_dir(nested)
            compat.ensure_dir(nested)
            source = os.path.join(nested, "source")
            destination = os.path.join(nested, "destination")
            with open(source, "wb") as handle:
                handle.write(b"new")
            with open(destination, "wb") as handle:
                handle.write(b"old")
            compat.replace_file(source, destination)
            with open(destination, "rb") as handle:
                self.assertEqual(handle.read(), b"new")

    def test_full_hd_skin_scaling(self):
        source = '<screen size="1260,700"><widget position="36,185" size="386,100" font="Regular;25" itemHeight="44" /></screen>'
        scaled = layout.scale_skin_for_ratio(source, 1.5)
        self.assertIn('size="1890,1050"', scaled)
        self.assertIn('position="54,278"', scaled)
        self.assertIn('size="579,150"', scaled)
        self.assertIn('font="Regular;38"', scaled)
        self.assertIn('itemHeight="66"', scaled)

    def test_layout_presets(self):
        self.assertEqual(layout.layout_scale(1920, 1080), 1.5)
        self.assertEqual(layout.layout_scale(1280, 720), 1.0)
        self.assertLess(layout.layout_scale(720, 576), 1.0)


if __name__ == "__main__":
    unittest.main()
