"""Filesystem boundary: bounded reads, exclusive report creation, no execution."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

from .core import (
    AuditError, MAX_INPUT_BYTES, MAX_REVIEW_BYTES, VERSION, audit,
    canonical_json, make_review_template, markdown_report,
)


def read_regular(path: str, limit: int) -> bytes:
    try:
        # Refuse devices/FIFOs before opening; fstat checks the actual descriptor too.
        if not stat.S_ISREG(os.stat(path).st_mode):
            raise AuditError("Input must be a regular file.")
        with open(path, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise AuditError("Input must be a regular file.")
            data = stream.read(limit + 1)
    except OSError as exc:
        raise AuditError(f"Cannot read an input file ({exc.__class__.__name__}).") from exc
    if len(data) > limit:
        raise AuditError("Input exceeds its size limit.")
    return data


def strict_json(raw: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise AuditError("Duplicate JSON keys are not accepted.")
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(AuditError("Non-finite JSON is not accepted.")))
    except (ValueError, UnicodeDecodeError, RecursionError) as exc:
        raise AuditError("Review is not valid strict UTF-8 JSON.") from exc
    if not isinstance(value, dict):
        raise AuditError("Review must be a JSON object.")
    return value


def write_new(path: str, content: str, inputs: list[str]) -> None:
    destination = Path(path)
    resolved = destination.resolve()
    if any(resolved == Path(item).resolve() for item in inputs):
        raise AuditError("An output path must never be an input path.")
    try:
        # 'x' also refuses existing files and symlinks; there is no overwrite flag.
        with destination.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    except OSError as exc:
        raise AuditError(f"Cannot create new report ({exc.__class__.__name__}); existing files are never overwritten.") from exc


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="edit-auditor",
        description="Audit Markdown preservation locally. Never rewrite source documents.",
    )
    root.add_argument("--version", action="version", version=f"Edit Auditor {VERSION}")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("audit", "plan"):
        sub = commands.add_parser(name, help="Audit a pair" if name == "audit" else "Prepare a pending review; never approve")
        sub.add_argument("before", help="Original UTF-8 Markdown file")
        sub.add_argument("after", help="Edited UTF-8 Markdown file")
        sub.add_argument("--output", help="Create a NEW output file; otherwise print to stdout")
        sub.add_argument("--review", help="Existing snapshot-bound review JSON")
        if name == "audit":
            sub.add_argument("--format", choices=("json", "markdown"), default="json")
            sub.add_argument("--include-text", action="store_true", help="Explicitly include source text in report")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        before = read_regular(args.before, MAX_INPUT_BYTES)
        after = read_regular(args.after, MAX_INPUT_BYTES)
        inputs = [args.before, args.after]
        review = None
        if args.review:
            review = strict_json(read_regular(args.review, MAX_REVIEW_BYTES))
            inputs.append(args.review)
        report = audit(before, after, review, include_text=getattr(args, "include_text", False))
        if args.command == "plan":
            output = canonical_json(make_review_template(report, review))
            code = 0
        else:
            output = markdown_report(report) if args.format == "markdown" else canonical_json(report)
            code = 1 if report["status"] == "NEEDS_REVIEW" else 0
        if args.output:
            write_new(args.output, output, inputs)
        else:
            sys.stdout.write(output)
        return code
    except AuditError as exc:
        sys.stderr.write(f"Edit Auditor: {exc}\n")
        return 2
    except BrokenPipeError:
        return 2
    except UnicodeError:
        sys.stderr.write("Edit Auditor: output encoding cannot represent the requested text.\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())