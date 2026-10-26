"""Noisy repair agent, verifier agent, controllers, and the episode runner for Paper 2.

The repair agent performs *explicit constraint checks*. Each check is skipped
("overlooked") with probability eps -- the only stochastic element of the agent.
Hence the chance of an infeasible repair grows with the number of checks, which in turn
grows with the size of the affected region. A second agent audits the first one's output;
each audit check also fails with probability eps. All token costs are counted from
the number of checks performed (see TOKENS).
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from jobs import R, Inst, makespan, solve, violations

TOKENS = dict(agent_base=300, audit_base=200, per_check=25, validator=150)


@dataclass
class Outcome:
    start: list
    checks: int
    tokens: int
    latency: int
    invoked_second: bool


def _usage_ok(inst, start, placed, v, s, r):
    for t in range(s, s + inst.dur[v]):
        use = inst.dem[v][r]
        for u in placed:
            if u != v and start[u] <= t < start[u] + inst.dur[u]:
                use += inst.dem[u][r]
        if use > inst.cap[r]:
            return False
    return True


class Slipper:
    """Decides whether a check is overlooked and counts checks.

    mode 'eps'  : every check is skipped independently with probability eps (load-dependent risk).
    mode 'flat' : with probability flat_slip exactly one check of the repair, chosen uniformly,
                  is skipped (size-independent risk; used as a negative control)."""

    def __init__(self, eps, rng, flat_slip=None, total_est=0):
        self.eps, self.rng, self.n = eps, rng, 0
        self.target = None
        if flat_slip is not None and rng.random() < flat_slip and total_est > 0:
            self.target = rng.randrange(total_est)
        self.flat = flat_slip is not None

    def check(self):
        i = self.n
        self.n += 1
        if self.flat:
            return self.target is not None and i == self.target
        return self.rng.random() < self.eps


def _place(inst, start, region, slip):
    start = list(start)
    reg = set(region)
    order = [v for v in inst.topo() if v in reg]
    placed = set(range(inst.n)) - reg
    horizon = sum(inst.dur) + 5
    for v in order:
        s = 0
        for p in sorted(inst.preds[v]):
            if slip.check():
                continue
            s = max(s, start[p] + inst.dur[p])
        while s <= horizon:
            ok = True
            for r in range(R):
                if inst.dem[v][r] == 0:
                    continue
                if slip.check():
                    continue
                if not _usage_ok(inst, start, placed, v, s, r):
                    ok = False
                    break
            if ok:
                for pair in sorted(inst.excl, key=lambda x: tuple(sorted(x))):
                    if v in pair:
                        (q,) = tuple(pair - {v})
                        if q in placed:
                            if slip.check():
                                continue
                            if start[q] < s + inst.dur[v] and s < start[q] + inst.dur[q]:
                                ok = False
                                break
            if ok:
                break
            s += 1
        start[v] = s
        placed.add(v)
    return start


def place_tasks(inst, start, region, eps, rng, flat_slip=None, gamma=0.0):
    """Re-place `region` tasks (topological order) into `start`. Returns (start, checks)."""
    total_est = 0
    if flat_slip is not None:
        dry = Slipper(0.0, random.Random(0))
        _place(inst, start, region, dry)
        total_est = dry.n
    slip = Slipper(eps * (1 + gamma * len(region)), rng, flat_slip, total_est)
    out = _place(inst, start, region, slip)
    return out, slip.n


def audit_flags(inst: Inst, start: list, region: list, eps: float, rng: random.Random, gamma: float = 0.0):
    """Verifier re-checks every constraint of each region task. Returns (flagged tasks, checks)."""
    flagged, checks = set(), 0
    reg = set(region)
    eps = eps * (1 + gamma * len(region))
    for v in region:
        bad = False
        for p in sorted(inst.preds[v]):
            checks += 1
            if start[v] < start[p] + inst.dur[p]:
                if rng.random() >= eps:
                    bad = True
        for pair in sorted(inst.excl, key=lambda x: tuple(sorted(x))):
            if v in pair:
                (q,) = tuple(pair - {v})
                checks += 1
                if start[q] < start[v] + inst.dur[v] and start[v] < start[q] + inst.dur[q]:
                    if rng.random() >= eps:
                        bad = True
        for r in range(R):
            if inst.dem[v][r] == 0:
                continue
            checks += 1
            ok = True
            for t in range(start[v], start[v] + inst.dur[v]):
                use = sum(inst.dem[u][r] for u in range(inst.n) if start[u] <= t < start[u] + inst.dur[u])
                if use > inst.cap[r]:
                    ok = False
                    break
            if not ok and rng.random() >= eps:
                bad = True
        if bad:
            flagged.add(v)
    return flagged, checks


def run_single(inst1, start0, region, eps, rng, flat_slip=None, gamma=0.0):
    st, checks = place_tasks(inst1, start0, region, eps, rng, flat_slip, gamma)
    tokens = TOKENS["agent_base"] + TOKENS["per_check"] * checks
    return st, checks, tokens


def run_audit(inst1, start, region, eps, rng, flat_slip=None, rounds=2, gamma=0.0):
    """Second agent audits; flagged tasks (and region descendants) are re-placed by the first agent."""
    checks_total, tokens, latency = 0, 0, 0
    reg = set(region)
    for _ in range(rounds):
        flagged, c = audit_flags(inst1, start, region, eps, rng, gamma)
        checks_total += c
        tokens += TOKENS["audit_base"] + TOKENS["per_check"] * c
        latency += 1
        if not flagged:
            break
        fix = sorted(flagged | (inst1.descendants(list(flagged)) & reg))
        start, c2 = place_tasks(inst1, start, fix, eps, rng, flat_slip, gamma * len(region) / max(len(fix), 1))
        checks_total += c2
        tokens += TOKENS["per_check"] * c2 + 100
        latency += 1
    return start, checks_total, tokens, latency


def diff_score(inst1: Inst, meta: dict) -> dict:
    """Features available to the controller from the constraint diff alone (no schedule needed)."""
    desc = inst1.descendants(meta["seeds"])
    region = set(meta["seeds"]) | desc
    load = 0
    for v in region:
        load += len(inst1.preds[v]) + sum(1 for pr in inst1.excl if v in pr)
        load += sum(1 for r in range(R) if inst1.dem[v][r] > 0)
    # Exploratory reviewer-motivated features, fixed before the new run.
    # Slack ignores resource/exclusion constraints and is therefore a proxy,
    # not an exact critical path of the resource-constrained problem.
    earliest = [0] * inst1.n
    order = inst1.topo()
    for v in order:
        earliest[v] = max((earliest[u] + inst1.dur[u] for u in inst1.preds[v]), default=0)
    finish = max(earliest[v] + inst1.dur[v] for v in order)
    latest = [finish - inst1.dur[v] for v in range(inst1.n)]
    succ = inst1.succs()
    for v in reversed(order):
        if succ[v]:
            latest[v] = min(latest[u] - inst1.dur[v] for u in succ[v])
    critical = {v for v in range(inst1.n) if latest[v] == earliest[v]}
    overlap = len(region & critical) / max(1, len(critical))
    pressure = sum(inst1.dur[v] * sum(inst1.dem[v][r] / inst1.cap[r] for r in range(R)) for v in region)
    return dict(changed=meta["changed"], region_proxy=len(region), load=load,
                critical_overlap=overlap, resource_pressure=pressure)
