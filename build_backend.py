"""Small, offline PEP 517 backend for this pure-Python, dependency-free project.

No package discovery, shell commands, downloads, generated-code execution, or
editable-install hooks. Both archive formats are assembled from explicit roots.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import gzip
import io
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "edit_auditor"
VERSION = "0.1.0"
DIST_INFO = f"{NAME}-{VERSION}.dist-info"


def _metadata() -> dict[str, bytes]:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    body = (
        "Metadata-Version: 2.1\n"
        "Name: edit-auditor\n"
        f"Version: {VERSION}\n"
        "Summary: Preservation-first local Markdown auditing\n"
        "Author: Aaron Michael Weis (ΩNeiron™)\n"
        "Requires-Python: >=3.10\n"
        "License: MIT\n"
        "Description-Content-Type: text/markdown\n\n" + readme
    )
    return {
        "METADATA": body.encode("utf-8"),
        "WHEEL": b"Wheel-Version: 1.0\nGenerator: edit-auditor-offline-builder\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        "entry_points.txt": b"[console_scripts]\nedit-auditor = edit_auditor.cli:main\n",
        "LICENSE": (ROOT / "LICENSE").read_bytes(),
    }


def get_requires_for_build_wheel(config_settings=None):
    return []


def get_requires_for_build_sdist(config_settings=None):
    return []


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    destination = Path(metadata_directory) / DIST_INFO
    destination.mkdir(parents=True, exist_ok=True)
    for name, raw in _metadata().items():
        (destination / name).write_bytes(raw)
    return DIST_INFO


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    files = {str(path.relative_to(ROOT)).replace("\\", "/"): path.read_bytes()
             for path in sorted((ROOT / NAME).glob("*.py"))}
    files.update({f"{DIST_INFO}/{name}": raw for name, raw in _metadata().items()})
    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for name, raw in sorted(files.items()):
        encoded = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b"=").decode("ascii")
        writer.writerow([name, f"sha256={encoded}", len(raw)])
    writer.writerow([f"{DIST_INFO}/RECORD", "", ""])
    files[f"{DIST_INFO}/RECORD"] = record.getvalue().encode("utf-8")
    filename = f"{NAME}-{VERSION}-py3-none-any.whl"
    destination = Path(wheel_directory)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination / filename, "x", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 11, 17, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)
    return filename


def build_sdist(sdist_directory, config_settings=None):
    filename = f"edit_auditor-{VERSION}.tar.gz"
    destination = Path(sdist_directory)
    destination.mkdir(parents=True, exist_ok=True)
    paths = [path for path in ROOT.iterdir() if path.is_file() and path.suffix != ".pyc"]
    for name in (NAME, "tests", "tools", "docs", "fixtures", "examples", "evidence", "paper", ".github"):
        paths.extend(path for path in (ROOT / name).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc")
    with (destination / filename).open("xb") as stream:
        with gzip.GzipFile(filename="", fileobj=stream, mode="wb", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for path in sorted(set(paths)):
                    raw = path.read_bytes()
                    info = tarfile.TarInfo(f"edit_auditor-{VERSION}/{path.relative_to(ROOT).as_posix()}")
                    info.size, info.mode, info.mtime = len(raw), 0o644, 1794873600
                    archive.addfile(info, io.BytesIO(raw))
    return filename
