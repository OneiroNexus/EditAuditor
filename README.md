# Edit Auditor

**See what survived an edit. Account for what was merged.**

A local-first Markdown auditor by **Aaron Michael Weis (ΩNeiron™)**  
ORCID: [0009-0002-1906-148X](https://orcid.org/0009-0002-1906-148X)

**Version 0.1.0 · Python 3.10+ syntax · no runtime dependencies**

Edit Auditor reads an original document and its proposed revision. It reports
literal preservation, duplicate consolidation, human-reviewed absorption, and
unaccounted source blocks. It never rewrites source documents, follows links,
executes document code, or calls a model or network service.

The code is MIT licensed. The paper is CC BY 4.0. See [RIGHTS](RIGHTS.md).

## The important distinction

An edit that looks better can still lose a number, link, exception, or paragraph.
An ordinary diff shows changes. Edit Auditor adds a conservative accounting
contract: every original block needs a destination or remains unaccounted.

It does **not** prove that a rewrite means the same thing. That judgment remains
with the reviewer, and the report makes that dependency visible.

| Status | What it means |
| --- | --- |
| `EXACT` | The two input files have identical bytes. |
| `COVERED` | All original blocks literally match after line-ending normalization; no open heuristic finding remains. This is not rendering or meaning equivalence. |
| `REVIEWED` | Coverage depends on explicit human assertions or acknowledgements bound to these exact input files. |
| `NEEDS_REVIEW` | A source block is unaccounted for, or a heuristic finding remains unacknowledged. |

## Run without installing

From the extracted repository folder:

```sh
python -m edit_auditor audit examples/addition/before.md examples/addition/after.md --format markdown
```

This bundled example is expected to return `COVERED` and exit code 0.

The deliberately lossy example returns `NEEDS_REVIEW` and exit code 1:

```sh
python -m edit_auditor audit examples/loss/before.md examples/loss/after.md --format markdown
```

The release bundle also contains a standalone `.pyz` tool that can be run with
Python. No installation or external package download is required.

## Produce a new report file

```sh
python -m edit_auditor audit examples/addition/before.md examples/addition/after.md --output audit-report.json
```

Outputs use exclusive creation. Existing files, source files, and symlink
destinations are not overwritten. Use a fresh report filename for another run.

## Prepare a review

```sh
python -m edit_auditor plan examples/duplicate/before.md examples/duplicate/after.md --output review-draft.json
```

The plan contains **pending** decisions, never automatic approvals. A reviewer
records a destination, a disposition (`duplicate` or `absorbed`), their name,
and a rationale. They explicitly set `approved` to `true` only after inspection.
There is no `delete` disposition.

```sh
python -m edit_auditor audit examples/duplicate/before.md examples/duplicate/after.md --review review-draft.json --format markdown
```

A pending plan still returns `NEEDS_REVIEW`. If approved mappings reveal additional
token or code findings, generate a new plan preserving the existing decisions:

```sh
python -m edit_auditor plan examples/duplicate/before.md examples/duplicate/after.md --review review-draft.json --output review-expanded.json
```

See [the review contract](docs/REVIEW_CONTRACT.md) for the complete workflow and
[the synthetic example](examples/duplicate/review.synthetic.json) for structure.
The example's approvals are fictional test data, not a person's sign-off.

## What is checked

- One-to-one literal block matching; duplicate occurrences are not silently erased.
- Source-to-output maps for reviewed duplicate or absorbed content.
- Snapshot binding: an approval for different document bytes is rejected.
- Changed block order, heading context, blank-line counts and final newline.
- During approved absorption: missing link targets, numbers, inline code,
  a small English constraint-word list, and task states.
- Any absorbed fenced-code change receives a separate finding.
- Unmapped output blocks are listed, **not** fact-checked.

No semantic model, fuzzy auto-approval, hidden learning, or telemetry is used.

## Privacy and input boundaries

Reports omit source paths and raw text by default. `--include-text` explicitly
includes document text. Fingerprints, line ranges, and document structure can
still be sensitive; a default report is **not anonymized**.

Only UTF-8 regular files are accepted. Limits are 8 MiB per document, 20,000
blocks per document, 256 Ki characters per block, and 1 MiB per review file.
Malformed or oversized inputs return an error rather than a coverage verdict.

Markdown and Notion-style containers are segmented conservatively. This is not
a complete CommonMark parser, Notion importer, rendered-document comparator,
DOCX/PDF auditor, or permission enforcement system.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | `EXACT`, `COVERED`, or `REVIEWED`; for `plan`, a draft was created/printed. |
| `1` | A completed audit returned `NEEDS_REVIEW`. |
| `2` | Invalid input, invalid review, I/O failure, or command misuse. No passing verdict. |

Consumers that require machine-only literal coverage should accept `EXACT` or
`COVERED` by inspecting the JSON status—not rely on exit code 0 alone.

## Tests and evidence

```sh
python -m unittest discover -s tests -v
```

```sh
python tools/validate.py
```

The second command uses synthetic data only and creates a fresh receipt under
`validation-runs/`. The shipped results and exact environment are in
[evidence/validation.json](evidence/validation.json). These are implementation
checks, not measured semantic accuracy or an independent security audit.

## Research and release materials

- [Methods paper](paper/EditAuditor_Methods_v1.md)
- [Architecture and boundaries](docs/ARCHITECTURE.md)
- [Review contract](docs/REVIEW_CONTRACT.md)
- [Known limitations](docs/LIMITATIONS.md)
- [Verification and packaging](docs/REVIEW_STATUS.md)
- [Citation metadata](CITATION.cff)
- [AI assistance and authorship disclosure](AUTHORSHIP.md)

**Build status is explicit:** running code and observed tests are distinguished
from proposed extensions. No DOI, publication, peer review, or novelty is claimed.