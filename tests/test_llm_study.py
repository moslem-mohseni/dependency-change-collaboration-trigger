import random
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).parents[1]/'src/llm_study'))
from run import parse_schedule
from jobs import gen_instance,solve,violations

def test_schedule_parser_and_exact_domain_judge():
    import json
    inst=gen_instance(random.Random(2),'wide')
    _,schedule=solve(inst)
    assert not violations(inst,parse_schedule(json.dumps({'start':schedule}),inst))
    with pytest.raises(ValueError):parse_schedule('{"start":[]}',inst)
    assert violations(inst,parse_schedule('{"start":'+str([-1]*12)+'}',inst))
