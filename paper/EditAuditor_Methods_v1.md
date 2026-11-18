# Preservation-First Editing

## A Local, Review-Bound Auditor for Markdown

**Aaron Michael Weis (ΩNeiron™)**

ORCID: [0009-0002-1906-148X](https://orcid.org/0009-0002-1906-148X)

**Working methods paper · Version 0.1.0 · Prepared 17 November 2026**

### Abstract

AI-assisted editing can improve organization while accidentally discarding a unique detail. A conventional diff exposes textual change but leaves the editor to reconstruct which original information survives. This paper presents Edit Auditor, a small local implementation of preservation-first accounting for Markdown. Each original block occurrence is either literally preserved, explicitly classified as a duplicate, explicitly mapped to output blocks that a reviewer says absorb it, or left unaccounted.

The auditor distinguishes exact byte identity, normalized literal coverage and coverage dependent on human review. Whole-file fingerprints bind assertions to the precise input pair. Conservative findings identify changed order, heading context, spacing, code and selected protected-token losses. The tool reads untrusted documents as data and does not execute source code, follow links, contact a model, or rewrite the original files.

In the recorded environment, 95 unit tests passed; 36 authored scenarios and 256 deterministic generated checks matched their expected behavior. These are synthetic implementation checks, not a measured semantic-accuracy rate. The corpus deliberately includes a wrong human assertion that can receive reviewed status, illustrating the boundary between recorded judgment and proof of meaning.

> **Contribution:** an inspectable accounting contract, runnable reference implementation and reproducible synthetic evidence. No claim of prior-art novelty, independent security certification, or semantic equivalence is made.

### Keywords

Document preservation; Markdown; AI-assisted editing; human review; traceability; reproducible software.

<!-- PAGE -->

## 1. The problem and the contract

“Organize this” is not necessarily permission to discard distinct information. A revision can keep its topic and tone while losing an exception, a source destination, a number or an operational caveat. Conversely, a good consolidation can legitimately replace several paragraphs with a shorter passage. A useful audit must make both situations inspectable.

Edit Auditor treats an original document as a sequence of **occurrences**, not merely a set of unique strings. If a paragraph occurs twice, matching one output paragraph does not silently account for both. A reviewer can explicitly approve duplicate consolidation, but the program does not decide that repeated placement was unimportant.

Let B denote original block occurrences and A output occurrences. Each member of B receives one disposition: preserved, duplicate, absorbed or unaccounted. The counts partition the original sequence; they are not a percentage of semantic content retained.

| Disposition | Required evidence |
| --- | --- |
| Preserved | A one-to-one literal match of block kind and body after line-ending normalization. |
| Duplicate | An explicit review decision naming one literally matching output occurrence. |
| Absorbed | An explicit review assertion naming one or more output destinations for the source information. |
| Unaccounted | No literal match or applicable approved mapping. This remains visible. |

### Three research questions

- **RQ1:** Can the implementation account for every source occurrence without automatically excusing duplicate removal?
- **RQ2:** Can its verdict distinguish literal evidence from reviewer-dependent assertions?
- **RQ3:** Can the software and evidence be reproduced locally without uploading original documents?

The questions concern the implementation's stated contract. They do not ask whether a program can infer every relevant human meaning or independently validate a reviewer's motives.

<!-- PAGE -->

## 2. Representation and matching

The core accepts two UTF-8 byte strings and optional review data. It returns a deterministic report and performs no filesystem or network I/O. The CLI supplies bounded reads and can create a new report file; it never offers a source-editing or overwrite command.

### Conservative segmentation

The parser recognizes headings, paragraphs, list items, fenced code, pipe tables, quotes, reference definitions and selected Notion-style containers. Code fences and recognized containers remain opaque blocks. It is deliberately not a complete CommonMark parser or a rendered-document comparator.

CRLF and CR line endings normalize to LF for matching. Whitespace within block bodies remains literal. Separator blank lines are counted, but their individual whitespace characters are not compared. Final-newline presence is recorded separately. Unicode spelling is not silently normalized.

Equal block kind/body pairs are matched one-to-one using indexed occurrence queues. Equal heading context is preferred when several identical candidates exist. Exact matching is literal string comparison; fingerprints identify snapshots and report records rather than replacing the equality check.

### Conservative findings

| Finding family | What receives attention |
| --- | --- |
| Structure | Changed heading context, preserved-block order, blank-line counts or final newline. |
| References | Missing absolute/relative Markdown destinations and selected link/source attributes. |
| Values | Missing numeric spellings, inline code and task-state tokens during absorption review. |
| Constraints | Missing members of a small English vocabulary, including “not,” “must” and “only.” |
| Executable text | Every absorbed fenced-code change, without running that code. |

Inputs are limited to 8 MiB per document, 20,000 blocks, 256 Ki characters per block and 1 MiB per review. These are defensive bounds, not a throughput or denial-of-service guarantee.

<!-- PAGE -->

## 3. Human review stays explicit

A generated plan contains pending decisions only. The reviewer supplies destination IDs, a disposition, a reviewer label and a rationale. Approval is a separate boolean that remains false until explicitly changed. Unknown IDs, duplicate fields, malformed decisions and missing approval information are rejected.

**Duplicate** requires a literal target match. **Absorbed** permits one-to-many and many-to-one mappings, but it is an assertion about information, not a machine conclusion. There is no “delete” disposition.

The review records the SHA-256 fingerprints of both complete input files. Any byte change invalidates that review. This prevents accidentally reusing an old approval on a revised pair under ordinary hash collision-resistance assumptions. It does not authenticate a person, prove a date, establish authorship, or make editable JSON immutable.

### Two stages of inspection

An initial plan cannot know the intended destinations of rewritten information. Once a mapping is approved, token comparison can expose additional findings. A refreshed plan preserves supplied decisions and adds pending acknowledgements. Findings remain in the final report even when acknowledged.

| Verdict | Honest interpretation |
| --- | --- |
| EXACT | The input files have identical bytes. |
| COVERED | Every source block has literal normalized coverage; no open finding remains. Meaning and rendering are not proved. |
| REVIEWED | The accounting depends on explicit human assertions or acknowledgements. |
| NEEDS_REVIEW | Unaccounted source blocks or unacknowledged findings remain. |

Exit code zero includes REVIEWED. A consumer requiring machine-only literal coverage must inspect the JSON status rather than treating every zero exit code as automatic preservation.

> **Trust boundary:** a reviewer can make a false assertion. The software records and binds that assertion; it cannot make the assertion true.

<!-- PAGE -->

## 4. Evaluation and observed results

The evaluation uses only included synthetic documents and expected-behavior fixtures. No personal workspace export, proprietary engine implementation or real-user corpus was used. Test construction and implementation were AI-assisted and are not independent validation.

### Recorded environment

The reference run used CPython 3.13.15 on Linux, architecture x86_64. Its UTC receipt is `2026-11-17T22:01:17.505234+00:00`. Other Python versions and operating systems are proposed compatibility targets, not observed results.

**Observed:** 95 unit tests passed. All 36 authored scenarios matched their declared outcomes. All 256 generated checks matched their declared outcomes. No test in the recorded unit run was skipped.

The generated checks apply identity, append, last-paragraph removal and line-ending conversion to synthetic paragraph sequences. These families exercise the specified accounting behavior; they do not approximate the distribution of real editing tasks.

The authored corpus includes ordinary preservation, duplicate consolidation, split/merge mappings, missing links and numbers, code edits, stale review rejection, structural changes and deliberate limitations. “Matched expectation” means the implementation behaved as specified, including when that expected behavior exposes a limitation.

### Additional validation

The packaged zipapp ran outside the source repository. The wheel installed and ran with network indexes disabled. A wheel rebuilt from the source distribution matched the original wheel bytes. Source/fixture fingerprints remained unchanged across the recorded validation. Detailed outcomes are in the accompanying receipts.

Independent recounts cross-check the receipt totals against the individual outcomes. Code fingerprints bind the observations to the included implementation. These are local consistency checks, not an independent replication study.

No semantic accuracy, speed advantage, production reliability, human time saving or scientific novelty is inferred from these counts.

<!-- PAGE -->

## 5. Three inspectable examples

### A lost instruction

The bundled loss example begins with two paragraphs:

```text
A capsule contains 3 public sample tiles.

Keep the source model unchanged.
```

The revision retains only the first paragraph. The auditor reports NEEDS_REVIEW: the second original occurrence has no destination. The test does not depend on understanding why that instruction matters.

### An explicit duplicate

The duplicate example repeats “Use the public example.” twice. Keeping one copy leaves the other occurrence unaccounted in the unreviewed audit. A synthetic review can then point the repeated occurrence to the retained, literally equal block and classify it as duplicate.

The resulting status is REVIEWED, not an automatic claim that repeated placement was meaningless. The example review is explicitly fictional test data; it is not a real person's approval.

### A deliberately incorrect assertion

Consider these two statements:

```text
Before: Value must equal 5.
After:  Value must exceed 5.
```

Both retain the protected number and constraint word used by this implementation. A fictional reviewer who incorrectly asserts absorption can produce REVIEWED. This scenario is intentionally included and expected.

> The auditor can make a judgment inspectable without being able to validate that judgment. Passing the synthetic scenario is therefore not evidence that the changed statement preserved its meaning.

This negative example is central to the research claim. It prevents literal token checks or an approval flag from being presented as a semantic guarantee.

<!-- PAGE -->

## 6. Scope, privacy and release ethics

The output report omits source paths and source text by default. An explicit option includes text. Fingerprints, line locations, block types and structural changes can still disclose information, so a default report is not anonymous or automatically safe to publish.

Source text is data. The tool does not execute fenced code, follow embedded URLs, invoke a language model or treat document instructions as commands. It writes only a newly requested report or plan, refusing existing output files and direct input/output collisions.

The enclosing shell and other filesystem actors remain outside that promise. Shell redirection can overwrite a file before the auditor starts. Interrupted output can leave an incomplete new report, accompanied by an error status. Files are read as snapshots, not continuously monitored.

### Limits worth retaining

- The parser is not a full Markdown/Notion syntax tree; nested or escaped constructs can be segmented coarsely.
- Protected tokens are sets, not a model of relationships, units, repetition, multilingual meaning or logical implication.
- A reviewer can select irrelevant targets or acknowledge a finding incorrectly.
- Newly added statements are listed where unmapped, not fact-checked.
- No authenticated signatures, independent reviewer or immutable evidence store is implemented.

### Public usefulness without private disclosure

The release candidate is a standalone implementation with synthetic examples. It does not expose a private game-engine mechanism or require uploading original workspace content. Attribution is carried visibly through the author line, ORCID, citation metadata, version and associated evidence.

Free access, code reuse and model-training permission remain separate choices. This draft does not select an open-source or training grant. Rights, platform fields and public submission remain the owner's explicit decision, subject to applicable law.

<!-- PAGE -->

## 7. Reproduction, position and conclusion

The source package runs directly with Python and has no runtime dependencies. Its CLI, examples, synthetic corpus, tests, review contract and evidence receipts accompany this paper. Optional PDF rendering uses ReportLab and locally available fonts; it is separate from running the auditor.

The included commands are executed from the repository folder:

```sh
python -m unittest discover -s tests -v
```

```sh
python tools/validate.py
```

The validation command creates a fresh receipt rather than overwriting a previous run. Full usage, packaging commands and exact exit behavior are documented in the README and release notes.

### Research position

Diffing, traceability, checksums and human review are established technique families. No external literature or current prior-art search was performed for this draft. A future related-work section should be source-reviewed rather than fabricated; this paper makes no claim to have invented those families.

The five-phase association is operational: SOW names scope; FORGE produces a candidate; PULSE audits; VAULT retains the pair, decisions and receipt; TEND carries useful examples into regression testing. This association is not an integration claim about a private engine.

### Conclusion

Edit Auditor makes a narrow promise: original occurrences do not disappear from its accounting merely because the revised document reads smoothly. Literal evidence and human assertions remain distinguishable. The runnable implementation supports that contract on the included synthetic cases while explicitly preserving its own limitations.

### Associated records and assistance

**R1.** Weis, Aaron Michael. Edit Auditor v0.1.0, accompanying software draft. DOI and public repository are not yet assigned.

**R2.** Included evidence: `evidence/validation.json`, `evidence/packaging.json`, and `fixtures/corpus.json`. These are associated project records, not independent external sources.

**Disclosure.** The author supplied the requirements, research direction and attribution. OpenAI's assistant through Notion AI assisted implementation, testing and drafting. Human author review remains distinct. This is a working methods paper, not a peer-reviewed publication or degree thesis.
