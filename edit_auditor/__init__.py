"""Preservation-first, local-only Markdown auditing.

No source document is written by this package. Human review is explicit,
snapshot-bound, and is never represented as a proof of semantic equivalence.
"""

__version__ = "0.1.0"

from .core import AuditError, audit, make_review_template

__all__ = ["AuditError", "audit", "make_review_template", "__version__"]