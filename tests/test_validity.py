import random
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from agents import diff_score
from jobs import gen_instance, violations, solve


@pytest.mark.parametrize('bad', [[-1]*12,[0]*11,[False]*12,[0.2]*12])
def test_validator_rejects_out_of_domain_schedules(bad):
    assert violations(gen_instance(random.Random(3),'wide'),bad)[0][0]=='domain'


def test_new_features_use_only_predecision_structure():
    inst=gen_instance(random.Random(3),'wide')
    feature=diff_score(inst,{'seeds':[2],'changed':1})
    assert 0<=feature['critical_overlap']<=1
    assert feature['resource_pressure']>=0
    assert feature==diff_score(inst,{'seeds':[2],'changed':1})


def test_unproved_reference_is_not_called_optimal():
    inst=gen_instance(random.Random(7),'wide')
    with pytest.raises(RuntimeError,match='not proved'):
        solve(inst,time_limit=0.0,require_optimal=True)


def test_bounded_reference_has_explicit_certificate():
    inst=gen_instance(random.Random(0),'wide')
    objective,schedule,info=solve(inst,return_info=True)
    assert not violations(inst,schedule)
    assert info['reference_lower_bound']<=objective
    assert info['reference_status'] in ('OPTIMAL','FEASIBLE','UNKNOWN_SERIAL_FALLBACK')
