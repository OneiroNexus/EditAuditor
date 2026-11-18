"""Verify built packages in isolated temporary locations, using no network."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command, *, cwd, env=None):
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(f"Package smoke command failed ({result.returncode}).\n{result.stderr[-2000:]}")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("build_directory")
    args = parser.parse_args()
    directory = Path(args.build_directory).resolve()
    wheel = next(directory.glob("*.whl"))
    sdist = next(directory.glob("*.tar.gz"))
    pyz = directory / "EditAuditor_Tool_v1.pyz"
    bundle = directory / "EditAuditor_ReleaseBundle_v1.zip"
    checks = {}
    with tempfile.TemporaryDirectory(prefix="edit-auditor-package-") as temporary:
        temp = Path(temporary)
        before, after = temp / "before.md", temp / "after.md"
        before.write_text("Synthetic input.\n", encoding="utf-8")
        after.write_text("Synthetic input.\n\nA synthetic addition.\n", encoding="utf-8")
        original = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (before, after)]
        result = run([sys.executable, str(pyz), "audit", str(before), str(after)], cwd=temp)
        checks["zipapp_runs_outside_repository"] = json.loads(result.stdout)["status"] == "COVERED"
        target = temp / "installed"
        run([sys.executable, "-m", "pip", "install", "--no-index", "--no-deps",
             "--disable-pip-version-check", "--no-cache-dir", "--no-warn-script-location",
             "--target", str(target), str(wheel)], cwd=temp)
        env = dict(os.environ, PYTHONPATH=str(target), PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
        result = run([sys.executable, "-m", "edit_auditor", "audit", str(before), str(after)], cwd=temp, env=env)
        checks["wheel_offline_install_and_run"] = json.loads(result.stdout)["status"] == "COVERED"
        launcher = "edit-auditor.exe" if os.name == "nt" else "edit-auditor"
        scripts = sorted(target.rglob(launcher))
        if scripts:
            result = run([str(scripts[0]), "--version"], cwd=temp, env=env)
            checks["installed_console_entry_point"] = "0.1.0" in result.stdout
        else:
            checks["installed_console_entry_point"] = False
        extracted = temp / "source"
        extracted.mkdir()
        with tarfile.open(sdist, "r:gz") as archive:
            # Only our generated ordinary files/directories; reject traversal and links.
            for member in archive.getmembers():
                name = Path(member.name)
                if name.is_absolute() or ".." in name.parts or member.issym() or member.islnk():
                    raise RuntimeError("Unsafe source-distribution member.")
            archive.extractall(extracted, filter="data")
        source = next(extracted.iterdir())
        built = temp / "rebuilt"
        run([sys.executable, "-m", "pip", "wheel", "--no-index", "--no-deps",
             "--disable-pip-version-check", "--no-cache-dir", "--no-build-isolation",
             "--wheel-dir", str(built), str(source)], cwd=temp)
        rebuilt_wheel = next(built.glob("*.whl"))
        checks["sdist_offline_build_matches_wheel"] = rebuilt_wheel.read_bytes() == wheel.read_bytes()
        checks["smoke_input_files_unchanged"] = original == [hashlib.sha256(p.read_bytes()).hexdigest() for p in (before, after)]
        with zipfile.ZipFile(bundle) as archive:
            manifest = archive.read("MANIFEST.sha256").decode("ascii").splitlines()
            listed = set()
            for line in manifest:
                expected, name = line.split("  ", 1)
                if name.startswith("/") or ".." in Path(name).parts:
                    raise RuntimeError("Unsafe bundle member.")
                if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                    raise RuntimeError("Manifest mismatch.")
                listed.add(name)
            checks["bundle_manifest_complete_and_valid"] = set(archive.namelist()) == listed | {"MANIFEST.sha256"}
        for artifact, key in ((wheel, "wheel_code_matches_repository"), (pyz, "zipapp_code_matches_repository")):
            with zipfile.ZipFile(artifact) as archive:
                checks[key] = all(
                    archive.read(path.relative_to(ROOT).as_posix()) == path.read_bytes()
                    for path in (ROOT / "edit_auditor").glob("*.py")
                )
    receipt = {
        "schema_version": "1.0", "project": "Edit Auditor", "version": "0.1.0",
        "scope": "Offline packaging smoke checks in the recorded build environment; not cross-platform validation.",
        "checks": checks, "all_passed": all(checks.values()),
        "artifacts": {
            wheel.name: hashlib.sha256(wheel.read_bytes()).hexdigest(),
            pyz.name: hashlib.sha256(pyz.read_bytes()).hexdigest(),
        },
    }
    with (directory / "packaging-checks.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"checks": len(checks), "all_passed": receipt["all_passed"],
                      "failed": [name for name, passed in checks.items() if not passed]}, indent=2))
    return 0 if receipt["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
