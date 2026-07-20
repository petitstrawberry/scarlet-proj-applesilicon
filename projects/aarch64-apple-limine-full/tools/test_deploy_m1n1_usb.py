#!/usr/bin/env python3
"""Unit tests for deploy_m1n1_usb helpers that do not require hardware."""

import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import types
import unittest
from types import SimpleNamespace
from unittest import mock


MODULE_PATH = pathlib.Path(__file__).with_name("deploy_m1n1_usb.py")
SPEC = importlib.util.spec_from_file_location("deploy_m1n1_usb", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ChainloadFailureTests(unittest.TestCase):
    def test_project_runner_disables_rebuild(self):
        runner = MODULE_PATH.with_name("run.sh").read_text()

        self.assertIn('deploy_m1n1_usb.py" --no-build "$@"', runner)

    def test_missing_tool_fails_environment_check(self):
        with mock.patch.object(MODULE.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "missing command.*ld.lld"):
                MODULE.ensure_commands(("ld.lld",))

    def test_chainload_waits_for_proxy_device_before_starting(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = pathlib.Path(directory) / "m1n1.bin"
            payload.write_bytes(b"m1n1")
            args = SimpleNamespace(
                proxy_device="/dev/cu.test-proxy",
                m1n1=payload,
                connect_timeout=1.0,
            )
            result = subprocess.CompletedProcess(["chainload.py"], 0, "", "")

            with (
                mock.patch.object(MODULE, "wait_for_device") as wait_for_device,
                mock.patch.object(MODULE, "run_checked_capture", return_value=result),
            ):
                MODULE.chainload(args)

            wait_for_device.assert_called_once()
            self.assertEqual(wait_for_device.call_args.args[0], args.proxy_device)

    def test_serial_connection_failure_is_retryable(self):
        error = subprocess.CalledProcessError(
            1,
            ["chainload.py"],
            stderr="serial.serialutil.SerialException: device not ready",
        )

        self.assertTrue(MODULE.chainload_failure_is_retryable(error))

    def test_missing_module_is_not_retryable(self):
        error = subprocess.CalledProcessError(
            1,
            ["chainload.py"],
            stderr="ModuleNotFoundError: No module named 'construct'",
        )

        self.assertFalse(MODULE.chainload_failure_is_retryable(error))

    def test_missing_file_is_not_retryable(self):
        error = subprocess.CalledProcessError(
            1,
            ["chainload.py"],
            stderr="python3: can't open file 'chainload.py'",
        )

        self.assertFalse(MODULE.chainload_failure_is_retryable(error))

    def test_missing_tool_is_not_retryable(self):
        error = subprocess.CalledProcessError(
            1,
            ["chainload.py"],
            stderr="Command 'ld.lld -maarch64elf' returned non-zero exit status 127",
        )

        self.assertFalse(MODULE.chainload_failure_is_retryable(error))

    def test_proxy_timeout_is_retryable(self):
        error = subprocess.CalledProcessError(
            1,
            ["chainload.py"],
            stderr="m1n1.proxy.UartTimeout: proxy request timed out",
        )

        self.assertTrue(MODULE.chainload_failure_is_retryable(error))

    def test_bare_chainload_does_not_retry_tool_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            directory_path = pathlib.Path(directory)
            image = directory_path / "scarlet.img"
            payload = directory_path / "boot.bin"
            image.write_bytes(b"image")
            payload.write_bytes(b"payload")
            args = SimpleNamespace(
                image=image,
                payload=payload,
                image_map_size=0x1000,
                image_addr=0x900000000,
                proxy_device="/dev/cu.test-proxy",
                connect_timeout=1.0,
                avd_dtb_patch="off",
                avd_pmgr="off",
            )

            iface = mock.MagicMock()
            proxy = mock.MagicMock()
            proxy_utils = SimpleNamespace(
                adt=None,
                ba=SimpleNamespace(phys_base=0x800000000, mem_size=0x200000000),
            )
            proxyutils_module = types.ModuleType("m1n1.proxyutils")
            proxyutils_module.ProxyUtils = lambda _proxy, heap_size: proxy_utils
            pmu_module = types.ModuleType("m1n1.hw.pmu")
            pmu_module.PMU = lambda _proxy_utils: mock.MagicMock()
            tool_error = subprocess.CalledProcessError(
                1,
                ["chainload.py"],
                stderr="Command 'ld.lld -maarch64elf' returned non-zero exit status 127",
            )

            with (
                mock.patch.dict(
                    sys.modules,
                    {
                        "m1n1.proxyutils": proxyutils_module,
                        "m1n1.hw.pmu": pmu_module,
                    },
                ),
                mock.patch.object(MODULE, "open_proxy", return_value=(iface, proxy)),
                mock.patch.object(MODULE, "wait_for_device"),
                mock.patch.object(MODULE.time, "sleep"),
                mock.patch.object(
                    MODULE,
                    "run_checked_capture",
                    side_effect=tool_error,
                ) as run_chainload,
            ):
                with self.assertRaisesRegex(RuntimeError, "ld.lld"):
                    MODULE.start_guest_bare(args)

            run_chainload.assert_called_once()


if __name__ == "__main__":
    unittest.main()
