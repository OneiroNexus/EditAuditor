# Python API

Run this complete example from the repository folder:

```python
from pathlib import Path
from edit_auditor import audit, make_review_template
from edit_auditor.core import canonical_json, markdown_report

before = Path("examples/addition/before.md").read_bytes()
after = Path("examples/addition/after.md").read_bytes()

report = audit(before, after)
assert report["status"] == "COVERED"
print(markdown_report(report))

pending_review = make_review_template(report)
assert not pending_review["decisions"]
```

## Public entry points

| Entry point | Behavior |
| --- | --- |
| `audit(before_bytes, after_bytes, review=None, include_text=False)` | Return a deterministic report; raise `AuditError` for invalid input/review. No filesystem I/O. |
| `make_review_template(report, existing_review=None)` | Create pending items, preserving an explicitly supplied existing review only when its fingerprint matches the report. Never generates approval. |
| `AuditError` | Validation exception. An exception is not a coverage verdict. |

If `existing_review` is supplied to `make_review_template`, the report must have
been produced by `audit` using that same review. Do not fabricate or mutate report
structures and then assume the template helper performs a fresh source audit.

`canonical_json` and `markdown_report` are serialization helpers in
`edit_auditor.core`. CLI file handling is separate.

## Report fields

- `status` and `meaning`: the exact verdict and its bounded interpretation.
- `before` / `after`: byte size, block count and whole-file fingerprint.
- `summary`: disposition counts and unresolved/acknowledged finding counts.
- `records`: each original occurrence and its output mapping.
- `findings`: structural/token flags, retained even after acknowledgement.
- `inventory`: block IDs, kinds, line spans and fingerprints; text only by opt-in.
- `unmapped_output_ids`: output blocks not used by accounting; not a fact check.
- `review_sha256`: canonical review fingerprint, or null when no review was supplied.
- `privacy` and `limitations`: explicit output boundaries.

The schema is versioned. Consumers should reject unsupported schema versions and
should not collapse `REVIEWED` into automatic literal coverage.