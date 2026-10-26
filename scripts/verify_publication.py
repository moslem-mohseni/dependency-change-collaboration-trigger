"""Verify published source/data hashes, archive boundaries and mock-only provenance."""
from pathlib import Path
import hashlib,json,re

ROOT=Path(__file__).resolve().parents[1]

def digest(path,mode):
    data=path.read_bytes()
    if mode=='lf':data=data.replace(b'\r\n',b'\n')
    return hashlib.sha256(data).hexdigest()

def main():
    for filename in ('SOURCE_MANIFEST.json','RESULTS_MANIFEST.json'):
        manifest=json.loads((ROOT/filename).read_text(encoding='utf8'))
        for rel,record in manifest['files'].items():
            path=ROOT/rel
            assert path.is_file(),rel
            assert digest(path,record['mode'])==record['sha256'],f'Published baseline changed: {rel}'
    status=json.loads((ROOT/'results/llm/status.json').read_text())
    assert status.get('real_llm_run') is False
    transcripts=list((ROOT/'results/llm/mock_transcripts').glob('*.json'))
    assert transcripts,'Expected labelled mock transcripts'
    for path in transcripts:
        record=json.loads(path.read_text())
        assert record.get('backend')=='mock' and record.get('mock') is True,path.name
    for folder in ('src','tests','scripts','docs','paper','.github'):
        for path in (ROOT/folder).rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts:continue
            assert path.stat().st_size<100*1024*1024,path.name
            if path.suffix in ('.py','.md','.json','.yml','.yaml','.sh','.ps1','.txt'):
                text=path.read_text(encoding='utf-8-sig')
                for pattern in (r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'gh[pousr]_[A-Za-z0-9]{30,}',r'github_pat_[A-Za-z0-9_]{40,}',r'sk-(?:proj-|ant-)?[A-Za-z0-9_-]{45,}'):
                    assert not re.search(pattern,text),f'Potential credential in {path.relative_to(ROOT)}'
    print(f'Publication source/data hashes and {len(transcripts)} mock transcripts verified')

if __name__=='__main__':main()
