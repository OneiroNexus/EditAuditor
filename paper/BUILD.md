# Building the paper PDF

The Markdown is the editable source. The supplied renderer supports only the
simple headings, tables, paragraphs, callouts and fenced blocks used in this
paper; it is not a general Markdown conversion package.

Optional local document-build requirements: ReportLab and a local Arial or
DejaVu Sans font pair. These are not runtime dependencies of Edit Auditor.
The renderer does not fetch fonts, images or other resources.

From the repository folder:

```sh
python paper/render_pdf.py
```

This rebuilds only the generated paper PDF from its Markdown source. It does not
edit the Markdown, tool code, workspace pages or evidence receipts. Review the
rendered pages after any content or layout change.
