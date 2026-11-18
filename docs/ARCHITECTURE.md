# Architecture

## One local boundary

The Python core accepts two UTF-8 byte strings and optional review data.
It returns a deterministic dictionary. It performs no filesystem I/O,
subprocess execution, network access, model inference, or persistent learning.

The CLI reads explicitly named regular files and optionally creates one new
report or review-plan file. It never writes an input file. It does not offer
an overwrite, delete, upload, sync, or auto-approve command.

Shells can overwrite files before a program starts. Prefer `--output` with a
fresh filename over shell redirection; the program cannot prevent an enclosing
shell from redirecting output onto an input.

## Occurrence-based accounting

1. Decode UTF-8 strictly. Reject NUL, oversized input, and oversized blocks.
2. Normalize CRLF and CR line endings to LF for block comparison.
3. Segment headings, paragraphs, list items, fenced code, tables, quotes,
   reference definitions, and selected Notion-style containers.
4. Retain each occurrence separately, even when its text is identical to another.
5. Match equal `(kind, text)` pairs one-to-one, preferring equal heading context.
6. Apply snapshot-bound explicit review decisions to unmatched source occurrences.
7. Generate structural and protected-token findings.
8. Apply explicit acknowledgements to the exact current findings.
9. Emit a verdict, inventory, source-to-output records, and limitations.

Whitespace inside a block is literal. Separator blank lines are counted, but
their whitespace characters are not compared. Final-newline presence is tracked.
`COVERED` therefore never means byte-exact. Only `EXACT` means identical bytes.

## The mapping

Let B be the sequence of original block occurrences and A the sequence of output
block occurrences. A literal match consumes one output occurrence. A source block
not consumed by a literal match remains unaccounted until an explicit decision:

- **Duplicate:** exactly one output target must have the same kind and text.
- **Absorbed:** one or more output targets are named, and the reviewer asserts
  that those targets retain the source information.

Many original blocks may be explicitly mapped to the same merged output. One
original block may be mapped to several split outputs. These are human assertions,
not inferred semantic equivalence.

## Snapshot binding

Whole-file SHA-256 fingerprints bind a review to the precise before and after
bytes. Changing either file invalidates the supplied review—even when normalized
blocks would still match. A report also records the canonical review fingerprint.

Fingerprints detect a mismatched snapshot under ordinary collision-resistance
assumptions. They do not authenticate a reviewer, prove a date, establish
authorship, authorize publication, or protect an editable JSON file from forgery.

## Findings

Structural findings cover order inversions among preserved blocks, changed heading
context, blank-line counts and final-newline presence. During absorbed-content
review, token sets flag missing links, numbers, inline code, task states and a small
English constraint vocabulary. Absorbed fenced-code edits always get a finding.

Token sets are not a linguistic model. They do not count all repetitions or
associate a number with the correct subject. A target can retain the same words
and still mean something different. An acknowledged finding is visible in the
report rather than silently removed.

## Five-phase fit

| Phase | Role in this standalone tool |
| --- | --- |
| SOW | Name the source scope and preservation expectations. |
| FORGE | Produce the candidate revision outside the auditor. |
| PULSE | Run literal checks, mappings and findings. |
| VAULT | Retain the exact pair, review and audit receipt locally. |
| TEND | Re-run on each new revision and retain regression examples. |

This is a workflow association, not an engine integration, repository migration,
new permission, or claim that an existing private system is implemented here.

## Resource limits and complexity

Exact matching uses occurrence queues, not an all-pairs semantic-similarity
search. Duplicate suggestions are indexed and capped at twenty targets per
unmatched occurrence. Heading-context fingerprints reuse per-heading digests.
Inputs remain bounded by documented size and block limits.

No production-scale throughput claim is made. The included validation exercises
small synthetic files and input-limit failures, not a denial-of-service proof.

## Files of interest

| File | Responsibility |
| --- | --- |
| `edit_auditor/core.py` | Parsing, matching, reviews, findings, report serialization. |
| `edit_auditor/cli.py` | Bounded reads, strict JSON, command interface, exclusive outputs. |
| `build_backend.py` | Offline pure-Python wheel and source-distribution construction. |
| `tools/validate.py` | Synthetic tests and fresh evidence receipts. |
| `fixtures/corpus.json` | Authored expected-behavior cases, including explicit limitations. |