"""Fill the DarnerView Word template with a manuscript spec.

Usage (from a manuscript module):  build(spec, out_path)
Spec keys: meta (dict), abstract (str), keywords (list), blocks (list), declarations (list of (label, text)),
references (list of str). Inline markup in text: **bold**, *italic*, ^{sup}, _{sub}.
Cross references: {T:key} -> "Table N", {F:key} -> "Figure N", {E:key} -> "Equation N" (keys declared on blocks).
"""
from __future__ import annotations

import copy
import datetime
import io
import os
import re
import zipfile

from lxml import etree
from PIL import Image

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
NS = {"w": W}
_here = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = next((c for c in (os.path.join(_here, "DarnerView templete.docx"),
                             os.path.join(_here, "..", "DarnerView templete.docx"),
                             os.path.join(_here, "..", "..", "DarnerView templete.docx")) if os.path.exists(c)),
                os.path.join(_here, "DarnerView templete.docx"))


def q(tag):
    return "{%s}%s" % (W, tag)


def el(tag, **attrs):
    e = etree.Element(q(tag))
    for k, v in attrs.items():
        e.set(q(k), str(v))
    return e


TOKEN = re.compile(r"(\*\*.+?\*\*|\*.+?\*|\^\{.+?\}|_\{.+?\})")


def parse_markup(text):
    """-> list of (string, flags) with flags subset of {'b','i','sup','sub'}"""
    out = []
    for part in TOKEN.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            out.append((part[2:-2], {"b"}))
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            out.append((part[1:-1], {"i"}))
        elif part.startswith("^{"):
            out.append((part[2:-1], {"sup"}))
        elif part.startswith("_{"):
            out.append((part[2:-1], {"sub"}))
        else:
            out.append((part, set()))
    return out


def make_run(text, flags=(), base_rpr=None):
    r = el("r")
    rpr = copy.deepcopy(base_rpr) if base_rpr is not None else el("rPr")
    for f in flags:
        if f == "b":
            for t in ("b", "bCs"):
                if rpr.find(q(t)) is None:
                    rpr.append(el(t))
        elif f == "i":
            for t in ("i", "iCs"):
                if rpr.find(q(t)) is None:
                    rpr.append(el(t))
        elif f in ("sup", "sub"):
            va = el("vertAlign", val="superscript" if f == "sup" else "subscript")
            rpr.append(va)
    if len(rpr):
        r.append(rpr)
    t = el("t")
    t.text = text
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    r.append(t)
    return r


_MINUS = re.compile(r"(?<![\w\)\]])-(?=\d)")


def add_markup_runs(p, text, base_rpr=None):
    if "http" not in text:
        text = _MINUS.sub("−", text)
    for s, fl in parse_markup(text):
        p.append(make_run(s, fl, base_rpr))


def para(style=None, text="", ppr_extra=None, base_rpr=None):
    p = el("p")
    ppr = el("pPr")
    if style:
        ppr.append(el("pStyle", val=style))
    if ppr_extra is not None:
        for c in ppr_extra:
            ppr.append(c)
    if len(ppr):
        p.append(ppr)
    if text:
        add_markup_runs(p, text, base_rpr)
    return p


def rpr_of(p, idx=0):
    runs = p.findall(q("r"))
    r = runs[idx].find(q("rPr"))
    return copy.deepcopy(r) if r is not None else el("rPr")


def clear_runs(p):
    for c in list(p):
        if c.tag != q("pPr"):
            p.remove(c)


class Builder:
    def __init__(self, template=TEMPLATE):
        with zipfile.ZipFile(template) as z:
            self.files = {n: z.read(n) for n in z.namelist()}
        self.doc = etree.fromstring(self.files["word/document.xml"])
        self.body = self.doc.find(q("body"))
        self.kids = list(self.body)
        self.rels = etree.fromstring(self.files["word/_rels/document.xml.rels"])
        self.numbering = etree.fromstring(self.files["word/numbering.xml"])
        self.next_num = 10
        self.next_rid = 100
        self.next_img = 1
        self.media = {}
        self.proto = {k: copy.deepcopy(self.kids[i]) for k, i in dict(
            doi=0, rule=1, tag=2, title=3, authors=4, aff=5, corr=8, dates=9, blank=10, abs_h=11, abs_t=12, kw=13,
            copy=15, h1=17, h2=27, h3=33, body=18, quote=29, tcap=56, tnote=58, fcap=63, decl=81, ref=86,
            eq=48, tbl=57).items()}
        self.sect = self.kids[-1]

    # ------------------------------------------------------------- numbering helpers
    def new_list(self, kind):
        """kind 'ol' or 'ul' -> numId with restart."""
        abstract = "0" if kind == "ol" else "2"
        nid = self.next_num
        self.next_num += 1
        num = etree.SubElement(self.numbering, q("num"))
        num.set(q("numId"), str(nid))
        a = etree.SubElement(num, q("abstractNumId"))
        a.set(q("val"), abstract)
        ov = etree.SubElement(num, q("lvlOverride"))
        ov.set(q("ilvl"), "0")
        so = etree.SubElement(ov, q("startOverride"))
        so.set(q("val"), "1")
        return nid

    # ------------------------------------------------------------- blocks
    def heading(self, level, text):
        p = para(f"Heading{level}", text)
        return p

    def body_p(self, text):
        return para("ArticleBodyText", text)

    def list_items(self, kind, items):
        nid = self.new_list(kind)
        out = []
        for it in items:
            ppr_extra = []
            numpr = el("numPr")
            numpr.append(el("ilvl", val=0))
            numpr.append(el("numId", val=nid))
            ppr_extra.append(numpr)
            ppr_extra.append(el("spacing", after=60))
            out.append(para("ArticleBodyText", it, ppr_extra))
        return out

    def table(self, spec, number):
        cap = copy.deepcopy(self.proto["tcap"])
        clear_runs(cap)
        cap.append(make_run(f"Table {number}. ", {"b"}))
        cap.append(make_run(spec["caption"], {"i"}))
        header, rows = spec["header"], spec["rows"]
        ncol = len(header)
        total = 8700
        widths = spec.get("widths")
        if not widths:
            first = 2600 if ncol > 3 else 3000
            rest = (total - first) // (ncol - 1)
            widths = [first] + [rest] * (ncol - 1)
        tbl = copy.deepcopy(self.proto["tbl"])
        for c in list(tbl):
            if c.tag in (q("tr"), q("tblGrid")):
                tbl.remove(c)
        tw = tbl.find(q("tblPr")).find(q("tblW"))
        tw.set(q("w"), str(sum(widths)))
        grid = el("tblGrid")
        for w in widths:
            grid.append(el("gridCol", w=w))
        tbl.append(grid)
        fs = spec.get("font_half_points", 17)

        def cell(text, w, top, bottom, bold, left):
            tc = el("tc")
            pr = el("tcPr")
            pr.append(el("tcW", w=w, type="dxa"))
            b = el("tcBorders")
            for side, (val, sz) in (("top", top), ("left", ("none", 0)), ("bottom", bottom), ("right", ("none", 0))):
                x = el(side, val=val, sz=sz, space=0, color="000000" if val != "none" else "FFFFFF")
                b.append(x)
            pr.append(b)
            mar = el("tcMar")
            for side, wv in (("top", 50), ("left", 80), ("bottom", 50), ("right", 80)):
                mar.append(el(side, w=wv, type="dxa"))
            pr.append(mar)
            pr.append(el("vAlign", val="center"))
            tc.append(pr)
            p = el("p")
            ppr = el("pPr")
            ppr.append(el("spacing", after=0, line=240, lineRule="auto"))
            if not left:
                ppr.append(el("jc", val="center"))
            p.append(ppr)
            rpr = el("rPr")
            rf = el("rFonts", ascii="Calibri", eastAsia="Calibri", hAnsi="Calibri", cs="Calibri")
            rpr.append(rf)
            if bold:
                rpr.append(el("b"))
                rpr.append(el("bCs"))
            rpr.append(el("sz", val=fs))
            rpr.append(el("szCs", val=fs))
            add_markup_runs(p, str(text), rpr)
            tc.append(p)
            return tc

        def row(vals, top, bottom, bold, is_header=False):
            tr = el("tr")
            trpr = el("trPr")
            trpr.append(el("cantSplit"))
            if is_header:
                trpr.append(el("tblHeader"))
            tr.append(trpr)
            for i, (v, w) in enumerate(zip(vals, widths)):
                tr.append(cell(v, w, top, bottom, bold, left=(i == 0)))
            return tr

        none = ("none", 0)
        tbl.append(row(header, ("single", 8), ("single", 4), True, True))
        for ri, r in enumerate(rows):
            last = ri == len(rows) - 1
            tbl.append(row(r, none, ("single", 8) if last else none, False))
        note = None
        if spec.get("note"):
            note = copy.deepcopy(self.proto["tnote"])
            clear_runs(note)
            note.append(make_run("Note. ", {"i"}))
            add_markup_runs(note, spec["note"])
        keep = el("keepNext")
        cap.find(q("pPr")).append(keep)
        return [cap, tbl] + ([note] if note is not None else [para("ArticleBodyText", "", [el("spacing", after=60)])])

    def figure(self, spec, number):
        path = spec["path"]
        with Image.open(path) as im:
            wpx, hpx = im.size
        width_cm = spec.get("width_cm", 15.0)
        cx = int(width_cm * 360000)
        cy = int(cx * hpx / wpx)
        name = f"image{self.next_img}.png"
        self.next_img += 1
        with open(path, "rb") as f:
            self.media["word/media/" + name] = f.read()
        rid = f"rId{self.next_rid}"
        self.next_rid += 1
        rel = etree.SubElement(self.rels, "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
        rel.set("Id", rid)
        rel.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image")
        rel.set("Target", "media/" + name)
        alt = spec.get("alt", spec["caption"]).replace('"', "'")
        xml = f'''<w:r xmlns:w="{W}" xmlns:r="{R}" xmlns:wp="{WP}" xmlns:a="{A}" xmlns:pic="{PIC}"><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{number + 10}" name="Figure {number}" descr="{alt}"/><wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr><a:graphic><a:graphicData uri="{PIC}"><pic:pic><pic:nvPicPr><pic:cNvPr id="{number + 10}" name="{name}"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>'''
        p = el("p")
        ppr = el("pPr")
        ppr.append(el("keepNext"))
        ppr.append(el("spacing", before=120, after=0))
        ppr.append(el("jc", val="center"))
        p.append(ppr)
        p.append(etree.fromstring(xml))
        cap = copy.deepcopy(self.proto["fcap"])
        clear_runs(cap)
        cap.append(make_run(f"Figure {number}. ", {"b"}))
        add_markup_runs(cap, spec["caption"], rpr_italic())
        return [p, cap]

    def equation(self, spec, number):
        p = copy.deepcopy(self.proto["eq"])
        clear_runs(p)
        r = el("r")
        r.append(el("tab"))
        p.append(r)
        p.append(make_run(spec["text"], {"i"}))
        r2 = el("r")
        r2.append(el("tab"))
        t = el("t")
        t.text = f"({number})"
        r2.append(t)
        p.append(r2)
        return p


def rpr_italic():
    r = el("rPr")
    r.append(el("i"))
    r.append(el("iCs"))
    return r


def build(spec, out_path, template=TEMPLATE):
    B = Builder(template)
    meta = spec["meta"]
    # ---- numbering of tables / figures / equations
    counters = {"table": 0, "figure": 0, "eq": 0}
    labels = {}
    for kind, blk in spec["blocks"]:
        if kind in counters:
            counters[kind] += 1
            if blk.get("key"):
                labels[blk["key"]] = (kind, counters[kind])
    counters = {"table": 0, "figure": 0, "eq": 0}

    def xref(text):
        def sub(m):
            tag, key = m.group(1), m.group(2)
            kind, n = labels[key]
            return {"T": f"Table {n}", "F": f"Figure {n}", "E": f"Equation {n}"}[tag]
        return re.sub(r"\{([TFE]):(\w+)\}", sub, text)

    new = []
    # ---- top matter
    P = B.proto
    doi = copy.deepcopy(P["doi"])
    runs = doi.findall(q("r"))
    runs[1].find(q("t")).text = meta.get("doi", "to be assigned by the journal")
    new.append(doi)
    new.append(copy.deepcopy(P["rule"]))
    new.append(copy.deepcopy(P["tag"]))
    title = copy.deepcopy(P["title"])
    clear_runs(title)
    title_runs = B.kids[3].findall(q("r"))
    base = title_runs[0].find(q("rPr"))
    title.append(make_run(meta["title"], (), base))
    new.append(title)
    # authors
    authors = copy.deepcopy(P["authors"])
    r_name, r_sup, r_sep = (rpr_of(B.kids[4], 0), rpr_of(B.kids[4], 1), rpr_of(B.kids[4], 2))
    clear_runs(authors)
    for i, a in enumerate(meta["authors"]):
        authors.append(make_run(a["name"], (), r_name))
        authors.append(make_run(a.get("sup", "1"), (), r_sup))
        if i < len(meta["authors"]) - 1:
            authors.append(make_run(", ", (), r_sep))
    new.append(authors)
    for i, aff in enumerate(meta["affiliations"], 1):
        a = copy.deepcopy(P["aff"])
        runs = a.findall(q("r"))
        runs[0].find(q("t")).text = str(i)
        for r in runs[2:]:
            a.remove(r)
        for pe in a.findall(q("proofErr")):
            a.remove(pe)
        runs[1].find(q("t")).text = " " + aff
        new.append(a)
    corr = copy.deepcopy(P["corr"])
    runs = corr.findall(q("r"))
    for pe in corr.findall(q("proofErr")):
        corr.remove(pe)
    runs[0].find(q("t")).text = f"*Corresponding author: {meta['corresponding']}"
    runs[1].find(q("t")).text = f"  •  Email: {meta['email']}"
    for r in runs[2:]:
        corr.remove(r)
    new.append(corr)
    dates = copy.deepcopy(P["dates"])
    build_date = os.environ.get("BUILD_DATE", datetime.date.today().strftime("%d.%m.%Y"))
    dates.find(q("r")).find(q("t")).text = meta.get("dates", f"Received: {build_date}   •   Accepted: —   •   Published: —")
    new.append(dates)
    new.append(copy.deepcopy(P["blank"]))
    new.append(copy.deepcopy(P["abs_h"]))
    ab = copy.deepcopy(P["abs_t"])
    clear_runs(ab)
    add_markup_runs(ab, spec["abstract"])
    new.append(ab)
    kw = copy.deepcopy(P["kw"])
    runs = kw.findall(q("r"))
    runs[1].find(q("t")).text = "; ".join(spec["keywords"])
    new.append(kw)
    new.append(copy.deepcopy(P["blank"]))
    cp = copy.deepcopy(P["copy"])
    cruns = cp.findall(q("r"))
    cruns[0].find(q("t")).text = "© 2026 "
    for pe in cp.findall(q("proofErr")):
        cp.remove(pe)
    new.append(cp)
    new.append(copy.deepcopy(P["blank"]))

    # ---- body
    for kind, blk in spec["blocks"]:
        if kind in ("h1", "h2", "h3"):
            new.append(B.heading(int(kind[1]), blk))
        elif kind == "p":
            new.append(B.body_p(xref(blk)))
        elif kind in ("ol", "ul"):
            new.extend(B.list_items(kind, [xref(x) for x in blk]))
        elif kind == "quote":
            q_ = copy.deepcopy(P["quote"])
            clear_runs(q_)
            add_markup_runs(q_, xref(blk))
            new.append(q_)
        elif kind == "table":
            counters["table"] += 1
            b = dict(blk)
            b["note"] = xref(b["note"]) if b.get("note") else None
            b["rows"] = [[xref(str(c)) for c in r] for r in b["rows"]]
            new.extend(B.table(b, counters["table"]))
        elif kind == "figure":
            counters["figure"] += 1
            b = dict(blk)
            b["caption"] = xref(b["caption"])
            new.extend(B.figure(b, counters["figure"]))
        elif kind == "eq":
            counters["eq"] += 1
            new.append(B.equation(blk, counters["eq"]))
        else:
            raise ValueError(kind)

    # ---- declarations & references
    new.append(B.heading(1, "Declarations"))
    for label, text in spec["declarations"]:
        d = copy.deepcopy(P["decl"])
        clear_runs(d)
        d.append(make_run(label + ": ", {"b"}))
        add_markup_runs(d, text)
        new.append(d)
    new.append(B.heading(1, "References"))
    for ref in spec["references"]:
        r = copy.deepcopy(P["ref"])
        clear_runs(r)
        add_markup_runs(r, ref)
        new.append(r)

    for k in list(B.body):
        B.body.remove(k)
    for e in new:
        B.body.append(e)
    B.body.append(B.sect)

    # ---- headers
    h1 = B.files["word/header1.xml"].decode("utf8")
    h1 = h1.replace("Journal Name, 20XX, X(X), XX–XX", "DarnerView: Journal of Artificial Intelligence, 2026")
    h1 = h1.replace("Surname et al.", meta.get("short_author", "Author"))
    B.files["word/header1.xml"] = h1.encode("utf8")
    h2 = B.files["word/header2.xml"].decode("utf8")
    h2 = h2.replace("Year 20XX, Vol. X, No. X, pp. XX–XX", "Year 2026 • Manuscript submitted for review")
    h2 = h2.replace("e-ISSN: XXXX-XXXX", "e-ISSN: assigned by the journal")
    B.files["word/header2.xml"] = h2.encode("utf8")

    # ---- core properties
    core = B.files["docProps/core.xml"].decode("utf8")
    core = re.sub(r"<dc:title>.*?</dc:title>", f"<dc:title>{escape(meta['title'])}</dc:title>", core)
    if "<dc:title>" not in core:
        core = core.replace("</cp:coreProperties>", f"<dc:title>{escape(meta['title'])}</dc:title></cp:coreProperties>")
    B.files["docProps/core.xml"] = core.encode("utf8")

    # ---- write
    B.files["word/document.xml"] = etree.tostring(B.doc, xml_declaration=True, encoding="UTF-8", standalone=True)
    B.files["word/numbering.xml"] = etree.tostring(B.numbering, xml_declaration=True, encoding="UTF-8", standalone=True)
    B.files["word/_rels/document.xml.rels"] = etree.tostring(B.rels, xml_declaration=True, encoding="UTF-8", standalone=True)
    ct = B.files["[Content_Types].xml"].decode("utf8")
    if 'Extension="png"' not in ct and B.media:
        ct = ct.replace('<Default Extension="xml"', '<Default Extension="png" ContentType="image/png"/><Default Extension="xml"')
    B.files["[Content_Types].xml"] = ct.encode("utf8")
    B.files.update(B.media)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        # [Content_Types].xml first, as Word expects
        z.writestr("[Content_Types].xml", B.files.pop("[Content_Types].xml"))
        for n, data in B.files.items():
            z.writestr(n, data)
    return out_path


def escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
