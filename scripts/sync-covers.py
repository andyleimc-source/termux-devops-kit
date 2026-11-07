#!/usr/bin/env python3
"""Download reviewed RetroArch artwork, optionally push it to one ADB target.

Uses Python's standard library. Downloads images from source_url in the manifest;
the repository does not bundle the artwork. Existing pinned SHA256 values must
match. No playlist, emulator setting, or controller binding is modified.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import tempfile
import urllib.request

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_IMAGE_BYTES = 20 * 1024 * 1024


def sanitize(label):
    """RetroArch's filename scrub set; preserve Chinese/full-width punctuation."""
    return re.sub(r'[&*/:`"<>?\\|]', "_", label)


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def destination(root, item):
    library = item["library"]
    label = item["label"]
    if not isinstance(library, str) or library in ("", ".", ".."):
        raise ValueError("Library must be one directory name")
    if "/" in library or "\\" in library:
        raise ValueError("Library must be one directory name: " + library)
    if not isinstance(label, str) or not label.strip():
        raise ValueError("Missing label for " + item["rom_id"])
    dest = root / library / "Named_Boxarts" / (sanitize(label) + ".png")
    try:
        dest.resolve().relative_to(root.resolve())
    except ValueError:
        raise ValueError("Image destination escapes output directory") from None
    return dest


def checked_image(data, item):
    if not data.startswith(PNG_SIGNATURE) or len(data) < 33:
        raise ValueError("Not a PNG image: " + item["rom_id"])
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image exceeds 20 MiB: " + item["rom_id"])
    digest = hashlib.sha256(data).hexdigest()
    expected = item.get("sha256")
    if expected and expected != digest:
        raise ValueError("Hash mismatch: " + item["rom_id"])
    return digest


def install_image(serial, remote_root, relative, local_path, digest):
    remote = str(PurePosixPath(remote_root) / PurePosixPath(relative))
    parent = str(PurePosixPath(remote).parent)
    adb = ["adb", "-s", serial]
    # adb shell joins its arguments into a remote shell command. Quote the
    # filename there as well as passing the local process an argument list.
    subprocess.run(
        adb + ["shell", "mkdir -p " + shlex.quote(parent)],
        check=True, stdout=subprocess.DEVNULL, timeout=30,
    )
    subprocess.run(
        adb + ["push", str(local_path), remote],
        check=True, stdout=subprocess.DEVNULL, timeout=120,
    )
    result = subprocess.check_output(
        adb + ["shell", "sha256sum " + shlex.quote(remote)],
        text=True, timeout=30,
    )
    if not result.split() or result.split()[0] != digest:
        raise ValueError("Remote hash mismatch: " + remote)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--serial", help="Optional adb target; omit for download-only")
    parser.add_argument("--remote-root", default="/sdcard/RetroArch/thumbnails")
    parser.add_argument("--only", help="One ROM ID for a first-image smoke test")
    args = parser.parse_args()
    if args.serial and (
        not PurePosixPath(args.remote_root).is_absolute()
        or ".." in PurePosixPath(args.remote_root).parts
    ):
        raise ValueError("--remote-root must be an absolute directory without '..'")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    selected = [
        item for item in manifest["items"]
        if not args.only or item["rom_id"] == args.only
    ]
    if not selected:
        raise ValueError("No matching games in manifest")
    # Validate all destinations before creating or downloading any file.
    destinations = [(item, destination(args.output, item)) for item in selected]
    seen = set()
    for _, path in destinations:
        key = str(path.resolve())
        if key in seen:
            raise ValueError("Duplicate image destination: " + str(path))
        seen.add(key)
    for item, dest in destinations:
        if dest.exists():
            data = dest.read_bytes()
            digest = checked_image(data, item)
        else:
            if not item["source_url"].startswith("https://"):
                raise ValueError("Artwork source must use HTTPS")
            with urllib.request.urlopen(item["source_url"], timeout=60) as response:
                data = response.read(MAX_IMAGE_BYTES + 1)
            digest = checked_image(data, item)
            atomic_write(dest, data)
        item["sha256"] = digest
        item["local_relative_path"] = dest.relative_to(args.output).as_posix()
        if args.serial:
            install_image(
                args.serial, args.remote_root,
                item["local_relative_path"], dest, digest,
            )
        print(item["rom_id"], item["art_kind"], digest[:12], flush=True)
    atomic_write(
        args.manifest,
        (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    print("Verified images:", len(selected))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit("Error: " + str(error)) from error
