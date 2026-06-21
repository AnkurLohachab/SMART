"""Emit the in-scope canonical provisions as Markdown plus LaTeX/PDF."""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARTITION = ROOT / "sample_results" / "partition.json"
COVERAGE = ROOT / "vocabulary" / "coverage.csv"
DST_MD = ROOT / "sample_results" / "in_scope_provisions.md"
DST_PDF = ROOT / "sample_results" / "in_scope_provisions.pdf"
DST_TEX = ROOT / "sample_results" / "in_scope_provisions.tex"

PLATFORM_COMPONENTS = {"Schema", "Lifecycle", "Schema+Lifecycle",
                       "Lifecycle+Chain", "Schema+Lifecycle+Chain", "Chain"}
UNKNOWN_PREFIX = "Unknown_"

DOC_NAMES = {
    "eu_ai_act_2024_1689":      "EU AI Act 2024/1689",
    "eu_mdr_2017_745":          "EU MDR 2017/745",
    "fda_ai_ml_action_plan_2021": "FDA AI/ML SaMD Action Plan (2021)",
    "fda_pccp_guidance_2024":   "FDA PCCP guidance (2024)",
    "fda_lifecycle_draft_2025": "FDA lifecycle management draft guidance (2025)",
    "tripod_ai_2024":           "TRIPOD+AI (2024)",
}


def _is_fully_canonicalised(entry: dict) -> bool:
    return not (entry["bearer"].startswith(UNKNOWN_PREFIX)
                or entry["predicate"].startswith(UNKNOWN_PREFIX)
                or entry["artefact"].startswith(UNKNOWN_PREFIX))


def _coverage_lookup() -> dict[str, dict]:
    out: dict[str, dict] = {}
    with COVERAGE.open() as f:
        for r in csv.DictReader(f):
            out[r["artefact"]] = r
    return out


def _format_quote(text: str, max_chars: int = 600) -> str:
    text = " ".join(text.split())
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "…"
    return "> " + text


def _provision_block(entry: dict, cov: dict) -> list[str]:
    triple = f"({entry['bearer']}, {entry['predicate']}, {entry['artefact']})"
    sources = entry["sources"]
    verbatims = entry["verbatims"]
    extractors = entry["extractors"]

    lines = [f"#### `{triple}`\n"]
    lines.append(f"- **SMART component:** {cov['smart_component']}")
    lines.append(f"- **SMART section:** {cov['smart_section']}")
    if cov.get("note"):
        lines.append(f"- **Coverage note:** {cov['note']}")
    lines.append(f"- **Extractors:** {', '.join(set(extractors)) or '—'}")
    lines.append(f"- **Restated in {len(sources)} paragraph(s):**\n")
    for (doc_id, locator), verbatim in zip(sources, verbatims):
        doc_label = DOC_NAMES.get(doc_id, doc_id)
        lines.append(f"  - *{doc_label} — {locator}*")
        lines.append("    " + _format_quote(verbatim).replace("\n", "\n    "))
        lines.append("")
    return lines


def _tex_escape(s: str) -> str:
    out = s.replace("\\", r"\textbackslash{}")
    for a, b in (("&", r"\&"), ("%", r"\%"), ("$", r"\$"),
                 ("#", r"\#"), ("_", r"\_"),
                 ("{", r"\{"), ("}", r"\}"),
                 ("~", r"\textasciitilde{}"),
                 ("^", r"\textasciicircum{}"),
                 ("<", r"\textless{}"), (">", r"\textgreater{}")):
        out = out.replace(a, b)
    repl = {
        "–": "--", "—": "---",
        "‘": "`", "’": "'",
        "“": "``", "”": "''",
        " ": " ",
        "­": "",
        "·": r"$\cdot$",
        "•": r"$\bullet$",
        "…": "\\ldots{}",
    }
    for a, b in repl.items():
        out = out.replace(a, b)
    return out


def _tex_quote(text: str, max_chars: int = 600) -> str:
    text = " ".join(text.split())
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "…"
    return _tex_escape(text)


def write_latex(in_scope: list, dst: Path) -> None:
    """Write a self-contained LaTeX document grouped by SMART component."""
    groups: dict[str, list] = {}
    for entry, cov in in_scope:
        groups.setdefault(cov["smart_component"], []).append((entry, cov))
    for k in groups:
        groups[k].sort(key=lambda ec: (-len(ec[0]["sources"]),
                                        ec[0]["bearer"], ec[0]["predicate"],
                                        ec[0]["artefact"]))

    out: list[str] = []
    out.append(r"\documentclass[10pt,a4paper]{article}")
    out.append(r"\usepackage[utf8]{inputenc}")
    out.append(r"\usepackage[T1]{fontenc}")
    out.append(r"\usepackage{lmodern}")
    out.append(r"\usepackage[margin=1in]{geometry}")
    out.append(r"\usepackage{booktabs}")
    out.append(r"\usepackage{longtable}")
    out.append(r"\usepackage{hyperref}")
    out.append(r"\usepackage{xcolor}")
    out.append(r"\usepackage{enumitem}")
    out.append(r"\usepackage{microtype}")
    out.append(r"\hypersetup{colorlinks=true, urlcolor=blue, linkcolor=black}")
    out.append(r"\setlength{\parindent}{0pt}")
    out.append(r"\setlength{\parskip}{0.4em}")
    out.append(r"")
    out.append(r"\title{In-scope canonical provisions \\ \large SMART Model "
               r"Card Platform --- Legal-evaluation Track}")
    out.append(r"\author{Auto-generated from \texttt{sample_results/partition.json} + "
               r"\texttt{vocabulary/coverage.csv}}")
    out.append(r"\date{}")
    out.append(r"\begin{document}")
    out.append(r"\maketitle")
    out.append(r"\tableofcontents")
    out.append(r"\newpage")
    out.append(r"")
    out.append(r"\section*{About this document}")
    out.append(rf"This document lists the \textbf{{{len(in_scope)}}} canonical "
               r"provisions extracted from a six-document regulatory corpus "
               r"that are (a)~\emph{fully canonicalised} (actor, action, and "
               r"artefact all in the closed vocabulary), and (b)~\emph{within "
               r"SMART's design scope} --- i.e.\ attested by at least one "
               r"platform component (\texttt{Schema}, \texttt{Lifecycle}, "
               r"\texttt{Schema+Lifecycle}, or \texttt{Lifecycle+Chain}).")
    out.append(r"")
    out.append(r"Each entry shows:")
    out.append(r"\begin{itemize}[leftmargin=*]")
    out.append(r"  \item the canonical triple \texttt{(bearer, predicate, "
               r"artefact)};")
    out.append(r"  \item the SMART component(s) capable of attestation;")
    out.append(r"  \item the model-card section the artefact maps to;")
    out.append(r"  \item the verbatim source-paragraph quote(s) that produced "
               r"the provision.")
    out.append(r"\end{itemize}")
    out.append(r"All quotes are taken directly from the regulatory PDFs "
               r"committed in \texttt{legal\_evaluation/docs/}; no paraphrase "
               r"is applied. Document is runs end-to-end with "
               r"\texttt{python3 scripts/in\_scope\_provisions\_doc.py} on a "
               r"warm extraction cache --- no LLM calls.")
    out.append(r"")

    out.append(r"\section{Summary}")
    out.append(r"\begin{tabular}{lr}")
    out.append(r"\toprule")
    out.append(r"Component & \# Provisions \\")
    out.append(r"\midrule")
    for comp in ["Schema", "Lifecycle", "Schema+Lifecycle",
                 "Lifecycle+Chain", "Schema+Lifecycle+Chain", "Chain"]:
        if comp in groups:
            out.append(rf"\texttt{{{_tex_escape(comp)}}} & {len(groups[comp])} \\")
    out.append(rf"\midrule \textbf{{Total}} & \textbf{{{len(in_scope)}}} \\")
    out.append(r"\bottomrule")
    out.append(r"\end{tabular}")
    out.append(r"")

    for comp in ["Schema", "Lifecycle", "Schema+Lifecycle",
                 "Lifecycle+Chain", "Schema+Lifecycle+Chain", "Chain"]:
        items = groups.get(comp, [])
        if not items:
            continue
        out.append(rf"\section{{{_tex_escape(comp)} ({len(items)} provisions)}}")
        for entry, cov in items:
            triple = (f"({entry['bearer']}, {entry['predicate']}, "
                      f"{entry['artefact']})")
            out.append(rf"\subsection*{{\texttt{{{_tex_escape(triple)}}}}}")
            out.append(r"\begin{itemize}[leftmargin=*]")
            out.append(rf"  \item \textbf{{Component:}} \texttt{{{_tex_escape(cov['smart_component'])}}}")
            out.append(rf"  \item \textbf{{Section:}} {_tex_escape(cov['smart_section'])}")
            if cov.get("note"):
                out.append(rf"  \item \textbf{{Coverage note:}} {_tex_escape(cov['note'])}")
            extractors_str = ", ".join(sorted(set(entry['extractors']))) or "---"
            out.append(rf"  \item \textbf{{Extractors:}} {_tex_escape(extractors_str)}")
            out.append(rf"  \item \textbf{{Restated in {len(entry['sources'])} paragraph(s):}}")
            out.append(r"\end{itemize}")
            for (doc_id, locator), verbatim in zip(entry["sources"], entry["verbatims"]):
                doc_label = DOC_NAMES.get(doc_id, doc_id)
                out.append(rf"\textit{{{_tex_escape(doc_label)} --- {_tex_escape(locator)}}}")
                out.append(r"\begin{quote}")
                out.append(_tex_quote(verbatim))
                out.append(r"\end{quote}")
            out.append(r"")

    out.append(r"\end{document}")
    dst.write_text("\n".join(out))


def main() -> int:
    if not PARTITION.exists():
        print(f"ERROR: missing {PARTITION}", file=sys.stderr)
        return 2
    if not COVERAGE.exists():
        print(f"ERROR: missing {COVERAGE}", file=sys.stderr)
        return 2

    part = json.loads(PARTITION.read_text())
    cov_by_artefact = _coverage_lookup()

    in_scope = []
    for entry in part:
        if not _is_fully_canonicalised(entry):
            continue
        cov = cov_by_artefact.get(entry["artefact"])
        if not cov:
            continue
        if cov["smart_component"] not in PLATFORM_COMPONENTS:
            continue
        in_scope.append((entry, cov))

    groups: dict[str, list] = {}
    for entry, cov in in_scope:
        groups.setdefault(cov["smart_component"], []).append((entry, cov))
    for k in groups:
        groups[k].sort(key=lambda ec: (-len(ec[0]["sources"]),
                                        ec[0]["bearer"], ec[0]["predicate"],
                                        ec[0]["artefact"]))

    out: list[str] = []
    out.append("# In-scope canonical provisions\n")
    out.append(f"**{len(in_scope)} provisions** that are fully canonicalised "
               "(actor, action, and artefact all in the closed vocabulary) "
               "and attested by at least one SMART platform component "
               "(`Schema`, `Lifecycle`, `Schema+Lifecycle`, or `Lifecycle+Chain`).\n")
    out.append("Each entry shows the canonical triple, the SMART component "
               "that attests it, the section of the model-card template it "
               "maps to, and the verbatim source-paragraph quotes that "
               "produced it. Sources are taken directly from the "
               "regulatory documents committed in `requirements-analysis/docs/`; "
               "no paraphrase is applied.\n")
    out.append("Generated by `scripts/in_scope_provisions_doc.py` from "
               "`sample_results/partition.json` + `vocabulary/coverage.csv`. "
               "Runs end-to-end with no LLM calls.\n")

    out.append("## Summary\n")
    out.append("| Component | # Provisions |")
    out.append("|---|---|")
    for comp in ["Schema", "Lifecycle", "Schema+Lifecycle",
                 "Lifecycle+Chain", "Schema+Lifecycle+Chain", "Chain"]:
        if comp in groups:
            out.append(f"| `{comp}` | {len(groups[comp])} |")
    out.append(f"| **Total** | **{len(in_scope)}** |\n")

    for comp in ["Schema", "Lifecycle", "Schema+Lifecycle",
                 "Lifecycle+Chain", "Schema+Lifecycle+Chain", "Chain"]:
        items = groups.get(comp, [])
        if not items:
            continue
        out.append(f"## {comp} ({len(items)} provisions)\n")
        for entry, cov in items:
            out.extend(_provision_block(entry, cov))

    DST_MD.write_text("\n".join(out))
    print(f"wrote {DST_MD}  ({sum(1 for _ in DST_MD.read_text().splitlines())} lines)")

    write_latex(in_scope, DST_TEX)
    print(f"wrote {DST_TEX}  ({sum(1 for _ in DST_TEX.read_text().splitlines())} lines)")

    if shutil.which("pandoc"):
        cmd = ["pandoc", str(DST_MD), "-o", str(DST_PDF),
               "--pdf-engine=xelatex" if shutil.which("xelatex") else "--pdf-engine=pdflatex",
               "-V", "geometry:margin=1in",
               "-V", "fontsize=10pt",
               "--toc"]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"wrote {DST_PDF}")
        except subprocess.CalledProcessError as e:
            print(f"pandoc failed; markdown is at {DST_MD}", file=sys.stderr)
            print(f"  cmd: {' '.join(cmd)}", file=sys.stderr)
            print(f"  stderr: {e.stderr[:500]}", file=sys.stderr)
            return 1
        except FileNotFoundError:
            print(f"PDF engine not found; markdown only at {DST_MD}",
                  file=sys.stderr)
    else:
        print(f"pandoc not available; markdown only at {DST_MD}")
        print(f"To make a PDF on the host:")
        print(f"  pandoc {DST_MD} -o {DST_PDF} --pdf-engine=xelatex --toc")

    return 0


if __name__ == "__main__":
    sys.exit(main())
