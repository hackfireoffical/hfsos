import os
import tempfile
import time
import unittest
from pathlib import Path

from app.downloads import (
    DELIVERY_PART_SIZE, RUBIKA_FILE_LIMIT, cleanup_download_cache, cleanup_job_directory,
    is_allowed_asset_url, safe_filename, split_for_rubika,
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

    def test_completed_job_directory_is_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory) / ("a" * 32)
            job.mkdir()
            (job / "download.zip").write_bytes(b"finished")
            cleanup_job_directory(job / "download.zip")
            self.assertFalse(job.exists())

    def test_stale_orphan_jobs_are_removed_but_recent_jobs_are_kept(self):
        with tempfile.TemporaryDirectory() as directory:
            old_job = Path(directory) / ("b" * 32)
            new_job = Path(directory) / ("c" * 32)
            unrelated = Path(directory) / "keep-me"
            for folder in (old_job, new_job, unrelated):
                folder.mkdir()
                (folder / "file.bin").write_bytes(b"x")
            old = time.time() - 7200
            os.utime(old_job, (old, old))
            previous = os.environ.get("DOWNLOAD_DIR")
            os.environ["DOWNLOAD_DIR"] = directory
            try:
                self.assertEqual(cleanup_download_cache(3600), 1)
            finally:
                if previous is None:
                    os.environ.pop("DOWNLOAD_DIR", None)
                else:
                    os.environ["DOWNLOAD_DIR"] = previous
            self.assertFalse(old_job.exists())
            self.assertTrue(new_job.exists())
            self.assertTrue(unrelated.exists())

    def test_split_file_into_rubika_safe_parts(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "large.bin"
            source.write_bytes(b"x" * (RUBIKA_FILE_LIMIT + 123))
            parts = split_for_rubika(source)
            self.assertEqual(len(parts), 2)
            self.assertEqual(parts[0].stat().st_size, DELIVERY_PART_SIZE)
            self.assertEqual(parts[1].stat().st_size, RUBIKA_FILE_LIMIT + 123 - DELIVERY_PART_SIZE)
            self.assertTrue(all(part.read_bytes() == b"x" * part.stat().st_size for part in parts))
            self.assertEqual(sum(part.stat().st_size for part in parts), source.stat().st_size)


if __name__ == "__main__":
    unittest.main()
