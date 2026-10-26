"""Recompute the manuscript and audit every numeric token against provenance.

No approximate numeric matching to unrelated CSV cells is permitted. Dynamic
claims must be identical when their saved expressions are reevaluated. The
entire numeric sequence in the submitted OOXML must equal an independent
rebuild from current inputs. Literal numbers require an explicit constant,
structural-number or verified-reference explanation in the audit report.
"""
from __future__ import annotations

import hashlib
import datetime
import os
import json
import re
import runpy
import sys
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

NUM = re.compile(r"(?<![A-Za-z0-9])[-−+]?\d+(?:,\d{3})*(?:\.\d+)?(?:[eE][-+]?\d+)?%?")
W = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def paragraphs(path):
    out = []
    with zipfile.ZipFile(path) as archive:
        for name in ["word/document.xml"] + sorted(n for n in archive.namelist() if re.match(r"word/(header|footer)\d+\.xml$", n)):
            root = etree.fromstring(archive.read(name))
            out.extend((name, "".join(p.xpath(".//w:t/text()", namespaces=W))) for p in root.xpath(".//w:p", namespaces=W))
    return out


def main():
    here = Path(__file__).resolve().parent
    saved = json.loads((here / "numeric_provenance.json").read_text(encoding="utf-8"))
    for rel, expected in saved["sources"].items():
        assert hashlib.sha256((here.parent / rel).read_bytes()).hexdigest() == expected, f"Stale manuscript input: {rel}"
    namespace = runpy.run_path(str(here / "build_manuscript.py"), run_name="number_audit")
    evidence = namespace["E"]
    assert evidence.claims == saved["claims"], "Recomputed result expressions differ from saved provenance"
    spec, actual = namespace["spec"], Path(namespace["OUT"])
    from build_docx import build
    with tempfile.TemporaryDirectory() as tmp:
        rebuilt = Path(tmp) / "recomputed.docx"
        build(spec, str(rebuilt))
        expected_tokens = [(part, NUM.findall(text)) for part, text in paragraphs(rebuilt) if NUM.search(text)]
    actual_paras = paragraphs(actual)
    assert [(part, NUM.findall(text)) for part, text in actual_paras if NUM.search(text)] == expected_tokens, "DOCX numbers differ from a fresh computation"
    constants = json.loads((here / "design_constants.json").read_text(encoding="utf-8"))
    build_date = os.environ.get("BUILD_DATE", datetime.date.today().strftime("%d.%m.%Y"))
    for component in NUM.findall(build_date):
        constants[component] = "Actual build-date metadata; independent of experiment results."
    registry = {}
    for claim in evidence.claims:
        for token in NUM.findall(claim["displayed"]):
            registry.setdefault(token.lstrip("+−-").rstrip("%"), []).append(claim["expression"])
    ref_text = " ".join(spec["references"])
    ref_numbers = set(NUM.findall(ref_text))
    rows, unexplained = [], []
    for part, text in actual_paras:
        for token in NUM.findall(text):
            key = token.lstrip("+−-").rstrip("%")
            reason = None
            if key in registry:
                reason = "recomputed result expression: " + " | ".join(registry[key])
            elif token in ref_numbers:
                reason = "verified reference metadata (see literature/verified_sources.md)"
            elif key in constants or token in constants:
                reason = "documented design constant: " + constants.get(key, constants.get(token))
            elif re.match(r"^(?:\d+\.)+\s", text) or re.match(r"^(Table|Figure|Equation) \d+", text):
                reason = "structural heading/caption numbering"
            elif re.search(r"(?:Section|Table|Figure|Equation|RQ|Study)\s*" + re.escape(token), text):
                reason = "structural cross-reference"
            row = dict(part=part, value=token, context=text, evidence=reason)
            rows.append(row)
            if reason is None:
                unexplained.append(row)
    report = dict(numeric_occurrences=len(rows), dynamic_claims=len(evidence.claims), unexplained=unexplained, audit=rows)
    (here / "number_audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Number audit: {len(rows)} occurrences, {len(evidence.claims)} recomputed result expressions, {len(unexplained)} unexplained")
    assert not unexplained, "Document literal constants before passing this gate"


if __name__ == "__main__":
    main()
