"""Local manuscript evidence helpers; copied into each independent paper."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


class Evidence:
    """Evaluate result expressions and keep the exact displayed value and inputs."""

    def __init__(self, paper_dir, context):
        self.paper_dir = Path(paper_dir)
        self.context = context
        self.claims = []

    def value(self, expression, fmt=".3f"):
        value = eval(expression, {"__builtins__": {}}, self.context)
        shown = format(value, fmt)
        self.claims.append(dict(expression=expression, format=fmt, displayed=shown))
        return shown

    def save(self, spec):
        sources = {}
        for path in sorted((self.paper_dir.parent / "results").rglob("*.csv")):
            sources[str(path.relative_to(self.paper_dir.parent)).replace("\\", "/")] = hashlib.sha256(path.read_bytes()).hexdigest()
        (self.paper_dir / "numeric_provenance.json").write_text(
            json.dumps(dict(claims=self.claims, sources=sources), indent=2, ensure_ascii=False), encoding="utf-8")
        (self.paper_dir / "manuscript_spec.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")

    def capture(self, value, expression, fmt="", conversion=-1):
        """Trace an existing builder's formatted expression without changing it.

        A separate audit reexecutes the builder from the hashed CSV inputs and
        compares this sequence, including each source expression and display.
        This preserves existing data-driven manuscripts during focused edits.
        """
        if conversion == 115:
            value = str(value)
        elif conversion == 114:
            value = repr(value)
        elif conversion == 97:
            value = ascii(value)
        shown = format(value, fmt)
        self.claims.append(dict(expression=expression, format=fmt, displayed=shown))
        return shown


def author_meta(paper_dir, title):
    author = json.loads((Path(paper_dir) / "author.json").read_text(encoding="utf-8-sig"))
    return dict(title=title, authors=[dict(name=author["name"], sup="1*")],
                affiliations=[author["affiliation"] + "  •  ORCID: " + author["orcid"]],
                corresponding=author["name"], email=author["email"], short_author=author["short_author"])


def declarations(paper_dir, paper_id):
    author = json.loads((Path(paper_dir) / "author.json").read_text(encoding="utf-8-sig"))
    return [
        ("Ethics Committee Approval", "Not applicable. Only synthetic tasks and simulated service data were used; no human participants or personal data were involved."),
        ("Author Contributions", "Conceptualization, methodology, software, formal analysis, writing – original draft, writing – review and editing: " + author["name"] + "."),
        ("Conflict of Interest", "The author declares no conflict of interest."),
        ("Funding", "This research received no external funding."),
        ("Data and Code Availability", "Code, data and generated results are provided as supplementary material and are available from the corresponding author. Supplementary file: supplementary_" + paper_id.lower() + ".zip."),
    ]
