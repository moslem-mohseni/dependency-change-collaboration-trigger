"""Primary-family and clustered AUC invariants on transparent outcomes."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from primary_statistics import primary_family,auc_ci
from analyze import FEATURES


def test_primary_family_preserves_all_seven_contrasts_and_pairing():
    rows=[]
    for split in ('dev','test'):
        for base in range(4):
            for rep in range(2):
                rows.append(dict(split=split,base=base,rep=rep,family='wide',mode='eps',eps=.02,
                    feasA=0,feasT=1,tokA=10,tokB=10,latB=1,
                    **{feature:1.0 for feature in FEATURES}))
    result=primary_family(pd.DataFrame(rows))
    assert len(result)==7
    assert set(result.feature)==set(FEATURES)
    matched=result[result.comparator=='random_matched']
    np.testing.assert_array_equal(matched['diff'],np.zeros(5))
    np.testing.assert_array_equal(matched.p_holm,np.ones(5))
    assert set(result.clusters)=={4}
    assert result[(result.feature=='load')&(result.comparator=='always_single')]['diff'].iloc[0]>.99


def test_auc_cluster_bootstrap_keeps_perfect_ranking():
    frame=pd.DataFrame(dict(family=['wide']*8,base=np.repeat(range(4),2),
                            signal=[0,1]*4,feasA=[1,0]*4))
    assert auc_ci(frame,'signal',n_boot=20)==(1.0,1.0,1.0)
