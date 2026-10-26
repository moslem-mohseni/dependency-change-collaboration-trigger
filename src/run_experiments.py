"""Generate per-episode raw outcomes for Paper 2 (policies are assembled in analyze.py)."""
from __future__ import annotations

import argparse
import os
import random
import sys
import zlib

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from agents import TOKENS, diff_score, run_audit, run_single
from jobs import (dependency_disruption, gen_instance, local_disruption, makespan, solve,
                  violations)

RES = os.path.join(os.path.dirname(__file__), "..", "results")
SETTINGS = [("eps", 0.005), ("eps", 0.01), ("eps", 0.02), ("eps", 0.04), ("flat", 0.30), ("loaded", 0.005)]


def build_episodes(split: str, n_bases: int, seed0: int):
    eps_list = []
    for fam in ("pipeline", "wide"):
        for b in range(n_bases):
            seed = seed0 + b + (0 if fam == "pipeline" else 100000)
            rng = random.Random(seed)
            inst = gen_instance(rng, fam)
            mk0, st0 = solve(inst)
            for kind in ("local", "dependency", "cascade"):
                r2 = random.Random(seed * 31 + {"local": 1, "dependency": 2, "cascade": 3}[kind])
                if kind == "local":
                    new, meta = local_disruption(inst, r2)
                elif kind == "dependency":
                    new, meta = dependency_disruption(inst, st0, r2)
                else:  # added after the pilot showed small effects: larger dependency changes
                    new, meta = dependency_disruption(inst, st0, r2, ks=(5, 6, 7))
                mk1, st1, reference_info = solve(new, return_info=True)
                region = sorted(set(meta["seeds"]) | new.descendants(meta["seeds"]))
                eps_list.append(dict(split=split, family=fam, base=b, kind=kind, seed=seed,
                                     inst=new, st0=st0, mk_opt=mk1, region=region, meta=meta,
                                     reference_info=reference_info))
    return eps_list


def run_setting(ep, mode, val, reps):
    rows = []
    sc = diff_score(ep["inst"], ep["meta"])
    for rep in range(reps):
        rngA = random.Random(zlib.crc32(repr((ep["seed"], ep["kind"], rep, "A", mode, val)).encode()))
        rngB = random.Random(zlib.crc32(repr((ep["seed"], ep["kind"], rep, "B", mode, val)).encode()))
        eps = val if mode in ("eps", "loaded") else 0.0
        flat = val if mode == "flat" else None
        gamma = 0.5 if mode == "loaded" else 0.0  # error rate grows with the size of the affected region
        stA, checksA, tokA = run_single(ep["inst"], ep["st0"], ep["region"], eps, rngA, flat, gamma)
        vA = violations(ep["inst"], stA)
        stT, checksB, tokB, latB = run_audit(ep["inst"], stA, ep["region"], eps, rngB, flat, gamma=gamma)
        vT = violations(ep["inst"], stT)
        mkA, mkT = makespan(ep["inst"], stA), makespan(ep["inst"], stT)
        rows.append(dict(
            split=ep["split"], family=ep["family"], base=ep["base"], kind=ep["kind"], rep=rep,
            **ep["reference_info"],
            mode=mode, eps=val, changed=sc["changed"], region_proxy=sc["region_proxy"], load=sc["load"],
            critical_overlap=sc["critical_overlap"], resource_pressure=sc["resource_pressure"],
            true_region=len(ep["region"]), feasA=int(not vA), feasT=int(not vT),
            gapA=(mkA - ep["mk_opt"]) / ep["mk_opt"] if not vA else float("nan"),
            gapT=(mkT - ep["mk_opt"]) / ep["mk_opt"] if not vT else float("nan"),
            tokA=tokA, tokB=tokB, latB=latB, checksA=checksA, checksB=checksB))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", type=int, default=100)
    ap.add_argument("--test", type=int, default=200)
    ap.add_argument("--reps", type=int, default=5)
    a = ap.parse_args()
    os.makedirs(RES, exist_ok=True)
    eps_dev = build_episodes("dev", a.dev, 0)
    eps_test = build_episodes("test", a.test, 1000)
    rows = []
    for index, ep in enumerate(eps_dev + eps_test):
        if index % 100 == 0:
            print(f"Completed {index} disrupted instances", flush=True)
        for mode, val in SETTINGS:
            rows.extend(run_setting(ep, mode, val, a.reps))
    pd.DataFrame(rows).to_csv(os.path.join(RES, "raw_episodes.csv"), index=False)
    print("episodes", len(eps_dev + eps_test), "rows", len(rows))


if __name__ == "__main__":
    main()
