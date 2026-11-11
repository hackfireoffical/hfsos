import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.downloads import (
    DELIVERY_PART_SIZE, is_allowed_asset_url, safe_filename, split_for_rubika,
)


class DownloadUtilityTests(unittest.TestCase):
    def test_safe_filename_removes_path_and_unsafe_chars(self):
        self.assertEqual(safe_filename("../../hello world?.zip"), "hello world_.zip")

    def test_asset_host_allowlist(self):
        self.assertTrue(is_allowed_asset_url("https://objects.githubusercontent.com/file.zip"))
        self.assertTrue(is_allowed_asset_url("https://cdn.modrinth.com/data/a.jar"))
        self.assertFalse(is_allowed_asset_url("http://github.com/file.zip"))
        self.assertFalse(is_allowed_asset_url("https://github.com.evil.example/file.zip"))
        self.assertFalse(is_allowed_asset_url("https://example.com/file.zip"))

    def test_split_file_into_rubika_safe_parts(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "large.bin"
            source.write_bytes(b"x" * (DELIVERY_PART_SIZE + 123))
            parts = split_for_rubika(source)
            self.assertEqual(len(parts), 2)
            self.assertEqual(parts[0].stat().st_size, DELIVERY_PART_SIZE)
            self.assertEqual(parts[1].stat().st_size, 123)
            self.assertEqual(b"".join(part.read_bytes() for part in parts), source.read_bytes())


if __name__ == "__main__":
    unittest.main()
