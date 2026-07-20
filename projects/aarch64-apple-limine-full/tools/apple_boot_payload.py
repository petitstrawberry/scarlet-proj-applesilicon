#!/usr/bin/env python3
"""Build and validate generated Apple Silicon m1n1 boot payloads."""

import argparse
import gzip
import hashlib
import json
import pathlib
import subprocess


SCHEMA_VERSION = 1
FDT_MAGIC = b"\xd0\x0d\xfe\xed"


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_output(repo: pathlib.Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def _git_fingerprint(repo: pathlib.Path, excludes: tuple[str, ...]) -> bytes:
    paths = [".", *(f":(exclude){path}" for path in excludes)]
    digest = hashlib.sha256()
    digest.update(_git_output(repo, "rev-parse", "HEAD"))
    digest.update(_git_output(repo, "diff", "--binary", "HEAD", "--", *paths))
    untracked = _git_output(
        repo, "ls-files", "--others", "--exclude-standard", "--", *paths
    ).decode()
    for relative in sorted(filter(None, untracked.splitlines())):
        path = repo / relative
        if path.is_file():
            digest.update(relative.encode())
            digest.update(path.read_bytes())
    return digest.digest()


def _paths(project: pathlib.Path, machine: str) -> dict[str, pathlib.Path]:
    m1n1 = project / "m1n1"
    firmware = project / ".scarlet" / "firmware"
    return {
        "m1n1": m1n1 / "build" / "m1n1.bin",
        "dtb": m1n1 / "payloads" / "dtb" / f"t8103-{machine}.dtb",
        "uboot": project / "u-boot" / "u-boot-nodtb.bin",
        "payload": firmware / f"boot-{machine}.bin",
        "manifest": firmware / f"boot-{machine}.json",
    }


def input_fingerprint(project: pathlib.Path, machine: str) -> str:
    paths = _paths(project, machine)
    digest = hashlib.sha256()
    digest.update(machine.encode())
    digest.update(
        _git_fingerprint(project / "m1n1", ("build/**", "payloads/**"))
    )
    digest.update(_git_fingerprint(project / "u-boot", ()))
    digest.update(paths["dtb"].read_bytes())
    digest.update((project / "build-uboot.sh").read_bytes())
    for patch in sorted((project / "patches" / "u-boot").glob("*.patch")):
        digest.update(patch.name.encode())
        digest.update(patch.read_bytes())
    digest.update(pathlib.Path(__file__).read_bytes())
    return digest.hexdigest()


def _write_manifest(
    project: pathlib.Path,
    machine: str,
    mode: str,
    info_json: pathlib.Path | None = None,
) -> None:
    paths = _paths(project, machine)
    data = {
        "schema": SCHEMA_VERSION,
        "machine": machine,
        "mode": mode,
        "inputs": input_fingerprint(project, machine),
        "artifacts": {
            name: _sha256(paths[name])
            for name in ("m1n1", "dtb", "uboot", "payload")
        },
    }
    if info_json is not None:
        data["info_json"] = {
            "path": str(info_json.resolve()),
            "sha256": _sha256(info_json),
        }
    paths["manifest"].write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def compose(project: pathlib.Path, machine: str) -> pathlib.Path:
    paths = _paths(project, machine)
    for name in ("m1n1", "dtb", "uboot"):
        if not paths[name].is_file():
            raise FileNotFoundError(paths[name])
    payload = (
        paths["m1n1"].read_bytes()
        + paths["dtb"].read_bytes()
        + gzip.compress(paths["uboot"].read_bytes(), mtime=0)
    )
    paths["payload"].parent.mkdir(parents=True, exist_ok=True)
    temporary = paths["payload"].with_suffix(".tmp")
    temporary.write_bytes(payload)
    temporary.replace(paths["payload"])
    _write_manifest(project, machine, "composed")
    return paths["payload"]


def record_patched(
    project: pathlib.Path, machine: str, info_json: pathlib.Path
) -> None:
    _write_manifest(project, machine, "patched", info_json)


def check_fresh(
    project: pathlib.Path,
    machine: str,
    m1n1_path: pathlib.Path | None = None,
    payload_path: pathlib.Path | None = None,
) -> tuple[bool, str]:
    paths = _paths(project, machine)
    if m1n1_path is not None:
        paths["m1n1"] = m1n1_path
    if payload_path is not None:
        paths["payload"] = payload_path
    for name in ("m1n1", "dtb", "uboot", "payload", "manifest"):
        if not paths[name].is_file():
            return False, f"missing {name}: {paths[name]}"
    try:
        manifest = json.loads(paths["manifest"].read_text())
        if manifest.get("schema") != SCHEMA_VERSION:
            return False, "manifest schema changed"
        if manifest.get("inputs") != input_fingerprint(project, machine):
            return False, "payload inputs changed"
        for name in ("m1n1", "dtb", "uboot", "payload"):
            if manifest["artifacts"].get(name) != _sha256(paths[name]):
                return False, f"{name} hash changed"

        payload = paths["payload"].read_bytes()
        m1n1 = paths["m1n1"].read_bytes()
        if not payload.startswith(m1n1 + FDT_MAGIC):
            return False, "payload does not start with the current m1n1 and FDT"
        dtb_offset = len(m1n1)
        dtb_size = int.from_bytes(payload[dtb_offset + 4 : dtb_offset + 8], "big")
        dtb = payload[dtb_offset : dtb_offset + dtb_size]
        if manifest.get("mode") == "composed" and dtb != paths["dtb"].read_bytes():
            return False, "payload DTB differs from the selected base DTB"
        if gzip.decompress(payload[dtb_offset + dtb_size :]) != paths["uboot"].read_bytes():
            return False, "payload U-Boot differs from the current build"
        if manifest.get("mode") == "patched":
            info = manifest.get("info_json", {})
            info_path = pathlib.Path(info.get("path", ""))
            if not info_path.is_file() or info.get("sha256") != _sha256(info_path):
                return False, "AVD patch input changed"
    except (KeyError, OSError, ValueError, gzip.BadGzipFile, json.JSONDecodeError) as exc:
        return False, f"invalid payload metadata: {exc}"
    return True, "payload is current"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("compose", "check", "record-patched"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--project", type=pathlib.Path, required=True)
        sub.add_argument("--machine", default="j293")
        if command == "record-patched":
            sub.add_argument("--info-json", type=pathlib.Path, required=True)
    args = parser.parse_args()
    project = args.project.resolve()
    if args.command == "compose":
        print(compose(project, args.machine))
        return 0
    if args.command == "record-patched":
        record_patched(project, args.machine, args.info_json.resolve())
        return 0
    fresh, reason = check_fresh(project, args.machine)
    print(reason)
    return 0 if fresh else 1


if __name__ == "__main__":
    raise SystemExit(main())
