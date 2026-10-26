"""Clustered uncertainty and a fixed primary family for the revised P2 study."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent))
from analyze import FEATURES, LAMBDAS, HEADLINE, assemble, auc, policy_eval, tune_theta
from stats_utils import holm, mean_ci, sign_flip_p

ROOT=Path(__file__).resolve().parents[1]


def auc_ci(frame, feature, n_boot=500):
    # Every base contributes the same number of disruptions and repetitions.
    clusters=frame.family+'_'+frame.base.astype(str)
    keys=sorted(clusters.unique())
    scores=np.stack([frame.loc[clusters==key,feature].values for key in keys])
    labels=np.stack([1-frame.loc[clusters==key,'feasA'].values for key in keys])
    rng=np.random.default_rng(420)
    values=[]
    for _ in range(n_boot):
        selected=rng.integers(0,len(keys),len(keys))
        value=auc(scores[selected].ravel(),labels[selected].ravel())
        if np.isfinite(value):values.append(value)
    lo,hi=np.quantile(values,[.025,.975])
    return auc(frame[feature].values,1-frame.feasA.values),float(lo),float(hi)


def primary_family(raw):
    base=raw[(raw['mode']=='eps')&(raw.eps==.02)]
    dev=assemble(base[base['split']=='dev'])
    test=assemble(base[base['split']=='test'])
    lam=LAMBDAS[HEADLINE]
    rows=[]
    cl=test.family+'_'+test.base.astype(str)
    for feature in FEATURES:
        threshold=tune_theta(dev,feature,lam)
        invocation=(test[feature]>=threshold).values
        policy=policy_eval(test,invocation,feature)
        rate=invocation.mean()
        u=policy.feas-lam*policy.tok
        expected_feas=(1-rate)*test.feasA+rate*test.feasT
        expected_tok=(1-rate)*test.tok_single+rate*test.tok_team
        comparators={'random_matched':(expected_feas-lam*expected_tok).values}
        if feature=='load':
            comparators['always_single']=(test.feasA-lam*test.tok_single).values
            comparators['always_team']=(test.feasT-lam*test.tok_team).values
        for comparator,other in comparators.items():
            difference=pd.Series(u.values-other).groupby(cl.values).mean().values
            effect,lo,hi=mean_ci(difference,n_boot=2000,seed=731)
            rows.append(dict(feature=feature,comparator=comparator,threshold=threshold,
                             invocation_rate=rate,diff=effect,lo=lo,hi=hi,
                             p=sign_flip_p(difference,np.zeros_like(difference),n_perm=5000,seed=731),
                             clusters=len(difference)))
    result=pd.DataFrame(rows)
    result['p_holm']=holm(result.p.values)
    return result


def main():
    raw=pd.read_csv(ROOT/'results/raw_episodes.csv')
    primary_family(raw).to_csv(ROOT/'results/primary_paired.csv',index=False)
    rows=[]
    for (mode,eps),frame in raw[raw['split']=='test'].groupby(['mode','eps']):
        for feature in FEATURES:
            effect,lo,hi=auc_ci(frame,feature)
            rows.append(dict(mode=mode,eps=eps,feature=feature,auc=effect,lo=lo,hi=hi))
    pd.DataFrame(rows).to_csv(ROOT/'results/auc_cluster_intervals.csv',index=False)
    print('Primary seven-contrast family and cluster-bootstrap AUC intervals saved')


if __name__=='__main__':main()
