import hashlib
import json
import os
import tarfile
import tempfile
import unittest
import zipfile

from plugin_loader import load_core


core = load_core()


class CoreTests(unittest.TestCase):
    def valid_manifest(self):
        checksum = "a" * 64
        return {
            "schema_version": 1,
            "channel_lists": [
                {
                    "id": "list-1",
                    "name": "Lista 1",
                    "version": "1",
                    "url": "channels/list.tar.gz",
                    "sha256": checksum,
                }
            ],
            "plugins": [],
            "picons": [],
            "oscam_dvbapi": None,
        }

    def test_manifest_is_normalized(self):
        result = core.normalize_manifest(self.valid_manifest())
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["channel_lists"][0]["sha256"], "a" * 64)

    def test_manifest_rejects_bad_checksum(self):
        manifest = self.valid_manifest()
        manifest["channel_lists"][0]["sha256"] = "nope"
        with self.assertRaises(core.ManifestError):
            core.normalize_manifest(manifest)

    def test_sha256(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "file")
            with open(path, "wb") as handle:
                handle.write(b"e2-foorys")
            expected = hashlib.sha256(b"e2-foorys").hexdigest()
            self.assertTrue(core.verify_sha256(path, expected))

    def test_safe_archive_extract_and_channel_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = os.path.join(directory, "channels.tar.gz")
            with tarfile.open(archive_path, "w:gz") as archive:
                for filename, content in (
                    ("nested/bouquets.tv", b"#NAME TV\n"),
                    ("nested/userbouquet.foorys.tv", b"#NAME Foorys\n"),
                    ("nested/readme.txt", b"ignore"),
                ):
                    path = os.path.join(directory, filename.replace("/", os.sep))
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "wb") as handle:
                        handle.write(content)
                    archive.add(path, arcname=filename)
            extracted = os.path.join(directory, "out")
            core.extract_archive(archive_path, extracted)
            files = core.find_channel_files(extracted)
            self.assertEqual(
                sorted(os.path.basename(path) for path in files),
                ["bouquets.tv", "userbouquet.foorys.tv"],
            )

    def test_safe_archive_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = os.path.join(directory, "bad.tar")
            with tarfile.open(archive_path, "w") as archive:
                path = os.path.join(directory, "bad.txt")
                with open(path, "wb") as handle:
                    handle.write(b"bad")
                archive.add(path, arcname="../../outside.txt")
            with self.assertRaises(core.ArchiveError):
                core.extract_archive(archive_path, os.path.join(directory, "out"))

    def test_safe_zip_extract(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = os.path.join(directory, "channels.zip")
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("nested/bouquets.radio", b"#NAME Radio\n")
            extracted = os.path.join(directory, "out")
            core.extract_archive(archive_path, extracted)
            self.assertEqual(
                [os.path.basename(path) for path in core.find_channel_files(extracted)],
                ["bouquets.radio"],
            )

    def test_find_picon_files(self):
        with tempfile.TemporaryDirectory() as directory:
            nested = os.path.join(directory, "nested")
            os.makedirs(nested)
            with open(os.path.join(nested, "channel.png"), "wb") as handle:
                handle.write(b"png")
            with open(os.path.join(nested, "readme.txt"), "wb") as handle:
                handle.write(b"ignore")
            self.assertEqual(
                [os.path.basename(path) for path in core.find_picon_files(directory)],
                ["channel.png"],
            )

    def test_version_is_newer(self):
        self.assertTrue(core.version_is_newer("0.2.1", "0.2.0"))
        self.assertFalse(core.version_is_newer("0.2.0", "0.2.0"))
        self.assertFalse(core.version_is_newer("v0.1.9", "0.2.0"))


if __name__ == "__main__":
    unittest.main()
