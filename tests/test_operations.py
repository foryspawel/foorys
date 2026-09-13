import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from plugin_loader import load_operations


operations = load_operations()


class OperationTests(unittest.TestCase):
    def test_install_channel_list_from_local_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_dir = root / "source"
            source_dir.mkdir()
            (source_dir / "bouquets.tv").write_text("new bouquet\n", encoding="utf-8")
            (source_dir / "userbouquet.foorys.tv").write_text(
                "new user bouquet\n", encoding="utf-8"
            )
            (source_dir / "readme.txt").write_text("ignore\n", encoding="utf-8")
            archive_path = root / "channels.zip"
            with zipfile.ZipFile(str(archive_path), "w") as archive:
                for path in sorted(source_dir.iterdir()):
                    archive.write(str(path), arcname="channels/" + path.name)

            destination = root / "enigma2"
            destination.mkdir()
            (destination / "bouquets.tv").write_text("old bouquet\n", encoding="utf-8")
            storage = root / "storage"
            item = {
                "id": "foorys",
                "name": "Foorys",
                "version": "1",
                "url": archive_path.as_uri(),
                "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
            }
            result = operations.install_channel_list(
                item,
                {
                    "storage_dir": str(storage),
                    "enigma2_dir": str(destination),
                    "create_backup": True,
                },
            )

            self.assertEqual(
                result["installed"], ["bouquets.tv", "userbouquet.foorys.tv"]
            )
            self.assertEqual(
                (destination / "bouquets.tv").read_text(encoding="utf-8"),
                "new bouquet\n",
            )
            self.assertTrue(result["backup"])
            backup = Path(result["backup"])
            self.assertEqual(
                (backup / "bouquets.tv").read_text(encoding="utf-8"),
                "old bouquet\n",
            )
            self.assertTrue((backup / "backup.json").is_file())

    def test_current_oscam_dvbapi_contains_only_foorys_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "oscam.dvbapi"
            target.write_text("P:9999\n# old rule\n", encoding="utf-8")
            result = operations.install_current_oscam_dvbapi(
                {},
                {
                    "storage_dir": str(root / "storage"),
                    "oscam_dvbapi_path": str(target),
                    "create_backup": True,
                },
            )
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                "P:1884\nP:0B01\nP:1861\n",
            )
            self.assertEqual(result["lines"], ["P:1884", "P:0B01", "P:1861"])
            self.assertTrue(result["backup"])


if __name__ == "__main__":
    unittest.main()
