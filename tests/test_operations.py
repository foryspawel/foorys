import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from plugin_loader import load_operations


operations = load_operations()


class OperationTests(unittest.TestCase):
    def test_parse_iptv_m3u_reads_names_groups_and_logos(self):
        playlist = """#EXTM3U
#EXTINF:-1 tvg-id="tvp1.pl" tvg-name="TVP 1" tvg-logo="https://cdn.example/tvp1.png" group-title="Polskie",TVP 1 HD
https://stream.example/live/tvp1
#EXTGRP:Informacja
#EXTINF:-1,TVP Info
https://stream.example/live/info
#EXTINF:-1,nieobsługiwany
file:///tmp/local.ts
"""
        result = operations.parse_iptv_m3u(playlist)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "TVP 1")
        self.assertEqual(result[0]["group"], "Polskie")
        self.assertEqual(result[0]["tvg_logo"], "https://cdn.example/tvp1.png")
        self.assertEqual(result[1]["group"], "Informacja")

    def test_parse_iptv_m3u_removes_polish_prefixes(self):
        playlist = """#EXTM3U
#EXTINF:-1,PL: TVP Sport HD
https://stream.example/live/sport
#EXTINF:-1,PL | Canal+ Extra 1
https://stream.example/live/extra
"""
        result = operations.parse_iptv_m3u(playlist)
        self.assertEqual([entry["name"] for entry in result], ["TVP Sport HD", "Canal+ Extra 1"])

    def test_install_iptv_playlist_creates_named_bouquet_and_picons(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            enigma2 = root / "enigma2"
            enigma2.mkdir()
            storage = root / "storage"
            picon_dir = root / "picon"
            logo = root / "tvp1.png"
            logo.write_bytes(b"\x89PNG\r\n\x1a\nfoorys")
            playlist = root / "foorys.m3u"
            playlist.write_text(
                "#EXTM3U\n"
                '#EXTINF:-1 tvg-id="tvp1.pl" tvg-logo="%s",TVP 1\n'
                "https://stream.example/live/tvp1\n" % logo.as_uri(),
                encoding="utf-8",
            )
            progress = []
            settings = {
                "storage_dir": str(storage),
                "enigma2_dir": str(enigma2),
                "picon_dir": str(picon_dir),
                "iptv_m3u_url": playlist.as_uri(),
                "create_backup": True,
            }
            with mock.patch.object(operations, "_storage_directory", return_value=str(storage)):
                result = operations.install_iptv_playlist({}, settings, progress.append)

            bouquet = enigma2 / "userbouquet.foorys-iptv.tv"
            bouquets_tv = enigma2 / "bouquets.tv"
            self.assertEqual(result["kind"], "iptv")
            self.assertEqual(result["name"], "Foorys IPTV")
            self.assertEqual(result["channels"], 1)
            self.assertEqual(result["picons"], 0)
            content = bouquet.read_text(encoding="utf-8")
            self.assertIn("#NAME Foorys IPTV", content)
            self.assertIn("#DESCRIPTION TVP 1", content)
            self.assertIn('FROM BOUQUET "userbouquet.foorys-iptv.tv"', bouquets_tv.read_text(encoding="utf-8"))
            self.assertFalse(picon_dir.exists() and list(picon_dir.glob("*.png")))
            self.assertTrue(any("Foorys IPTV: bukiet jest gotowy" in line for line in progress))

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

    def test_install_picons_from_local_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_dir = root / "source"
            source_dir.mkdir()
            (source_dir / "1_0_1_2.png").write_bytes(b"new picon")
            (source_dir / "notes.txt").write_text("ignore\n", encoding="utf-8")
            archive_path = root / "picons.zip"
            with zipfile.ZipFile(str(archive_path), "w") as archive:
                archive.write(str(source_dir / "1_0_1_2.png"), arcname="picons/1_0_1_2.png")
                archive.write(str(source_dir / "notes.txt"), arcname="picons/notes.txt")

            target = root / "picon"
            item = {
                "id": "picons-test",
                "name": "Picons test",
                "version": "1",
                "url": archive_path.as_uri(),
                "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
            }
            result = operations.install_picons(
                item,
                {"picon_dir": str(target)},
            )
            self.assertEqual(result["kind"], "picons")
            self.assertEqual(result["installed_count"], 1)
            self.assertEqual((target / "1_0_1_2.png").read_bytes(), b"new picon")


if __name__ == "__main__":
    unittest.main()
