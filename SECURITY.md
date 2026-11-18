# Security and data handling

This is a local experimental tool, not a security product or certification.

- No network clients, telemetry, LLM calls or source-code execution are present.
- Treat source files and review records as untrusted data.
- Source and review reads are size-bounded and regular-file checked.
- Report files are new-only; no overwrite flag is provided.
- Whole-file fingerprints bind snapshots, not identity or legal authority.
- Source text is opt-in; structural metadata and fingerprints can still be sensitive.
- A caller's shell or another filesystem actor is outside the tool's no-write boundary.
- Unsupported input returns an error. A partial file after an I/O interruption is not a valid report.

Do not include confidential documents in a public bug report. A minimal synthetic
reproduction is the appropriate evidence. No public issue tracker is asserted
until the owner creates one.