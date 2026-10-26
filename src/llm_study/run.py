"""Separate LLM scheduling repair and audit, scored by the exact validator."""
from pathlib import Path
import argparse
import json
import sys
import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from run_experiments import build_episodes
from agents import diff_score
from jobs import violations,makespan
from client import LLMClient,discover


def public_task(ep):
    inst=ep['inst']
    return dict(durations=inst.dur,predecessors=[sorted(x) for x in inst.preds],
                exclusions=[sorted(x) for x in sorted(inst.excl,key=lambda x:tuple(sorted(x)))],
                resource_demands=inst.dem,capacities=inst.cap,old_schedule=ep['st0'])


def parse_schedule(text,inst):
    schedule=json.loads(text)['start']
    if not isinstance(schedule,list) or len(schedule)!=inst.n:
        raise ValueError('expected one start per task')
    # The validator, rather than a language model, checks all domain constraints.
    return schedule


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--backend',default='mock')
    parser.add_argument('--model',default='mock')
    args=parser.parse_args()
    out=HERE.parents[1]/'results/llm';out.mkdir(parents=True,exist_ok=True)
    client=LLMClient(args.backend,args.model,out/'cache',max_tokens=256)
    # 102 independent pre/post-disruption episodes in each split. Development
    # labels are separate from the held-out stream and used only for thresholds.
    rows=[]
    for split,seed0 in [('dev',30000),('test',40000)]:
        for ep in build_episodes(split,17,seed0):
            task=public_task(ep)
            messages=[{'role':'user','content':'Repair this synthetic schedule. Return only JSON {"start":[nonnegative integer start time for each task]}. '+json.dumps(task,sort_keys=True)}]
            answer=client.complete(messages,ep['seed'],temperature=0)
            prompt_hash=client.last['prompt_sha256']
            try:
                first=parse_schedule(answer,ep['inst'])
                valid=not violations(ep['inst'],first)
            except (ValueError,KeyError,TypeError):
                first=None;valid=False
            audit_messages=[{'role':'user','content':'Audit and repair the candidate schedule under all constraints. Return only JSON with start, one nonnegative integer for each task. '+json.dumps(dict(task=task,candidate=first),sort_keys=True)}]
            audited=client.complete(audit_messages,ep['seed'],temperature=0)
            try:
                team=parse_schedule(audited,ep['inst']);team_valid=not violations(ep['inst'],team)
            except (ValueError,KeyError,TypeError):
                team=None;team_valid=False
            features=diff_score(ep['inst'],ep['meta'])
            rows.append(dict(split=split,seed=ep['seed'],family=ep['family'],kind=ep['kind'],**features,
                             feasA=int(valid),feasT=int(team_valid),gapA=(makespan(ep['inst'],first)-ep['mk_opt'])/ep['mk_opt'] if valid else None,
                             gapT=(makespan(ep['inst'],team)-ep['mk_opt'])/ep['mk_opt'] if team_valid else None,
                             first_calls=1,audit_calls=1,prompt_sha256=prompt_hash,mock=args.backend=='mock'))
    frame=pd.DataFrame(rows)
    frame.to_csv(out/('dry_run.csv' if args.backend=='mock' else 'episodes.csv'),index=False)
    status=dict(real_llm_run=args.backend!='mock',backend=args.backend,model=args.model,temperature=0,
                episodes_per_split=len(frame)//2,availability=discover(),
                local_runtime_attempt=json.loads((HERE/'availability_attempt.json').read_text()))
    (out/'status.json').write_text(json.dumps(status,indent=2))
    if args.backend!='mock':
        from analyze import auc
        from stats_utils import holm,mean_ci,sign_flip_p
        dev=frame[frame.split=='dev'];test=frame[frame.split=='test']
        records=[]
        for feature in ('load','region_proxy','changed','critical_overlap','resource_pressure'):
            # Calls are priced explicitly here, separately from synthetic tokens.
            threshold=max(sorted(set(dev[feature]))+[float(dev[feature].max())+1],
                key=lambda q: float((dev.feasA.where(dev[feature]<q,dev.feasT)-.02*(1+(dev[feature]>=q))).mean()))
            invoke=test[feature]>=threshold
            score=test.feasA.where(~invoke,test.feasT)
            mean,lo,hi=mean_ci(score)
            records.append(dict(feature=feature,auc=auc(test[feature].values,1-test.feasA.values),
                                threshold=threshold,success=mean,lo=lo,hi=hi,mean_calls=1+invoke.mean()))
        pd.DataFrame(records).to_csv(out/'summary.csv',index=False)
    print(json.dumps(status,indent=2))


if __name__=='__main__':main()
