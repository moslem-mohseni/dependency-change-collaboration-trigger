import os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from agents import place_tasks, run_single
from jobs import dependency_disruption, gen_instance, local_disruption, solve, violations


def test_optimal_is_valid_and_disruptions_break_old_schedule_sometimes():
    rng = random.Random(0)
    broke = 0
    for i in range(30):
        inst = gen_instance(rng, "pipeline" if i % 2 else "wide")
        mk, st, info = solve(inst, return_info=True)
        assert violations(inst, st) == []
        new, meta = dependency_disruption(inst, st, rng)
        broke += bool(violations(new, st))
        mk2, st2, info2 = solve(new, return_info=True)
        assert violations(new, st2) == []
        if info['reference_optimal'] and info2['reference_optimal']:
            assert mk2 >= mk
    assert broke > 5


def test_error_free_agent_repairs_nearly_always():
    rng = random.Random(1)
    ok = tot = 0
    for i in range(60):
        inst = gen_instance(rng, "wide" if i % 2 else "pipeline")
        mk, st = solve(inst)
        new, meta = (dependency_disruption(inst, st, rng) if i % 3 else local_disruption(inst, rng))
        region = sorted(set(meta["seeds"]) | new.descendants(meta["seeds"]))
        s2, c, t = run_single(new, st, region, 0.0, rng)
        tot += 1
        ok += not violations(new, s2)
    assert ok / tot > 0.95


def test_more_checks_for_larger_regions():
    rng = random.Random(2)
    inst = gen_instance(rng, "pipeline")
    mk, st = solve(inst)
    _, c_small = place_tasks(inst, st, [5], 0.0, rng)
    _, c_big = place_tasks(inst, st, list(range(3, 12)), 0.0, rng)
    assert c_big > c_small
