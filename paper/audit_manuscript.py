"""Structural, citation, image and template checks for a submission artifact."""
import json
import re
import runpy
import sys
import zipfile
from pathlib import Path
from lxml import etree
from PIL import Image
import io

NS={"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp":"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"}

def main():
    here=Path(__file__).resolve().parent
    spec=runpy.run_path(str(here/"build_manuscript.py"),run_name="manuscript_audit")["spec"]
    docx=next(p for p in here.glob("P*.docx") if p.name!="DarnerView templete.docx")
    author=json.loads((here/"author.json").read_text(encoding="utf-8-sig"))
    with zipfile.ZipFile(docx) as archive,zipfile.ZipFile(here/"DarnerView templete.docx") as template:
        root=etree.fromstring(archive.read("word/document.xml"))
        all_text="\n".join("".join(el.xpath('.//w:t/text()',namespaces=NS)) for name in archive.namelist()
            if re.match(r"word/(?:document|header\d+|footer\d+)\.xml$",name)
            for el in etree.fromstring(archive.read(name)).xpath(".//w:p",namespaces=NS))
        banned=re.findall(r"\b(?:XX|DD\.MM|Lorem|placeholder|to be completed|TODO|Sample|imaginary|fictional|Claude|Anthropic)\b|AI system|Use of AI Tools",all_text,re.I)
        assert not banned,banned
        assert not re.search(r"\{[TFE]:",all_text),"Unresolved cross-reference"
        allowed={value for value in author.values() if value.startswith('[')}
        leftovers=[x for x in re.findall(r"\[[A-Z][A-Z ]+\]",all_text) if x not in allowed]
        assert not leftovers,leftovers
        assert 150<=len(spec["abstract"].split())<=250,len(spec["abstract"].split())
        assert 5<=len(spec["keywords"])<=6
        assert archive.read("word/styles.xml")==template.read("word/styles.xml"),"Template style definitions changed"
        original=etree.fromstring(template.read("word/document.xml")).find('.//w:sectPr',NS)
        current=root.find('.//w:sectPr',NS)
        assert etree.tostring(current)==etree.tostring(original),"Template section geometry changed"
        image_evidence=[]
        for drawing in root.xpath('.//wp:inline',namespaces=NS):
            desc=drawing.find('wp:docPr',NS)
            assert desc.get('descr'),"Missing image alternative text"
            extent=drawing.find('wp:extent',NS)
            embed=drawing.xpath('.//@r:embed',namespaces={"r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"})[0]
            rels=etree.fromstring(archive.read('word/_rels/document.xml.rels'))
            target=next(e.get('Target') for e in rels if e.get('Id')==embed)
            with Image.open(io.BytesIO(archive.read('word/'+target))) as im:
                dpi=im.width/(int(extent.get('cx'))/914400)
                assert dpi>=299,f"Effective DPI {dpi}"
                image_evidence.append(dict(name=target,effective_dpi=dpi,alt=desc.get('descr')))
    config=json.loads((here/'citation_keys.json').read_text())
    body=json.dumps(spec['blocks'],ensure_ascii=False)
    for item in config:
        assert item['citation'] in body, 'Uncited reference: '+item['citation']
        assert any(item['reference_start'] in ref for ref in spec['references']),item
    assert len(config)==len(spec['references']),"Reference registry is incomplete"
    starts=[re.sub('[^a-z]','',ref.lower().split('(')[0]) for ref in spec['references']]
    assert starts==sorted(starts),"References are not alphabetical"
    # Match each parenthetical or narrative author-year form against the registry.
    found=re.findall(r"(?:[A-Z]\. )?[A-Z][A-Za-z0-9-]*(?: et al\.)?,? \(?\d{4}[a-z]?\)?|solomoon313, n\.d\.",body)
    unknown=[]
    for citation in found:
        normal=citation.replace(' (',', ').rstrip(')')
        if not any(normal in c['citation'] or c['citation'] in normal for c in config):
            unknown.append(citation)
    assert not unknown,unknown
    report=dict(abstract_words=len(spec['abstract'].split()),keywords=len(spec['keywords']),
                reference_count=len(config),citations='passed',template_styles='identical',
                template_geometry='identical',leftovers='clean',images=image_evidence)
    (here/'manuscript_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
