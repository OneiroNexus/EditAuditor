# Limits and honest claims

## What this version does not establish

- Semantic equivalence, truth, completeness of a specification, or scientific novelty.
- A signer's identity, authorship, copyright, ownership, legal rights, or publication permission.
- Whether a new output claim is correct.
- Whether a human actually inspected what their JSON record asserts.
- Rendered equivalence in a browser, Notion, or another Markdown implementation.
- Preservation inside DOCX, PDF, spreadsheet, image, audio or video files.
- Cross-platform support beyond the exact environment recorded in evidence.
- Resistance to every resource-exhaustion input or malicious filesystem race.

## Conservative parser

The parser is deliberately smaller than CommonMark. Notion-style containers and
pipe tables are opaque blocks; embedded structure is not fully interpreted.
Nested lists, HTML edge cases, escaped/nested Markdown destinations, reference
semantics, setext ambiguities, and complex inline syntax can produce coarse
blocks or incomplete token findings.

This conservatism normally leaves a changed block for review. It does not
justify a claim that every possible meaningful transformation is detected.
Line endings normalize; blank-line whitespace characters are not compared
individually. Use `EXACT` when byte identity is the requirement.

## Token sets are not meaning

The number, URL, inline-code, constraint-word and task-state checks are heuristics.
They can be over-sensitive to formatting and under-sensitive to relationships,
repetitions, units, arithmetic, context, synonyms and languages other than the
small English vocabulary used.

For example, “Value must equal 5” and “Value must exceed 5” share the protected
tokens used by this version. If a reviewer incorrectly asserts absorption, the
result can be `REVIEWED`. The included corpus explicitly records this outcome.
It is a limitation demonstration, not evidence that the edit preserved meaning.

## Human review remains a trust boundary

A person can fabricate an approval, pick irrelevant output blocks, or acknowledge
a finding for a poor reason. The software makes those assertions inspectable
and binds them to snapshots; it does not make them true.

No cryptographic signature, independent reviewer, or immutable audit log is
implemented. SHA-256 fingerprints are not signature verification.

## Privacy

Default reports omit raw source text and paths, but expose fingerprints, block
types, counts, line locations, structural changes and inferred token categories.
Fingerprints can reveal equality or be checked against guessed content. Reports
are therefore not anonymous or automatically safe to publish.

`--include-text` intentionally includes the original and revised text. Keep such
reports local unless their content is authorized for release.

## Filesystem behavior

The auditor itself does not rewrite inputs. A caller's shell redirection, another
process, or a maliciously changing filesystem can operate outside that guarantee.
Input bytes are read into a snapshot; later changes to the disk file are not
continuously monitored. A write error can leave a partial newly created report;
the command exits 2, and the report must not be treated as complete.

## Evaluation

All published checks here use authored synthetic examples. They are not a random
sample, an independent evaluation, a field study, a semantic-accuracy measurement,
a security certification or a speed benchmark.

Related-work and prior-art searches have not been performed. The project claims
an inspectable implementation and an explicit contract, not invention of diffing,
checksums, traceability, review workflows or change-impact analysis.