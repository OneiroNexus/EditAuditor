from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from edit_auditor import AuditError, audit, make_review_template
from edit_auditor.cli import read_regular, strict_json
from edit_auditor.core import (
    MAX_BLOCKS, MAX_BLOCK_CHARS, MAX_INPUT_BYTES, canonical_json,
    markdown_report, parse_document, protected_tokens,
)

ROOT = Path(__file__).resolve().parents[1]


def approved_review(before: bytes, after: bytes, disposition: str = "absorbed"):
    report = audit(before, after)
    review = make_review_template(report)
    all_targets = [b["id"] for b in report["inventory"]["after"]]
    for item in review["decisions"]:
        item.update(
            disposition=disposition, target_ids=all_targets,
            approved=True, reviewer="Synthetic test fixture",
            rationale="Artificial test decision; not a real human approval.",
        )
    return review


def acknowledge(report, review):
    review = make_review_template(report, review)
    for item in review["acknowledgements"]:
        item.update(approved=True, reviewer="Synthetic test fixture",
                    rationale="Artificial acknowledgement for this fixture only.")
    return review


class BlockTests(unittest.TestCase):
    def blocks(self, text):
        return parse_document(text.encode(), "b").blocks

    def test_atx_headings(self):
        blocks = self.blocks("# Title\n\n## Section\n\nText.\n")
        self.assertEqual([b.kind for b in blocks], ["heading", "heading", "paragraph"])
        self.assertEqual(blocks[-1].context, ("# Title", "## Section"))

    def test_heading_context_pop(self):
        blocks = self.blocks("# A\n\n## B\n\nText.\n\n# C\n\nMore.\n")
        self.assertEqual(blocks[-1].context, ("# C",))

    def test_setext_heading(self):
        blocks = self.blocks("Title\n=====\n\nText.\n")
        self.assertEqual(blocks[0].kind, "heading")
        self.assertEqual(blocks[1].context, ("Title\n=====",))

    def test_fenced_code_opaque(self):
        blocks = self.blocks("````python\n# Not a heading\n```\n\nx = 2\n````\n")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].kind, "code")
        self.assertIn("\n\nx = 2", blocks[0].text)

    def test_tilde_fence(self):
        self.assertEqual(len(self.blocks("~~~\na\n\nb\n~~~\n")), 1)

    def test_unclosed_fence(self):
        self.assertEqual(len(self.blocks("```python\n# text\n\nmore\n")), 1)

    def test_table_opaque(self):
        self.assertEqual(len(self.blocks("| A | B |\n|---|---|\n| 1 | 2 |\n")), 1)

    def test_notion_nested_container(self):
        blocks = self.blocks('<callout>\nTitle\n\n<callout>\nNested\n</callout>\n</callout>\n\nAfter.\n')
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].kind, "notion_container")

    def test_self_closing_container(self):
        self.assertEqual(len(self.blocks("<p />\n\nAfter.\n")), 2)

    def test_list_items(self):
        blocks = self.blocks("- one\n  continuation\n- two\n  - nested\n")
        self.assertEqual(len(blocks), 3)
        self.assertIn("continuation", blocks[0].text)

    def test_quote_group(self):
        self.assertEqual(len(self.blocks("> one\n>\n> two\n")), 1)

    def test_reference_definition(self):
        self.assertEqual(self.blocks("[doc]: https://example.invalid/doc\n")[0].kind, "link_definition")

    def test_space_and_unicode_preserved(self):
        block = self.blocks("  Café  \nNext.\n")[0]
        self.assertEqual(block.text, "  Café  \nNext.")

    def test_line_numbers(self):
        blocks = self.blocks("\n# Title\n\nFirst\nsecond\n\nLast\n")
        self.assertEqual([(b.start, b.end) for b in blocks], [(2, 2), (4, 5), (7, 7)])

    def test_empty_and_blank(self):
        self.assertEqual(len(self.blocks("")), 0)
        self.assertEqual(len(self.blocks("\n \n")), 0)

    def test_protected_token_families(self):
        block = self.blocks('- [ ] Must keep `api_v1` at 2.5%: [docs](https://example.invalid/docs).\n')[0]
        tokens = protected_tokens(block)
        self.assertIn("2.5%", tokens["number"])
        self.assertIn("must", tokens["constraint_word"])
        self.assertIn("api_v1", tokens["inline_code"])
        self.assertIn("https://example.invalid/docs", tokens["link_target"])
        self.assertIn("unchecked", tokens["task_state"])


class AuditTests(unittest.TestCase):
    def test_exact(self):
        self.assertEqual(audit(b"One.\n", b"One.\n")["status"], "EXACT")

    def test_empty_exact(self):
        self.assertEqual(audit(b"", b"")["status"], "EXACT")

    def test_append(self):
        report = audit(b"One.\n", b"One.\n\nTwo.\n")
        self.assertEqual(report["status"], "COVERED")
        self.assertEqual(report["summary"]["unmapped_output_blocks"], 1)

    def test_removal(self):
        report = audit(b"One.\n\nTwo.\n", b"One.\n")
        self.assertEqual(report["status"], "NEEDS_REVIEW")
        self.assertEqual(report["summary"]["unaccounted"], 1)

    def test_rephrase_not_automatic(self):
        self.assertEqual(audit(b"Rain is falling.\n", b"It is raining.\n")["status"], "NEEDS_REVIEW")

    def test_line_endings_not_byte_equality(self):
        report = audit(b"One.\r\n\r\nTwo.\r\n", b"One.\n\nTwo.\n")
        self.assertEqual(report["status"], "COVERED")
        self.assertFalse(report["raw_bytes_equal"])

    def test_duplicate_occurrences_not_silently_collapsed(self):
        report = audit(b"Repeat.\n\nRepeat.\n", b"Repeat.\n")
        self.assertEqual(report["summary"]["preserved"], 1)
        self.assertEqual(report["summary"]["unaccounted"], 1)
        self.assertTrue(report["records"][1]["duplicate_candidates"])

    def test_duplicate_approved(self):
        before, after = b"Repeat.\n\nRepeat.\n", b"Repeat.\n"
        review = approved_review(before, after, "duplicate")
        report = audit(before, after, review)
        self.assertEqual(report["status"], "REVIEWED")
        self.assertEqual(report["summary"]["duplicate"], 1)

    def test_absorption_approved(self):
        before, after = b"Count 2. Mode calm.\n", b"Mode calm; count 2.\n"
        report = audit(before, after, approved_review(before, after))
        self.assertEqual(report["status"], "REVIEWED")

    def test_many_to_one_absorption(self):
        before, after = b"Count 2.\n\nMode calm.\n", b"Count 2; mode calm.\n"
        report = audit(before, after, approved_review(before, after))
        self.assertEqual(report["summary"]["absorbed"], 2)
        self.assertEqual(report["status"], "REVIEWED")

    def test_one_to_many_absorption(self):
        before, after = b"Count 2. Mode calm.\n", b"Count 2.\n\nMode calm.\n"
        self.assertEqual(audit(before, after, approved_review(before, after))["status"], "REVIEWED")

    def test_missing_number_stays_open(self):
        before, after = b"Count 2.\n", b"Count several.\n"
        report = audit(before, after, approved_review(before, after))
        self.assertEqual(report["status"], "NEEDS_REVIEW")
        self.assertIn("missing_number", [f["kind"] for f in report["findings"]])

    def test_missing_link_stays_open(self):
        before, after = b"[Read](https://example.invalid/guide)\n", b"Read the guide.\n"
        report = audit(before, after, approved_review(before, after))
        self.assertIn("missing_link_target", [f["kind"] for f in report["findings"]])

    def test_missing_relative_link(self):
        before, after = b"[Read](./guide.md)\n", b"Read the guide.\n"
        report = audit(before, after, approved_review(before, after))
        self.assertIn("missing_link_target", [f["kind"] for f in report["findings"]])

    def test_missing_constraint(self):
        before, after = b"Do not send.\n", b"Do send.\n"
        report = audit(before, after, approved_review(before, after))
        self.assertIn("missing_constraint_word", [f["kind"] for f in report["findings"]])

    def test_inline_code_change(self):
        before, after = b"Use `alpha`.\n", b"Use `beta`.\n"
        report = audit(before, after, approved_review(before, after))
        self.assertIn("missing_inline_code", [f["kind"] for f in report["findings"]])

    def test_checkbox_change(self):
        before, after = b"- [ ] Run test\n", b"- [x] Run test\n"
        report = audit(before, after, approved_review(before, after))
        self.assertIn("missing_task_state", [f["kind"] for f in report["findings"]])

    def test_changed_code_always_flagged(self):
        before, after = b"```\nalpha()\n```\n", b"```\nbeta()\n```\n"
        report = audit(before, after, approved_review(before, after))
        self.assertIn("code_block_changed", [f["kind"] for f in report["findings"]])

    def test_heading_context_change(self):
        report = audit(b"# A\n\nFact.\n", b"# B\n\nFact.\n")
        self.assertIn("heading_context_changed", [f["kind"] for f in report["findings"]])

    def test_order_change(self):
        report = audit(b"One.\n\nTwo.\n", b"Two.\n\nOne.\n")
        self.assertIn("preserved_block_order_changed", [f["kind"] for f in report["findings"]])

    def test_order_acknowledgement(self):
        before, after = b"One.\n\nTwo.\n", b"Two.\n\nOne.\n"
        report = audit(before, after)
        review = make_review_template(report)
        report = audit(before, after, review)
        review = acknowledge(report, review)
        self.assertEqual(audit(before, after, review)["status"], "REVIEWED")

    def test_blank_spacing_change(self):
        report = audit(b"One.\n\nTwo.\n", b"One.\n\n\nTwo.\n")
        self.assertIn("block_spacing_changed", [f["kind"] for f in report["findings"]])

    def test_final_newline_change(self):
        report = audit(b"One.\n", b"One.")
        self.assertIn("final_newline_changed", [f["kind"] for f in report["findings"]])

    def test_trailing_blank_change(self):
        report = audit(b"One.\n\n", b"One.\n")
        self.assertIn("trailing_blank_lines_changed", [f["kind"] for f in report["findings"]])

    def test_no_text_by_default(self):
        report = audit(b"PRIVATE_SYNTHETIC_PHRASE\n", b"Different.\n")
        self.assertNotIn("PRIVATE_SYNTHETIC_PHRASE", canonical_json(report))
        self.assertFalse(report["privacy"]["source_paths_included"])

    def test_include_text_is_explicit(self):
        report = audit(b"SYNTHETIC_PHRASE\n", b"SYNTHETIC_PHRASE\n", include_text=True)
        self.assertIn("SYNTHETIC_PHRASE", canonical_json(report))

    def test_lost_values_redacted_by_default(self):
        before, after = b"Number 739107.\n", b"Number omitted.\n"
        report = audit(before, after, approved_review(before, after))
        self.assertNotIn("739107", canonical_json(report))

    def test_deterministic(self):
        before, after = b"One.\n\nTwo.\n", b"One.\n\nChanged.\n"
        self.assertEqual(canonical_json(audit(before, after)), canonical_json(audit(before, after)))

    def test_review_not_mutated(self):
        before, after = b"Old.\n", b"New.\n"
        review = approved_review(before, after)
        snapshot = copy.deepcopy(review)
        report = audit(before, after, review)
        make_review_template(report, review)
        self.assertEqual(review, snapshot)

    def test_plan_never_approves(self):
        template = make_review_template(audit(b"Old.\n", b"New.\n"))
        self.assertTrue(all(item["approved"] is False for item in template["decisions"]))

    def test_plan_preserves_existing_approvals_and_adds_pending_findings(self):
        before, after = b"Count 2.\n", b"Count several.\n"
        review = approved_review(before, after)
        report = audit(before, after, review)
        updated = make_review_template(report, review)
        self.assertEqual(updated["decisions"], review["decisions"])
        self.assertTrue(updated["acknowledgements"])
        self.assertTrue(all(not a["approved"] for a in updated["acknowledgements"]))

    def test_semantic_equivalence_is_not_claimed(self):
        before, after = b"Value must equal 5.\n", b"Value must exceed 5.\n"
        report = audit(before, after, approved_review(before, after))
        self.assertEqual(report["status"], "REVIEWED")
        self.assertIn("not proof of semantic equivalence", report["meaning"])

    def test_markup_report_fence_safety(self):
        text = b"````\n```embedded```\n````\n"
        report = markdown_report(audit(text, text, include_text=True))
        self.assertIn("`````text\n", report)

    def test_untrusted_code_not_executed(self):
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / "must_not_exist"
            source = f"```python\nopen({str(marker)!r}, 'w').write('bad')\n```\n".encode()
            audit(source, source)
            self.assertFalse(marker.exists())


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.before, self.after = b"Old.\n", b"New.\n"
        self.review = approved_review(self.before, self.after)

    def invalid(self, review):
        with self.assertRaises(AuditError):
            audit(self.before, self.after, review)

    def test_stale_review(self):
        self.review["after_sha256"] = "0" * 64
        self.invalid(self.review)

    def test_schema_version(self):
        self.review["schema_version"] = "999"
        self.invalid(self.review)

    def test_missing_field(self):
        del self.review["decisions"]
        self.invalid(self.review)

    def test_unknown_field(self):
        self.review["approve_everything"] = True
        self.invalid(self.review)

    def test_optional_label_type(self):
        self.review["created_with"] = {"unexpected": "object"}
        self.invalid(self.review)

    def test_wrong_top_level(self):
        self.invalid([])

    def test_duplicate_decision(self):
        self.review["decisions"] *= 2
        self.invalid(self.review)

    def test_unknown_source(self):
        self.review["decisions"][0]["source_id"] = "unknown"
        self.invalid(self.review)

    def test_unknown_target(self):
        self.review["decisions"][0]["target_ids"] = ["unknown"]
        self.invalid(self.review)

    def test_duplicate_targets(self):
        self.review["decisions"][0]["target_ids"] *= 2
        self.invalid(self.review)

    def test_no_deletion_disposition(self):
        self.review["decisions"][0]["disposition"] = "delete"
        self.invalid(self.review)

    def test_duplicate_requires_literal_match(self):
        self.review["decisions"][0]["disposition"] = "duplicate"
        self.invalid(self.review)

    def test_approved_needs_target(self):
        self.review["decisions"][0]["target_ids"] = []
        self.invalid(self.review)

    def test_approved_needs_reviewer(self):
        self.review["decisions"][0]["reviewer"] = "  "
        self.invalid(self.review)

    def test_approved_needs_rationale(self):
        self.review["decisions"][0]["rationale"] = ""
        self.invalid(self.review)

    def test_approval_requires_boolean(self):
        self.review["decisions"][0]["approved"] = 1
        self.invalid(self.review)

    def test_unknown_acknowledgement(self):
        self.review["acknowledgements"] = [{
            "finding_id": "f-unknown", "approved": True,
            "reviewer": "Synthetic", "rationale": "Synthetic",
        }]
        self.invalid(self.review)

    def test_pending_review_has_no_effect(self):
        review = make_review_template(audit(self.before, self.after))
        self.assertEqual(audit(self.before, self.after, review)["status"], "NEEDS_REVIEW")

    def test_plan_rejects_unrelated_review(self):
        report = audit(self.before, self.after)
        with self.assertRaises(AuditError):
            make_review_template(report, self.review)

    def test_wrong_input_type(self):
        with self.assertRaises(AuditError):
            audit("not bytes", b"")

    def test_non_utf8(self):
        with self.assertRaises(AuditError):
            audit(b"\xff", b"")

    def test_nul(self):
        with self.assertRaises(AuditError):
            audit(b"x\0y", b"")

    def test_input_size_limit(self):
        with self.assertRaises(AuditError):
            audit(b"x" * (MAX_INPUT_BYTES + 1), b"")

    def test_block_size_limit(self):
        with self.assertRaises(AuditError):
            audit(b"x" * (MAX_BLOCK_CHARS + 1), b"")

    def test_block_count_limit(self):
        with self.assertRaises(AuditError):
            audit(b"x\n\n" * (MAX_BLOCKS + 1), b"")

    def test_duplicate_json_keys(self):
        with self.assertRaises(AuditError):
            strict_json(b'{"a":1,"a":2}')

    def test_nonfinite_json(self):
        with self.assertRaises(AuditError):
            strict_json(b'{"a":NaN}')


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        self.before, self.after = self.dir / "before.md", self.dir / "after.md"
        self.before.write_bytes(b"Original synthetic text.\n")
        self.after.write_bytes(b"Original synthetic text.\n\nAddition.\n")

    def tearDown(self):
        self.temp.cleanup()

    def call(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "edit_auditor", *map(str, args)],
            cwd=ROOT, capture_output=True, text=True, timeout=20,
        )

    def test_version(self):
        result = self.call("--version")
        self.assertEqual(result.returncode, 0)
        self.assertIn("0.1.0", result.stdout)

    def test_help(self):
        self.assertEqual(self.call("--help").returncode, 0)

    def test_audit_stdout(self):
        result = self.call("audit", self.before, self.after)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "COVERED")

    def test_review_exit_one(self):
        self.after.write_bytes(b"Rewritten.\n")
        self.assertEqual(self.call("audit", self.before, self.after).returncode, 1)

    def test_invalid_exit_two(self):
        result = self.call("audit", self.before, self.dir / "absent.md")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertNotIn(str(self.dir), result.stderr)

    def test_source_files_unchanged(self):
        before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.before, self.after)]
        self.call("audit", self.before, self.after)
        after = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.before, self.after)]
        self.assertEqual(before, after)

    def test_output_source_refused(self):
        original = self.before.read_bytes()
        result = self.call("audit", self.before, self.after, "--output", self.before)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.before.read_bytes(), original)

    def test_existing_output_refused(self):
        output = self.dir / "report.json"
        output.write_bytes(b"keep")
        result = self.call("audit", self.before, self.after, "--output", output)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(output.read_bytes(), b"keep")

    def test_symlink_output_refused(self):
        output = self.dir / "report.json"
        try:
            output.symlink_to(self.before)
        except OSError as error:
            if os.name == "nt" and getattr(error, "winerror", None) == 1314:
                self.skipTest("Windows account cannot create symlinks (WinError 1314)")
            raise
        result = self.call("audit", self.before, self.after, "--output", output)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.before.read_bytes(), b"Original synthetic text.\n")

    def test_new_report(self):
        output = self.dir / "report.json"
        result = self.call("audit", self.before, self.after, "--output", output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(output.read_text())["status"], "COVERED")

    def test_markdown_output(self):
        result = self.call("audit", self.before, self.after, "--format", "markdown")
        self.assertIn("# Edit Auditor report", result.stdout)
        self.assertNotIn("Original synthetic text", result.stdout)

    def test_no_absolute_paths_in_report(self):
        result = self.call("audit", self.before, self.after)
        self.assertNotIn(str(self.dir), result.stdout)

    def test_source_text_opt_in(self):
        result = self.call("audit", self.before, self.after, "--include-text")
        self.assertIn("Original synthetic text", result.stdout)

    def test_restricted_stdout_encoding_is_error_not_review_verdict(self):
        self.before.write_text("Café.\n", encoding="utf-8")
        self.after.write_text("Café.\n", encoding="utf-8")
        env = dict(os.environ, PYTHONIOENCODING="ascii")
        result = subprocess.run(
            [sys.executable, "-m", "edit_auditor", "audit", str(self.before), str(self.after), "--include-text"],
            cwd=ROOT, capture_output=True, text=True, env=env, timeout=20,
        )
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)

    def test_plan_pending(self):
        self.after.write_bytes(b"Rewrite.\n")
        result = self.call("plan", self.before, self.after)
        review = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(review["decisions"][0]["approved"])

    def test_review_input_not_overwritten(self):
        review = self.dir / "review.json"
        review.write_text(canonical_json(make_review_template(audit(self.before.read_bytes(), self.after.read_bytes()))))
        original = review.read_bytes()
        result = self.call("audit", self.before, self.after, "--review", review, "--output", review)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(review.read_bytes(), original)

    def test_directory_input_rejected(self):
        with self.assertRaises(AuditError):
            read_regular(str(self.dir), 100)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO test")
    def test_fifo_rejected_without_reading(self):
        fifo = self.dir / "fifo"
        os.mkfifo(fifo)
        with self.assertRaises(AuditError):
            read_regular(str(fifo), 100)


if __name__ == "__main__":
    unittest.main()