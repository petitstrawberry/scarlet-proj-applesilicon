#!/usr/bin/env python3
"""Tests for Apple Silicon generated boot payload metadata."""

import gzip
import pathlib
import tempfile
import unittest
from unittest import mock

import apple_boot_payload


class AppleBootPayloadTests(unittest.TestCase):
    def create_project(self, root: pathlib.Path) -> pathlib.Path:
        project = root / "project"
        (project / "m1n1" / "build").mkdir(parents=True)
        (project / "m1n1" / "payloads" / "dtb").mkdir(parents=True)
        (project / "u-boot").mkdir()
        (project / "m1n1" / "build" / "m1n1.bin").write_bytes(b"m1n1")
        dtb = bytearray(16)
        dtb[:4] = apple_boot_payload.FDT_MAGIC
        dtb[4:8] = len(dtb).to_bytes(4, "big")
        (project / "m1n1" / "payloads" / "dtb" / "t8103-j293.dtb").write_bytes(
            dtb
        )
        (project / "u-boot" / "u-boot-nodtb.bin").write_bytes(b"u-boot")
        return project

    def test_compose_and_check_use_exact_current_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            project = self.create_project(pathlib.Path(directory))
            with mock.patch.object(
                apple_boot_payload, "input_fingerprint", return_value="inputs"
            ):
                payload_path = apple_boot_payload.compose(project, "j293")
                fresh, reason = apple_boot_payload.check_fresh(project, "j293")

            self.assertTrue(fresh, reason)
            payload = payload_path.read_bytes()
            dtb_offset = len(b"m1n1")
            dtb_size = int.from_bytes(payload[dtb_offset + 4 : dtb_offset + 8], "big")
            self.assertEqual(gzip.decompress(payload[dtb_offset + dtb_size :]), b"u-boot")

    def test_changed_fingerprint_is_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            project = self.create_project(pathlib.Path(directory))
            with mock.patch.object(
                apple_boot_payload,
                "input_fingerprint",
                side_effect=("before", "after"),
            ):
                apple_boot_payload.compose(project, "j293")
                fresh, reason = apple_boot_payload.check_fresh(project, "j293")

            self.assertFalse(fresh)
            self.assertEqual(reason, "payload inputs changed")


if __name__ == "__main__":
    unittest.main()
