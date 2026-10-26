"""Run the complete paper pipeline and compare every CSV with the checked-in baseline."""
from pathlib import Path
import datetime,json,os,shutil,subprocess,sys,tempfile,time
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]

def main():
    out=ROOT/'artifacts';out.mkdir(exist_ok=True)
    environment=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    environment.setdefault('BUILD_DATE',datetime.datetime.now().strftime('%d.%m.%Y'))
    started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='research-csv-baseline-') as tmp:
        baseline=Path(tmp)
        names=sorted(str(p.relative_to(ROOT/'results')).replace('\\','/') for p in (ROOT/'results').rglob('*.csv'))
        if not names:raise RuntimeError('No published CSV baseline exists')
        for name in names:
            target=baseline/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/'results'/name,target)
        if os.name=='nt':
            command=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'run_all.ps1'),'-Python',sys.executable,'-SkipPdf']
        else:command=['bash','run_all.sh']
        with (out/'run.log').open('w',encoding='utf8') as log:
            process=subprocess.run(command,cwd=ROOT,env=environment,stdout=log,stderr=subprocess.STDOUT)
        if process.returncode:
            print((out/'run.log').read_text(encoding='utf8')[-14000:])
            raise RuntimeError(f'Pipeline failed with exit {process.returncode}; see artifacts/run.log')
        current=sorted(str(p.relative_to(ROOT/'results')).replace('\\','/') for p in (ROOT/'results').rglob('*.csv'))
        if current!=names:raise AssertionError('Generated CSV file set differs from published baseline')
        checked=[]
        for name in names:
            expected=pd.read_csv(baseline/name);actual=pd.read_csv(ROOT/'results'/name)
            pd.testing.assert_frame_equal(expected,actual,check_exact=True)
            checked.append(dict(file=name,rows=len(actual),columns=len(actual.columns),equal=True,mock=name.startswith('llm/')))
    report=dict(status='passed',comparison='Exact parsed pandas values; line endings ignored',files=checked,elapsed_seconds=round(time.monotonic()-started,2),python=sys.version,build_date=environment['BUILD_DATE'],real_model_calls=False)
    (out/'reproducibility.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(f'PASS: {len(checked)} CSV files reproduced exactly. Mock data are separate from scientific outcomes.')

if __name__=='__main__':main()
