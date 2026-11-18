"""Build local-only distributions into a fresh directory. Never upload."""
from __future__ import annotations

import datetime
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build_backend


def new_zip(path, files):
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 11, 17, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)


def public_files():
    top = ("README.md", "LICENSE", "CITATION.cff", "AUTHORSHIP.md", "CHANGELOG.md",
           "SECURITY.md", "CONTRIBUTING.md", ".gitignore", ".gitattributes", ".zenodo.json", "RIGHTS.md",
           "pyproject.toml", "build_backend.py", "SHA256SUMS", ".github/workflows/verify.yml")
    paths = [ROOT / name for name in top]
    for root in ("edit_auditor", "docs", "tests", "tools", "fixtures", "examples",
                 "evidence", "paper"):
        paths.extend(path for path in (ROOT / root).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc")
    return {path.relative_to(ROOT).as_posix(): path.read_bytes() for path in sorted(set(paths))}


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = ROOT / "build-runs" / stamp
    destination.mkdir(parents=True, exist_ok=False)
    wheel = build_backend.build_wheel(str(destination))
    sdist = build_backend.build_sdist(str(destination))
    pyz = "EditAuditor_Tool_v1.pyz"
    pyz_files = {path.relative_to(ROOT).as_posix(): path.read_bytes()
                 for path in (ROOT / "edit_auditor").glob("*.py")}
    pyz_files["__main__.py"] = b"from edit_auditor.cli import main\nraise SystemExit(main())\n"
    pyz_files["LICENSE"] = (ROOT / "LICENSE").read_bytes()
    pyz_files["CITATION.cff"] = (ROOT / "CITATION.cff").read_bytes()
    new_zip(destination / pyz, pyz_files)
    files = {"edit-auditor/" + name: raw for name, raw in public_files().items()}
    for name in (wheel, sdist, pyz):
        files["artifacts/" + name] = (destination / name).read_bytes()
    files["START_HERE.md"] = (
        "# Edit Auditor release bundle\n\n"
        "The `edit-auditor` folder is the repository source. The `artifacts` folder "
        "contains a standalone Python zipapp, a wheel, and a source distribution.\n\n"
        "See the README for examples and RIGHTS.md for software and paper licenses.\n"
    ).encode("utf-8")
    manifest = "".join(f"{hashlib.sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items()))
    files["MANIFEST.sha256"] = manifest.encode("ascii")
    bundle = "EditAuditor_ReleaseBundle_v1.zip"
    new_zip(destination / bundle, files)
    summary = {
        "directory": str(destination.relative_to(ROOT)),
        "bundle": bundle, "wheel": wheel, "sdist": sdist, "zipapp": pyz,
        "bundle_files": len(files),
        "bundle_sha256": hashlib.sha256((destination / bundle).read_bytes()).hexdigest(),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
