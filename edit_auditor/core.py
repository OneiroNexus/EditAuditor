"""Deterministic block accounting, conservative findings, explicit review."""

from __future__ import annotations

import hashlib
import json
import re
import copy
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

VERSION = "0.1.0"
SCHEMA = "1.0"
MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_BLOCKS = 20_000
MAX_BLOCK_CHARS = 256 * 1024
MAX_REVIEW_BYTES = 1024 * 1024


class AuditError(ValueError):
    """Invalid input; no usable audit verdict should be inferred."""


def digest(value: bytes | str) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+|$)")
LIST_ITEM = re.compile(r"^[ \t]*(?:[-+*]|\d+[.)])[ \t]+")
RULE = re.compile(r"^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$")
LINK_DEFINITION = re.compile(r"^ {0,3}\[[^\]]+\]:[ \t]*")
SETEXT = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
XML_CONTAINER = re.compile(
    r"^[ \t]*<(table|columns|column|callout|toggle|quote|ul|ol|li|p|"
    r"synced-block|synced-block-reference|meeting-notes|page|database|folder)"
    r"(?=[\s>])"
)
URL = re.compile(r"""(?:https?://|collection://|user://|session://|agent://)[^\s<>"'\]]+""")
ATTRIBUTE_LINK = re.compile(r"""\b(?:url|source|href)\s*=\s*["']([^"']+)["']""")
MD_DESTINATION = re.compile(r"!?\[[^\]\[\n]*\]\((<[^>\n]+>|[^\s)]+)")
INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.DOTALL)
NUMBER = re.compile(r"(?<![\w])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?")
CONSTRAINT = re.compile(r"\b(?:not|never|no|without|must|shall|only|may)\b", re.IGNORECASE)
TASK = re.compile(r"^[ \t]*[-+*][ \t]+\[([ xX])\]", re.MULTILINE)


@dataclass(frozen=True)
class Block:
    id: str
    index: int
    kind: str
    text: str
    start: int
    end: int
    signature: str
    context: tuple[str, ...]
    context_sha256: str
    blanks_before: int

    def public(self, include_text: bool) -> dict[str, Any]:
        result = {
            "id": self.id, "kind": self.kind,
            "line_start": self.start, "line_end": self.end,
            "content_sha256": self.signature,
            "context_sha256": self.context_sha256,
            "blank_lines_before": self.blanks_before,
        }
        if include_text:
            result["text"] = self.text
            result["heading_context"] = list(self.context)
        return result


@dataclass(frozen=True)
class Document:
    raw: bytes
    blocks: tuple[Block, ...]
    trailing_blank_lines: int
    final_newline: bool

    @property
    def sha256(self) -> str:
        return digest(self.raw)


def _kind(line: str) -> str | None:
    if FENCE.match(line):
        return "code"
    if HEADING.match(line):
        return "heading"
    if XML_CONTAINER.match(line):
        return "notion_container"
    if line.lstrip().startswith("|"):
        return "table"
    if RULE.match(line):
        return "rule"
    if LIST_ITEM.match(line):
        return "list_item"
    if line.lstrip().startswith(">"):
        return "quote"
    if LINK_DEFINITION.match(line):
        return "link_definition"
    return None


def parse_document(raw: bytes, prefix: str) -> Document:
    """Conservative block segmentation, NOT a complete CommonMark parser.

    Only CRLF and CR line endings are normalized. Interior/trailing spaces,
    indentation, Unicode, and content inside code are otherwise preserved.
    Blank-line counts and the final newline are tracked separately.
    """
    if not isinstance(raw, bytes):
        raise AuditError("Documents must be UTF-8 bytes.")
    if len(raw) > MAX_INPUT_BYTES:
        raise AuditError("Input exceeds the 8 MiB document limit.")
    if b"\0" in raw:
        raise AuditError("NUL bytes are not accepted in Markdown input.")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AuditError("Input is not valid UTF-8.") from exc
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    final_newline = normalized.endswith("\n")
    if final_newline:
        lines.pop()
    if not normalized:
        lines = []
    blocks: list[Block] = []
    headings: list[tuple[int, str, str]] = []
    blanks = 0
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            blanks += 1
            i += 1
            continue
        start = i
        kind = _kind(lines[i]) or "paragraph"
        if kind == "code":
            opening = FENCE.match(lines[i])
            assert opening is not None
            fence = opening.group(1)
            closer = re.compile(r"^ {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}[ \t]*$")
            i += 1
            while i < len(lines):
                closing = bool(closer.match(lines[i]))
                i += 1
                if closing:
                    break
        elif kind == "notion_container":
            match = XML_CONTAINER.match(lines[i])
            assert match is not None
            tag = match.group(1)
            tags = re.compile(r"</?" + re.escape(tag) + r"(?=[\s>])[^>]*>")
            depth = 0
            while i < len(lines):
                for item in tags.finditer(lines[i]):
                    value = item.group(0)
                    if value.startswith("</"):
                        depth -= 1
                    elif not value.rstrip().endswith("/>"):
                        depth += 1
                i += 1
                if depth <= 0:
                    break
        elif kind in {"heading", "rule", "link_definition"}:
            i += 1
        elif kind in {"table", "quote"}:
            marker = "|" if kind == "table" else ">"
            i += 1
            while i < len(lines) and lines[i].lstrip().startswith(marker):
                i += 1
        elif kind == "paragraph" and i + 1 < len(lines) and SETEXT.match(lines[i + 1]):
            kind = "heading"
            i += 2
        else:
            i += 1
            while i < len(lines) and lines[i].strip() and _kind(lines[i]) is None:
                # Preserve a new setext heading as its own conservative block.
                if i + 1 < len(lines) and SETEXT.match(lines[i + 1]):
                    break
                i += 1
        body = "\n".join(lines[start:i])
        if len(body) > MAX_BLOCK_CHARS:
            raise AuditError("Input contains a block exceeding 256 Ki characters.")
        signature = digest(kind + "\0" + body)
        index = len(blocks)
        context = tuple(value for _, value, _ in headings)
        context_sha = digest("\0".join(value for _, _, value in headings))
        blocks.append(Block(
            f"{prefix}{index + 1:05d}-{signature[:12]}", index, kind, body,
            start + 1, i, signature, context, context_sha, blanks,
        ))
        if len(blocks) > MAX_BLOCKS:
            raise AuditError("Input exceeds the 20,000-block document limit.")
        if kind == "heading":
            atx = HEADING.match(lines[start])
            level = len(atx.group(1)) if atx else (1 if lines[i - 1].lstrip().startswith("=") else 2)
            while headings and headings[-1][0] >= level:
                headings.pop()
            headings.append((level, body, digest(body)))
        blanks = 0
    return Document(raw, tuple(blocks), blanks, final_newline)


def protected_tokens(block: Block) -> dict[str, set[str]]:
    """Heuristic review aids. Never a proof of semantic preservation."""
    text = block.text
    links = set(ATTRIBUTE_LINK.findall(text))
    links.update(value.strip("<>") for value in MD_DESTINATION.findall(text))
    links.update(value.rstrip(".,;:)") for value in URL.findall(text))
    return {
        "link_target": links,
        "number": set(NUMBER.findall(text)),
        "inline_code": {match.group(2) for match in INLINE_CODE.finditer(text)},
        "constraint_word": {value.casefold() for value in CONSTRAINT.findall(text)},
        "task_state": {"checked" if value.casefold() == "x" else "unchecked" for value in TASK.findall(text)},
    }


def _exact_matches(before: Document, after: Document) -> dict[str, Block]:
    by_signature: dict[tuple[str, str], deque[Block]] = defaultdict(deque)
    by_context: dict[tuple[str, str, tuple[str, ...]], deque[Block]] = defaultdict(deque)
    for block in after.blocks:
        by_signature[(block.kind, block.text)].append(block)
        by_context[(block.kind, block.text, block.context)].append(block)
    consumed: set[str] = set()
    result: dict[str, Block] = {}
    for source in before.blocks:
        options = (
            by_context[(source.kind, source.text, source.context)],
            by_signature[(source.kind, source.text)],
        )
        for queue in options:
            while queue and queue[0].id in consumed:
                queue.popleft()
            if queue:
                target = queue.popleft()
                consumed.add(target.id)
                result[source.id] = target
                break
    return result


def _require_keys(obj: Any, required: set[str], optional: set[str], label: str) -> None:
    if not isinstance(obj, dict):
        raise AuditError(f"{label} must be an object.")
    if not required <= obj.keys() or obj.keys() - required - optional:
        raise AuditError(f"{label} has missing or unrecognized fields.")


def _approval(obj: dict[str, Any], label: str) -> None:
    if type(obj["approved"]) is not bool:
        raise AuditError(f"{label}.approved must be true or false.")
    for field in ("reviewer", "rationale"):
        if not isinstance(obj[field], str):
            raise AuditError(f"{label}.{field} must be text.")
        if obj["approved"] and not obj[field].strip():
            raise AuditError(f"Approved {label} requires reviewer and rationale.")
        if len(obj[field]) > 10_000:
            raise AuditError(f"{label}.{field} exceeds the length limit.")


def _validate_review(
    review: Any, before: Document, after: Document, matches: dict[str, Block]
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    if review is None:
        return {}, []
    try:
        size = len(canonical_json(review).encode("utf-8"))
    except (TypeError, ValueError, RecursionError) as exc:
        raise AuditError("Review must contain ordinary JSON data.") from exc
    if size > MAX_REVIEW_BYTES:
        raise AuditError("Review exceeds the 1 MiB limit.")
    _require_keys(
        review, {"schema_version", "before_sha256", "after_sha256", "decisions", "acknowledgements"},
        {"created_with"}, "Review",
    )
    if review["schema_version"] != SCHEMA:
        raise AuditError("Unsupported review schema version.")
    if "created_with" in review and (not isinstance(review["created_with"], str) or len(review["created_with"]) > 256):
        raise AuditError("Review.created_with must be a short text label.")
    if review["before_sha256"] != before.sha256 or review["after_sha256"] != after.sha256:
        raise AuditError("Stale review: document fingerprints do not match.")
    if not isinstance(review["decisions"], list) or not isinstance(review["acknowledgements"], list):
        raise AuditError("Review decisions and acknowledgements must be arrays.")
    sources = {block.id: block for block in before.blocks}
    targets = {block.id: block for block in after.blocks}
    decisions: dict[str, dict[str, Any]] = {}
    for item in review["decisions"]:
        _require_keys(
            item, {"source_id", "disposition", "target_ids", "approved", "reviewer", "rationale"},
            set(), "Decision",
        )
        sid = item["source_id"]
        if not isinstance(sid, str) or sid not in sources or sid in decisions or sid in matches:
            raise AuditError("Decision source must be a unique, unmatched source block.")
        if item["disposition"] not in ("duplicate", "absorbed"):
            raise AuditError("Disposition must be duplicate or absorbed; deletion is not a disposition.")
        tids = item["target_ids"]
        if not isinstance(tids, list) or any(not isinstance(t, str) or t not in targets for t in tids):
            raise AuditError("Decision targets must be existing output block IDs.")
        if len(tids) != len(set(tids)):
            raise AuditError("Decision target IDs must not repeat.")
        _approval(item, "Decision")
        if item["approved"] and not tids:
            raise AuditError("Approved decisions require at least one output target.")
        if item["disposition"] == "duplicate" and item["approved"]:
            if len(tids) != 1 or (targets[tids[0]].kind, targets[tids[0]].text) != (sources[sid].kind, sources[sid].text):
                raise AuditError("A duplicate must point to one literally matching output block.")
        decisions[sid] = item
    for ack in review["acknowledgements"]:
        _require_keys(
            ack, {"finding_id", "approved", "reviewer", "rationale"}, set(), "Acknowledgement",
        )
        if not isinstance(ack["finding_id"], str):
            raise AuditError("Acknowledgement finding_id must be text.")
        _approval(ack, "Acknowledgement")
    return decisions, review["acknowledgements"]


def audit(
    before_bytes: bytes,
    after_bytes: bytes,
    review: dict[str, Any] | None = None,
    *,
    include_text: bool = False,
) -> dict[str, Any]:
    """Return deterministic accounting; perform no filesystem or network I/O."""
    before = parse_document(before_bytes, "b")
    after = parse_document(after_bytes, "a")
    matches = _exact_matches(before, after)
    decisions, acknowledgements = _validate_review(review, before, after, matches)
    target_by_id = {block.id: block for block in after.blocks}
    findings: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    used_targets = {block.id for block in matches.values()}
    duplicate_targets: dict[tuple[str, str], list[str]] = defaultdict(list)
    for block in after.blocks:
        key = (block.kind, block.text)
        if len(duplicate_targets[key]) < 20:
            duplicate_targets[key].append(block.id)

    def finding(kind: str, source: str | None, targets: list[str], token: str | None = None) -> None:
        identity = [kind, source, targets, token]
        entry: dict[str, Any] = {
            "id": "f-" + digest(canonical_json(identity))[:20],
            "kind": kind, "source_id": source, "target_ids": targets,
            "acknowledged": False,
        }
        if token is not None:
            entry["value_sha256"] = digest(token)
            if include_text:
                entry["value"] = token
        findings.append(entry)

    for source in before.blocks:
        decision = decisions.get(source.id)
        record: dict[str, Any] = {
            "source_id": source.id, "disposition": "unaccounted",
            "target_ids": [], "human_approved": False,
        }
        if source.id in matches:
            target = matches[source.id]
            record.update(disposition="preserved", target_ids=[target.id])
            if source.context != target.context:
                finding("heading_context_changed", source.id, [target.id])
            if source.blanks_before != target.blanks_before:
                finding("block_spacing_changed", source.id, [target.id])
        elif decision and decision["approved"]:
            targets = [target_by_id[tid] for tid in decision["target_ids"]]
            record.update(
                disposition=decision["disposition"],
                target_ids=list(decision["target_ids"]), human_approved=True,
            )
            used_targets.update(decision["target_ids"])
            # Duplicate identity is checked literally by the review validator.
            if decision["disposition"] == "absorbed":
                available: dict[str, set[str]] = defaultdict(set)
                for target in targets:
                    for kind, tokens in protected_tokens(target).items():
                        available[kind].update(tokens)
                for kind, tokens in protected_tokens(source).items():
                    for token in sorted(tokens - available[kind]):
                        finding("missing_" + kind, source.id, record["target_ids"], token)
                if source.kind == "code":
                    finding("code_block_changed", source.id, record["target_ids"])
                if source.kind != "heading" and not any(source.context == target.context for target in targets):
                    finding("heading_context_changed", source.id, record["target_ids"])
        else:
            # A candidate is never silently accepted, even for literal duplicates.
            record["duplicate_candidates"] = duplicate_targets[(source.kind, source.text)]
        records.append(record)

    positions = [matches[block.id].index for block in before.blocks if block.id in matches]
    if any(left > right for left, right in zip(positions, positions[1:])):
        finding("preserved_block_order_changed", None, [])
    if before.trailing_blank_lines != after.trailing_blank_lines:
        finding("trailing_blank_lines_changed", None, [])
    if before.final_newline != after.final_newline:
        finding("final_newline_changed", None, [])

    findings_by_id = {entry["id"]: entry for entry in findings}
    seen: set[str] = set()
    for ack in acknowledgements:
        fid = ack["finding_id"]
        if fid not in findings_by_id or fid in seen:
            raise AuditError("Acknowledgement must name a unique finding in this exact audit.")
        seen.add(fid)
        if ack["approved"]:
            findings_by_id[fid]["acknowledged"] = True
    counts = {name: sum(item["disposition"] == name for item in records)
              for name in ("preserved", "duplicate", "absorbed", "unaccounted")}
    unresolved = sum(not finding["acknowledged"] for finding in findings)
    reviewed = any(record["human_approved"] for record in records) or any(f["acknowledged"] for f in findings)
    if counts["unaccounted"] or unresolved:
        status = "NEEDS_REVIEW"
    elif before.raw == after.raw:
        status = "EXACT"
    elif reviewed:
        status = "REVIEWED"
    else:
        status = "COVERED"
    report = {
        "schema_version": SCHEMA, "tool": "Edit Auditor", "tool_version": VERSION,
        "status": status,
        "meaning": {
            "EXACT": "Input bytes are identical.",
            "COVERED": "All source blocks match literally after line-ending normalization; this is not rendering or semantic equivalence.",
            "REVIEWED": "Coverage relies on explicit human assertions and/or acknowledgements; this is not proof of semantic equivalence.",
            "NEEDS_REVIEW": "Unaccounted source blocks or unacknowledged findings remain.",
        }[status],
        "before": {"sha256": before.sha256, "bytes": len(before.raw), "blocks": len(before.blocks)},
        "after": {"sha256": after.sha256, "bytes": len(after.raw), "blocks": len(after.blocks)},
        "raw_bytes_equal": before.raw == after.raw,
        "summary": {**counts, "unacknowledged_findings": unresolved,
                    "acknowledged_findings": len(findings) - unresolved,
                    "unmapped_output_blocks": sum(b.id not in used_targets for b in after.blocks)},
        "records": records,
        "findings": findings,
        "unmapped_output_ids": [b.id for b in after.blocks if b.id not in used_targets],
        "inventory": {
            "before": [b.public(include_text) for b in before.blocks],
            "after": [b.public(include_text) for b in after.blocks],
        },
        "review_sha256": digest(canonical_json(review)) if review is not None else None,
        "privacy": {
            "source_text_included": include_text,
            "source_paths_included": False,
            "notice": "Fingerprints and document structure can still be sensitive. Reports are not anonymized.",
        },
        "limitations": [
            "Conservative segmentation, not a complete CommonMark/Notion AST or rendered-document comparison.",
            "Literal coverage cannot establish truth, contextual meaning, authorship, or permission.",
            "Human review is self-attested, not identity-authenticated or cryptographically signed.",
            "Protected-token findings are heuristic; absence of findings is not proof of preservation.",
            "New output content is listed as unmapped; it is not fact-checked or authorized.",
            "Inputs are untrusted data. Links, code, and embedded directives are never executed.",
        ],
    }
    return report


def make_review_template(report: dict[str, Any], existing_review: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create pending items only; preserve previously supplied decisions.

    The caller must obtain report with audit(..., existing_review). This check
    prevents pairing an arbitrary existing review with an unrelated report.
    """
    if existing_review is not None and digest(canonical_json(existing_review)) != report["review_sha256"]:
        raise AuditError("Existing review was not used to produce this report.")
    decisions = copy.deepcopy(existing_review["decisions"]) if existing_review else []
    present = {item["source_id"] for item in decisions}
    for record in report["records"]:
        if record["disposition"] != "unaccounted" or record["source_id"] in present:
            continue
        candidates = record.get("duplicate_candidates", [])
        decisions.append({
            "source_id": record["source_id"],
            "disposition": "duplicate" if candidates else "absorbed",
            "target_ids": candidates[:1],
            "approved": False, "reviewer": "", "rationale": "",
        })
    acknowledgements = copy.deepcopy(existing_review["acknowledgements"]) if existing_review else []
    known = {item["finding_id"] for item in acknowledgements}
    acknowledgements.extend(
        {"finding_id": f["id"], "approved": False, "reviewer": "", "rationale": ""}
        for f in report["findings"] if f["id"] not in known
    )
    return {
        "schema_version": SCHEMA, "created_with": f"Edit Auditor {VERSION}",
        "before_sha256": report["before"]["sha256"],
        "after_sha256": report["after"]["sha256"],
        "decisions": decisions,
        "acknowledgements": acknowledgements,
    }


def markdown_report(report: dict[str, Any]) -> str:
    """Source-free report by default; opt-in text goes in inert fenced blocks."""
    summary = report["summary"]
    lines = [
        "# Edit Auditor report", "", f"**Status: {report['status']}**", "",
        report["meaning"], "",
        "| Source disposition | Blocks |", "| --- | ---: |",
    ]
    for name in ("preserved", "duplicate", "absorbed", "unaccounted"):
        lines.append(f"| {name} | {summary[name]} |")
    lines.extend([
        "", f"Unacknowledged findings: **{summary['unacknowledged_findings']}**.",
        f"Unmapped output blocks: **{summary['unmapped_output_blocks']}**. These are not fact-checked.",
        "", "## Source-to-output accounting", "",
        "| Source ID | Disposition | Output IDs |",
        "| --- | --- | --- |",
    ])
    for record in report["records"]:
        lines.append(f"| `{record['source_id']}` | {record['disposition']} | " +
                     ", ".join(f"`{target}`" for target in record["target_ids"]) + " |")
    lines.extend(["", "## Findings", ""])
    if not report["findings"]:
        lines.append("No heuristic findings. This is not a semantic guarantee.")
    for item in report["findings"]:
        state = "acknowledged by a reviewer" if item["acknowledged"] else "needs review"
        lines.append(f"- `{item['id']}` · `{item['kind']}` · {state}")
    if report["privacy"]["source_text_included"]:
        lines.extend(["", "## Explicitly requested source text", ""])
        for role in ("before", "after"):
            for block in report["inventory"][role]:
                text = block["text"]
                longest = max((len(m.group()) for m in re.finditer(r"`+", text)), default=0)
                fence = "`" * max(3, longest + 1)
                lines.extend([f"### {role}: {block['id']}", "", fence + "text", text, fence, ""])
    lines.extend(["", "## Limits and privacy", "", report["privacy"]["notice"], ""])
    lines.extend("- " + value for value in report["limitations"])
    return "\n".join(lines) + "\n"