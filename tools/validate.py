"""Run one synthetic validation suite and write one evidence object.

This script never loads workspace exports or network content. It does not
overwrite a prior run. Results measure implementation behavior, not semantic
accuracy or external novelty. Some corpus cases intentionally expose limitations.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import io
import json
import platform
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from edit_auditor import AuditError, __version__, audit, make_review_template
from edit_auditor.core import canonical_json


class Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed_ids = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed_ids.append(test.id())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_mode(before, after, mode):
    if mode == "none":
        return None
    report = audit(before, after)
    review = make_review_template(report)
    targets = [block["id"] for block in report["inventory"]["after"]]
    for item in review["decisions"]:
        item.update(
            disposition="duplicate" if mode == "duplicate" else "absorbed",
            target_ids=targets, approved=True, reviewer="Synthetic corpus fixture",
            rationale="Fictional test assertion, never a real review.",
        )
    if mode in ("absorbed_ack", "structure_ack"):
        staged = audit(before, after, review)
        review = make_review_template(staged, review)
        for item in review["acknowledgements"]:
            item.update(approved=True, reviewer="Synthetic corpus fixture",
                        rationale="Fictional acknowledgement for the expected-behavior test.")
    if mode == "stale":
        review["after_sha256"] = "0" * 64
    if mode == "missing_reviewer":
        review["decisions"][0]["reviewer"] = ""
    return review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-windows-platform-skips", action="store_true")
    args = parser.parse_args()
    stamp = datetime.datetime.now(datetime.timezone.utc)
    run_id = stamp.strftime("%Y%m%dT%H%M%S%fZ")
    destination = ROOT / "validation-runs" / run_id
    destination.mkdir(parents=True, exist_ok=False)
    source_paths = (
        sorted((ROOT / "edit_auditor").glob("*.py")) +
        sorted((ROOT / "tests").glob("*.py")) +
        sorted((ROOT / "tools").glob("*.py")) +
        [ROOT / "build_backend.py", ROOT / "pyproject.toml"]
    )
    fixture_paths = [ROOT / "fixtures" / "corpus.json"] + sorted((ROOT / "examples").rglob("*.md"))
    source_before = {p.relative_to(ROOT).as_posix(): sha(p) for p in source_paths}
    inputs_before = {p.relative_to(ROOT).as_posix(): sha(p) for p in fixture_paths}
    evidence = {
        "schema_version": "1.0", "project": "Edit Auditor", "version": __version__,
        "run_id": run_id, "run_utc": stamp.isoformat(),
        "environment": {"python": platform.python_version(), "os": platform.system(),
                        "machine": platform.machine(), "implementation": platform.python_implementation()},
        "scope": "Synthetic regression checks only; no real-user corpus, network, performance benchmark, semantic-accuracy estimate, or independent security review.",
        "comparison_plan": {
            "question": "Does this implementation behave according to its documented conservative contract?",
            "grain": "one unit test, authored scenario, or deterministic generated case",
            "population": "included synthetic cases only",
            "units": "checks, not users or documents sampled from production",
            "presentation": "prose totals and inspectable case receipts; no accuracy or comparative-performance chart",
            "reason": "This is a software validation receipt, not an observational dataset or sampled benchmark.",
        },
        "code_sha256": source_before, "input_sha256": inputs_before,
    }
    log = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=Result).run(suite)
    skips = [{"test": test.id(), "reason": reason} for test, reason in result.skipped]
    platform_skips = {
        ("test_fifo_rejected_without_reading", "POSIX FIFO test"),
        ("test_symlink_output_refused", "Windows account cannot create symlinks (WinError 1314)"),
    }
    skips_ok = not skips or (
        args.allow_windows_platform_skips and sys.platform == "win32"
        and all((item["test"].rsplit(".", 1)[-1], item["reason"]) in platform_skips
                for item in skips)
    )
    evidence["unit_tests"] = {
        "run": result.testsRun, "passed": len(result.passed_ids),
        "failed": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
        "passed_ids": result.passed_ids, "skip_details": skips,
    }
    corpus = json.loads((ROOT / "fixtures" / "corpus.json").read_text(encoding="utf-8"))
    cases = []
    for case in corpus["cases"]:
        before, after = case["before"].encode(), case["after"].encode()
        try:
            review = apply_mode(before, after, case["review_mode"])
            report = audit(before, after, review)
            actual = report["status"]
            detail = sorted({finding["kind"] for finding in report["findings"]})
        except AuditError:
            actual, detail = "ERROR", []
        cases.append({
            "id": case["id"], "expected": case["expected"], "actual": actual,
            "matched_expectation": actual == case["expected"],
            "purpose": case["purpose"], "finding_kinds": detail,
        })
    evidence["authored_corpus"] = {"cases": cases, "total": len(cases),
                                   "matched_expectation": sum(c["matched_expectation"] for c in cases)}
    generated = []
    for count in range(1, 65):
        paragraphs = [f"Synthetic entry {index} retains count {index * 11}." for index in range(1, count + 1)]
        before = ("\n\n".join(paragraphs) + "\n").encode()
        transforms = [
            ("identity", before, "EXACT"),
            ("append", before + b"\nA new synthetic entry.\n", "COVERED"),
            ("remove_last", (("\n\n".join(paragraphs[:-1]) + "\n") if count > 1 else "").encode(), "NEEDS_REVIEW"),
            ("line_endings", before.replace(b"\n", b"\r\n"), "COVERED"),
        ]
        for name, after, expected in transforms:
            actual = audit(before, after)["status"]
            generated.append({"id": f"{name}-{count:02d}", "expected": expected, "actual": actual,
                              "matched_expectation": actual == expected})
    evidence["generated_checks"] = {"cases": generated, "total": len(generated),
                                    "matched_expectation": sum(c["matched_expectation"] for c in generated)}
    source_after = {p.relative_to(ROOT).as_posix(): sha(p) for p in source_paths}
    inputs_after = {p.relative_to(ROOT).as_posix(): sha(p) for p in fixture_paths}
    unit_total_recount = len(result.passed_ids) + len(result.failures) + len(result.errors) + len(result.skipped)
    evidence["independent_checks"] = {
        "unit_total_recount_matches": unit_total_recount == result.testsRun,
        "authored_totals_recount_match": len([c for c in cases if c["actual"] == c["expected"]]) == evidence["authored_corpus"]["matched_expectation"],
        "generated_totals_recount_match": len([c for c in generated if c["actual"] == c["expected"]]) == evidence["generated_checks"]["matched_expectation"],
        "source_files_unchanged": source_before == source_after,
        "fixture_files_unchanged": inputs_before == inputs_after,
    }
    evidence["all_expected_checks_passed"] = (
        result.wasSuccessful() and skips_ok and
        all(c["matched_expectation"] for c in cases + generated) and
        all(evidence["independent_checks"].values())
    )
    evidence["interpretation"] = (
        "Matching an expected limitation outcome is not evidence of semantic correctness. "
        "Review approvals in fixtures are fictional. No platform other than the recorded environment is claimed tested."
    )
    (destination / "validation.json").write_text(canonical_json(evidence), encoding="utf-8")
    (destination / "unittest.log").write_text(log.getvalue(), encoding="utf-8")
    print(canonical_json({
        "all_expected_checks_passed": evidence["all_expected_checks_passed"],
        "unit_tests": evidence["unit_tests"]["run"],
        "authored_cases": evidence["authored_corpus"]["total"],
        "generated_checks": evidence["generated_checks"]["total"],
        "receipt": str(destination.relative_to(ROOT)),
        "unexpected_cases": [c["id"] for c in cases + generated if not c["matched_expectation"]],
    }), end="")
    return 0 if evidence["all_expected_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())