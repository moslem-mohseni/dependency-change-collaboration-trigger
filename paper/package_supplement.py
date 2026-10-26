"""Create a self-contained supplementary archive with deterministic metadata."""
from pathlib import Path
import hashlib
import json
import zipfile

def main():
    root=Path(__file__).resolve().parent.parent
    # Docker uses /work and an extracted archive may be renamed. The generated
    # manuscript identity, rather than the enclosing folder, names the archive.
    manuscripts=sorted((root/'paper').glob('P[1-5]_*.docx'))
    if len(manuscripts)!=1:
        raise ValueError('Expected one generated manuscript to determine paper ID')
    paper_id=manuscripts[0].name.split('_')[0].lower()
    out=root/'paper'/('supplementary_'+paper_id+'.zip')
    files=[]
    for folder in ('src','tests','results','figures','literature','paper','docs','scripts','.github'):
        for path in (root/folder).rglob('*'):
            if path.is_file() and not any(part in ('__pycache__','.pytest_cache','rendered','qa','source_cache','cache') for part in path.parts) and path.suffix not in ('.zip','.pyc','.pdf','.docx'):
                if path.name not in ('run_log.txt','number_audit.json'):
                    files.append(path)
    files.append(root/'paper'/'DarnerView templete.docx')
    for name in ('requirements.txt','Dockerfile','run_all.sh','run_all.ps1','README.md','.dockerignore'):
        if (root/name).exists():files.append(root/name)
    manifest={str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for rel in manifest:
            info=zipfile.ZipInfo(rel,date_time=(2026,10,26,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,(root/rel).read_bytes())
        z.writestr('MANIFEST_SHA256.json',json.dumps(manifest,indent=2))
    print(out, len(manifest),'files')

if __name__=='__main__':main()
