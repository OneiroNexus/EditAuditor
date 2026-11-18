# Review contract

**A review is a recorded human assertion, not a semantic proof or authenticated
signature.** The software never approves its own generated plan.

## Every field

| Field | Meaning |
| --- | --- |
| `schema_version` | Keep the generated schema version. |
| `created_with` | Optional tool label; keep the generated value. |
| `before_sha256` | Exact original-file fingerprint; never substitute one to revive an old approval. |
| `after_sha256` | Exact revised-file fingerprint; a changed revision requires a new review. |
| `decisions` | One entry per unmatched source block being accounted for. |
| `acknowledgements` | Separate inspection of structural or token findings. An empty array is valid when no findings exist. |

### Each decision

| Field | What the reviewer records |
| --- | --- |
| `source_id` | Generated original occurrence ID. Do not invent one. |
| `disposition` | `duplicate` for literal duplication; `absorbed` for information retained in rewritten or merged output. |
| `target_ids` | Actual destination IDs from the output inventory. Empty is permitted only while pending. |
| `approved` | Keep `false` until inspected. Only an explicit `true` applies the decision. |
| `reviewer` | Name or local reviewer identifier. Blank is allowed only while pending. Identity is self-attested. |
| `rationale` | Explain where the information survives. Blank is allowed only while pending. |

An approved duplicate must name one literally matching output block. A generic
claim such as “the rest is fine” does not establish absorption; the tool requires
concrete destination IDs, although it cannot verify the quality of the rationale.

### Each acknowledgement

| Field | What the reviewer records |
| --- | --- |
| `finding_id` | Exact ID produced by this audit and mapping. |
| `approved` | Explicit review of the finding, not automatic acceptance. |
| `reviewer` | The person making the assertion. |
| `rationale` | Why the information/structure is acceptably represented in this exact output. |

There is no standalone “delete” disposition. Acknowledgements must not be used
to pretend that genuinely lost unique information was retained. Nevertheless,
the program cannot prevent a person from entering an incorrect assertion; this
limitation is deliberately demonstrated in the corpus.

## Two-stage findings

A pending plan cannot know the intended absorption destinations. Once the
reviewer names them and approves the mapping, the auditor can compare protected
tokens and emit additional findings. `plan --review` preserves supplied decisions
and adds **pending** acknowledgements for the newly visible findings.

The tool rejects unknown or repeated source IDs, target IDs, finding IDs, malformed
review fields, missing rationales, and stale fingerprints. JSON with duplicate keys
or non-finite numbers is rejected by the CLI. A changed mapping can invalidate old
finding IDs; a reviewer must inspect the new report rather than carry old
acknowledgements forward blindly.

## Reviewed is different from covered

Exit code 0 includes `REVIEWED`, because the documented contract is satisfied by
explicit assertions. A workflow requiring automatic literal preservation must
inspect the JSON status and admit only `EXACT` or `COVERED`.

No application should translate `REVIEWED` into “scientifically equivalent,”
“factually verified,” “legally authorized,” “safe to publish,” or “independently
approved.” Those are different claims.

## Synthetic examples

The sample review files use a fictional reviewer and synthetic documents.
They demonstrate the shape of a review; they are never approvals of real work.
Their statuses are retained as test fixtures, not as evidence of human review.