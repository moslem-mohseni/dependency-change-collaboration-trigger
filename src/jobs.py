"""Scheduling instances, bounded reference solver (CP-SAT) and validator for Paper 2."""
from __future__ import annotations

import copy
import math
import numbers
import random
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

R = 2  # renewable resource types


@dataclass
class Inst:
    n: int
    dur: list
    preds: list            # list[set[int]]
    excl: set              # set[frozenset({a,b})] pairs that may not overlap
    dem: list              # n x R demands
    cap: list              # R capacities

    def copy(self):
        return copy.deepcopy(self)

    def succs(self):
        s = [set() for _ in range(self.n)]
        for v in range(self.n):
            for p in self.preds[v]:
                s[p].add(v)
        return s

    def descendants(self, seeds):
        s = self.succs()
        out, stack = set(), list(seeds)
        while stack:
            u = stack.pop()
            for w in s[u]:
                if w not in out:
                    out.add(w)
                    stack.append(w)
        return out

    def topo(self):
        indeg = [len(p) for p in self.preds]
        s = self.succs()
        order, q = [], [i for i in range(self.n) if indeg[i] == 0]
        while q:
            q.sort()
            u = q.pop(0)
            order.append(u)
            for w in sorted(s[u]):
                indeg[w] -= 1
                if indeg[w] == 0:
                    q.append(w)
        return order


def gen_instance(rng: random.Random, family: str, n: int = 12) -> Inst:
    dur = [rng.randint(1, 5) for _ in range(n)]
    preds = [set() for _ in range(n)]
    if family == "pipeline":      # deep layered DAG, light resources
        layers = 4
        per = n // layers
        lay = [min(i // per, layers - 1) for i in range(n)]
        for v in range(n):
            if lay[v] > 0:
                cands = [u for u in range(n) if lay[u] == lay[v] - 1]
                for u in rng.sample(cands, k=min(len(cands), rng.choice([1, 2]))):
                    preds[v].add(u)
        dem = [[rng.choice([0, 0, 1, 1, 2]) for _ in range(R)] for _ in range(n)]
        cap = [3, 3]
    else:                         # "wide": shallow DAG, tight resource contention
        for v in range(3, n):
            for u in rng.sample(range(0, v), k=rng.choice([0, 1])):
                preds[v].add(u)
        dem = [[rng.choice([0, 1, 1, 2, 2]) for _ in range(R)] for _ in range(n)]
        cap = [3, 2]
    return Inst(n=n, dur=dur, preds=preds, excl=set(), dem=dem, cap=cap)


def solve(inst: Inst, time_limit: float = 3600.0, return_info=False, require_optimal=False):
    m = cp_model.CpModel()
    H = sum(inst.dur)
    s = [m.NewIntVar(0, H, f"s{i}") for i in range(inst.n)]
    iv = [m.NewIntervalVar(s[i], inst.dur[i], s[i] + inst.dur[i], f"i{i}") for i in range(inst.n)]
    for v in range(inst.n):
        for p in sorted(inst.preds[v]):
            m.Add(s[v] >= s[p] + inst.dur[p])
    for pair in sorted(inst.excl, key=lambda x: tuple(sorted(x))):
        a, b = tuple(sorted(pair))
        m.AddNoOverlap([iv[a], iv[b]])
    for r in range(R):
        m.AddCumulative(iv, [inst.dem[i][r] for i in range(inst.n)], inst.cap[r])
    mk = m.NewIntVar(0, H, "mk")
    m.AddMaxEquality(mk, [s[i] + inst.dur[i] for i in range(inst.n)])
    # A serial topological schedule is always feasible. A hint supplies a
    # deterministic incumbent, and elementary energy/path bounds strengthen
    # propagation without exposing a reference answer to either repair agent.
    tick = 0
    for v in inst.topo():
        m.AddHint(s[v], tick)
        tick += inst.dur[v]
    for r in range(R):
        m.Add(mk >= math.ceil(sum(inst.dur[i] * inst.dem[i][r] for i in range(inst.n)) / inst.cap[r]))
    earliest = [0] * inst.n
    for v in inst.topo():
        earliest[v] = max((earliest[u] + inst.dur[u] for u in inst.preds[v]), default=0)
    m.Add(mk >= max(earliest[v] + inst.dur[v] for v in range(inst.n)))
    m.Minimize(mk)
    sol = cp_model.CpSolver()
    sol.parameters.max_time_in_seconds = time_limit
    sol.parameters.max_deterministic_time = 0.1
    sol.parameters.num_workers = 1
    sol.parameters.random_seed = 1
    st = sol.Solve(m)
    if require_optimal and st != cp_model.OPTIMAL:
        raise RuntimeError(f"Reference optimum not proved: {sol.StatusName(st)}")
    status = sol.StatusName(st)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        objective = int(sol.ObjectiveValue())
        starts = [int(sol.Value(x)) for x in s]
    else:
        # Never drop a hard seed: retain a valid serial upper bound and mark
        # the lack of a CP-SAT incumbent explicitly in the result ledger.
        starts = [0] * inst.n
        tick = 0
        for v in inst.topo():
            starts[v] = tick
            tick += inst.dur[v]
        objective = tick
        status += "_SERIAL_FALLBACK"
    info = dict(reference_status=status, reference_optimal=int(st == cp_model.OPTIMAL),
                reference_lower_bound=float(sol.BestObjectiveBound()),
                reference_makespan=objective)
    return (objective, starts, info) if return_info else (objective, starts)


def violations(inst: Inst, start: list):
    """All violated constraints of a start-time vector (ground-truth validator)."""
    if len(start) != inst.n or any(not isinstance(v, numbers.Integral) or isinstance(v, bool) or v < 0 for v in start):
        return [("domain", "expected nonnegative integer start time for every task")]
    out = []
    for v in range(inst.n):
        for p in inst.preds[v]:
            if start[v] < start[p] + inst.dur[p]:
                out.append(("prec", p, v))
    for pair in inst.excl:
        a, b = tuple(sorted(pair))
        if start[a] < start[b] + inst.dur[b] and start[b] < start[a] + inst.dur[a]:
            out.append(("excl", a, b))
    H = max(start[i] + inst.dur[i] for i in range(inst.n))
    for r in range(R):
        for t in range(H):
            use = sum(inst.dem[i][r] for i in range(inst.n) if start[i] <= t < start[i] + inst.dur[i])
            if use > inst.cap[r]:
                out.append(("cap", r, t))
    return out


def makespan(inst: Inst, start: list) -> int:
    return max(start[i] + inst.dur[i] for i in range(inst.n))


# ---- disruptions -------------------------------------------------------------------

def local_disruption(inst: Inst, rng: random.Random):
    """Duration increase of a task that has at most two transitive successors."""
    cands = [i for i in range(inst.n) if len(inst.descendants([i])) <= 2]
    i = rng.choice(cands or list(range(inst.n)))
    new = inst.copy()
    new.dur[i] += rng.randint(1, 2)
    return new, dict(kind="local", seeds=[i], changed=1)


def dependency_disruption(inst: Inst, start: list, rng: random.Random, ks=(2, 3, 4)):
    """Several new precedence edges and/or exclusion pairs among tasks (dependency change)."""
    new = inst.copy()
    k = rng.choice(list(ks))
    seeds, changed = [], 0
    attempts = 0
    while changed < k and attempts < 200:
        attempts += 1
        u, v = rng.sample(range(inst.n), 2)
        if rng.random() < 0.6:
            # new precedence u -> v must keep the graph acyclic
            if u in new.descendants([v]) or v in new.preds[u] or u in new.preds[v]:
                continue
            new.preds[v].add(u)
            seeds.append(v)
        else:
            if frozenset((u, v)) in new.excl:
                continue
            new.excl.add(frozenset((u, v)))
            seeds.append(max(u, v, key=lambda x: start[x]))
        changed += 1
    return new, dict(kind="dependency" if max(ks) <= 4 else "cascade", seeds=sorted(set(seeds)), changed=changed)

