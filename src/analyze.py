"""Assemble policies from raw episodes, tune the trigger on dev, evaluate on test, make tables/figures."""
from __future__ import annotations

import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

sys.path.insert(0, os.path.dirname(__file__))
RES = os.path.join(os.path.dirname(__file__), "..", "results")
FIG = os.path.join(os.path.dirname(__file__), "..", "figures")
os.makedirs(FIG, exist_ok=True)
rng = np.random.default_rng(0)

LAMBDAS = {"1/20k": 1 / 20000, "1/10k": 1 / 10000, "1/5k": 1 / 5000, "1/2.5k": 1 / 2500}
HEADLINE = "1/5k"          # declared before looking at test results
C_VAL = 150.0              # tokens for one external validator call (sensitivity below)
FEATURES = ("load", "region_proxy", "changed", "critical_overlap", "resource_pressure")


def assemble(df, c_val=C_VAL):
    d = df.copy()
    d["tok_single"] = d.tokA
    d["tok_team"] = d.tokA + d.tokB
    d["lat_team"] = 1 + d.latB
    fail = 1 - d.feasA
    d["feas_ft"] = np.where(fail == 1, d.feasT, 1)
    d["tok_ft"] = d.tokA + c_val + fail * d.tokB
    d["tok_oracle"] = d.tokA + fail * d.tokB
    return d


def policy_eval(d, invoke, name):
    """invoke: boolean array (call second agent after the first)."""
    feas = np.where(invoke, d.feasT, d.feasA)
    tok = np.where(invoke, d.tok_team, d.tok_single)
    return pd.DataFrame(dict(policy=name, feas=feas, tok=tok, inv=invoke.astype(float),
                             cluster=d.family + "_" + d.base.astype(str)))


def cluster_boot(x, clusters, n=1000):
    """Bootstrap CI of the mean of x, resampling clusters."""
    g = pd.Series(x).groupby(np.asarray(clusters)).agg(["sum", "count"])
    s, c = g["sum"].values, g["count"].values
    k = len(s)
    idx = rng.integers(0, k, size=(n, k))
    means = s[idx].sum(1) / c[idx].sum(1)
    return float(x.mean()), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def cluster_boot_diff(a, b, clusters, n=1000):
    return cluster_boot(np.asarray(a) - np.asarray(b), clusters, n)


def tune_theta(dev, feature, lam):
    best, bu = None, -1e9
    for th in sorted(set(dev[feature])) + [max(dev[feature]) + 1]:
        inv = (dev[feature] >= th).values
        p = policy_eval(dev, inv, "x")
        u = (p.feas - lam * p.tok).mean()
        if u > bu:
            best, bu = th, u
    return best


def auc(score, y):
    pos, neg = score[y == 1], score[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    u = mannwhitneyu(pos, neg, alternative="two-sided").statistic
    return float(u / (len(pos) * len(neg)))


def main():
    raw = pd.read_csv(os.path.join(RES, "raw_episodes.csv"))
    out_rows, auc_rows = [], []
    for (mode, val), g in raw.groupby(["mode", "eps"]):
        dev, test = assemble(g[g["split"] == "dev"]), assemble(g[g["split"] == "test"])
        y = (1 - test.feasA).values
        for f in FEATURES:
            auc_rows.append(dict(mode=mode, eps=val, feature=f, auc=auc(test[f].values.astype(float), y),
                                 fail_rate=y.mean()))
        for ln, lam in LAMBDAS.items():
            cl = test.family + "_" + test.base.astype(str)
            rows = {}
            n = len(test)
            rows["always_single"] = policy_eval(test, np.zeros(n, bool), "always_single")
            rows["always_team"] = policy_eval(test, np.ones(n, bool), "always_team")
            ft = pd.DataFrame(dict(feas=test.feas_ft, tok=test.tok_ft, inv=1 - test.feasA, cluster=cl))
            rows["fail_triggered"] = ft
            orc = pd.DataFrame(dict(feas=test.feas_ft, tok=test.tok_oracle, inv=1 - test.feasA, cluster=cl))
            rows["oracle_pre"] = orc
            for f in FEATURES:
                th = tune_theta(dev, f, lam)
                inv = (test[f] >= th).values
                rows[f"ours_{f}"] = policy_eval(test, inv, f"ours_{f}")
                # random policy with the same expected invocation rate (exact expectation)
                q = inv.mean()
                rnd_feas = (1 - q) * test.feasA + q * test.feasT
                rnd_tok = (1 - q) * test.tok_single + q * test.tok_team
                rows[f"random_matched_{f}"] = pd.DataFrame(dict(feas=rnd_feas, tok=rnd_tok, inv=q, cluster=cl))
            for pn, p in rows.items():
                u = p.feas - lam * p.tok
                m, lo, hi = cluster_boot(u.values, p.cluster.values)
                out_rows.append(dict(mode=mode, eps=val, lam=ln, policy=pn, feas=p.feas.mean(), tok=p.tok.mean(),
                                     inv=p.inv.mean(), U=m, U_lo=lo, U_hi=hi))
            # paired difference ours - random matched on utility, and on feasibility at equal tokens
            for f in FEATURES:
                a, b = rows[f"ours_{f}"], rows[f"random_matched_{f}"]
                ua, ub = a.feas - lam * a.tok, b.feas - lam * b.tok
                m, lo, hi = cluster_boot_diff(ua.values, ub.values, a.cluster.values)
                out_rows.append(dict(mode=mode, eps=val, lam=ln, policy=f"DIFF_ours_vs_random_{f}",
                                     feas=(a.feas - b.feas).mean(), tok=(a.tok - b.tok).mean(), inv=np.nan,
                                     U=m, U_lo=lo, U_hi=hi))
    res = pd.DataFrame(out_rows)
    res.to_csv(os.path.join(RES, "policy_summary.csv"), index=False)
    pd.DataFrame(auc_rows).to_csv(os.path.join(RES, "feature_auc.csv"), index=False)

    # ---- validator-cost break-even (headline lambda, eps=0.02) ----
    base = raw[(raw["mode"] == "eps") & (raw.eps == 0.02)]
    dev, test0 = assemble(base[base["split"] == "dev"]), assemble(base[base["split"] == "test"])
    lam = LAMBDAS[HEADLINE]
    th = tune_theta(dev, "load", lam)
    inv = (test0["load"] >= th).values
    ours = policy_eval(test0, inv, "ours")
    u_ours = (ours.feas - lam * ours.tok).mean()
    be = []
    for c in (0, 50, 150, 300, 600, 1200, 2400):
        t = assemble(base[base["split"] == "test"], c_val=c)
        u_ft = (t.feas_ft - lam * t.tok_ft).mean()
        be.append(dict(c_val=c, U_fail_triggered=u_ft, U_ours=u_ours, ft_minus_ours=u_ft - u_ours))
    pd.DataFrame(be).to_csv(os.path.join(RES, "validator_breakeven.csv"), index=False)

    # ---- by-kind table at default setting ----
    kt = []
    for kind, gk in test0.groupby("kind"):
        kt.append(dict(kind=kind, n=len(gk), feasA=gk.feasA.mean(), feasT=gk.feasT.mean(), tokA=gk.tokA.mean(),
                       tok_team=gk.tok_team.mean(), load=gk["load"].mean(), region=gk.region_proxy.mean()))
    pd.DataFrame(kt).to_csv(os.path.join(RES, "by_kind.csv"), index=False)

    # ---- figures ----
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    # Fig 1: failure rate vs load bins, for eps and flat models
    fig, ax = plt.subplots(1, 2, figsize=(7.4, 3.1), dpi=300)
    for (mode, val), c, lab in [(("eps", 0.02), "#1f77b4", "per-check slips (eps=0.02)"),
                                (("flat", 0.30), "#d62728", "size-independent slip (p=0.30)"),
                                (("loaded", 0.005), "#2ca02c", "load-dependent slips (eps0=0.005, gamma=0.5)")]:
        t = assemble(raw[(raw["mode"] == mode) & (raw.eps == val) & (raw["split"] == "test")])
        t["bin"] = pd.cut(t["load"], [-1, 3, 6, 10, 15, 25, 100], labels=["0-3", "4-6", "7-10", "11-15", "16-25", ">25"])
        g = t.groupby("bin", observed=True).agg(f=("feasA", lambda x: 1 - x.mean()), n=("feasA", "size"))
        ax[0].plot(range(len(g)), g.f, "-o", color=c, label=lab, ms=4)
        ax[0].set_xticks(range(len(g)))
        ax[0].set_xticklabels(g.index)
    ax[0].set_xlabel("Constraint-diff load (checks implied)")
    ax[0].set_ylabel("P(single-agent repair infeasible)")
    ax[0].legend(frameon=False, fontsize=6, loc="upper left")
    # Fig 1b: AUC bars by eps
    A = pd.read_csv(os.path.join(RES, "feature_auc.csv"))
    A["setting"] = A["mode"] + "\n" + A["eps"].astype(str)
    a2 = A.pivot(index="setting", columns="feature", values="auc")
    a2 = a2.loc[[i for i in a2.index if not i.startswith("flat")] + [i for i in a2.index if i.startswith("flat")]]
    a2 = a2[["load", "region_proxy", "changed"]]
    a2.plot(kind="bar", ax=ax[1], width=0.8, color=["#4c78a8", "#f58518", "#54a24b"], rot=0)
    ax[1].axhline(0.5, color="k", lw=0.6, ls=":")
    ax[1].set_ylabel("AUC (predicting single-agent failure)")
    ax[1].set_xlabel("Error model and eps")
    ax[1].tick_params(axis="x", labelsize=6)
    ax[1].set_ylim(0.4, 0.9)
    ax[1].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig1_risk_signal.png"))
    plt.close(fig)

    # Fig 2: frontier at eps=0.02 for the load feature
    fig, ax = plt.subplots(figsize=(3.8, 3.2), dpi=300)
    t = test0
    cl = (t.family + "_" + t.base.astype(str)).values
    ths = sorted(set(t["load"])) + [max(t["load"]) + 1]
    xs, ys = [], []
    for th in ths:
        p = policy_eval(t, (t["load"] >= th).values, "o")
        xs.append(p.tok.mean())
        ys.append(p.feas.mean())
    ax.plot(xs, ys, "-o", ms=3, color="#1f77b4", label="Dependency-load trigger (sweep of threshold)")
    s = policy_eval(t, np.zeros(len(t), bool), "s")
    tm = policy_eval(t, np.ones(len(t), bool), "t")
    ax.plot([s.tok.mean(), tm.tok.mean()], [s.feas.mean(), tm.feas.mean()], "--", color="gray", label="Random mixing (same endpoints)")
    ft = assemble(base[base["split"] == "test"], c_val=C_VAL)
    ax.plot(ft.tok_ft.mean(), ft.feas_ft.mean(), "s", color="#d62728", label=f"Failure-triggered (validator {int(C_VAL)} tok)")
    ax.plot(ft.tok_oracle.mean(), ft.feas_ft.mean(), "^", color="#2ca02c", label="Oracle (free failure signal)")
    ax.set_xlabel("Mean tokens per disruption")
    ax.set_ylabel("Feasible-repair rate")
    ax.legend(frameon=False, fontsize=6, loc="upper center", bbox_to_anchor=(0.5, -0.22))
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig2_frontier.png"), bbox_inches="tight")
    plt.close(fig)
    # ---- fine lambda sweep: how much can a diff-based trigger add over the best corner policy? ----
    lam_grid = np.geomspace(1 / 40000, 1 / 1000, 40)
    sw = []
    for (mode, val) in (("eps", 0.02), ("eps", 0.04), ("loaded", 0.005), ("flat", 0.30)):
        g = raw[(raw["mode"] == mode) & (raw.eps == val)]
        dv, ts = assemble(g[g["split"] == "dev"]), assemble(g[g["split"] == "test"])
        n = len(ts)
        cl = (ts.family + "_" + ts.base.astype(str)).values
        for lam_ in lam_grid:
            th = tune_theta(dv, "load", lam_)
            inv = (ts["load"] >= th).values
            po = policy_eval(ts, inv, "o")
            ps = policy_eval(ts, np.zeros(n, bool), "s")
            pt = policy_eval(ts, np.ones(n, bool), "t")
            u = lambda p: float((p.feas - lam_ * p.tok).mean())
            best_corner = max(u(ps), u(pt))
            corner = ps if u(ps) >= u(pt) else pt  # best fixed corner policy, paired episode by episode
            gain = (po.feas - lam_ * po.tok).values - (corner.feas - lam_ * corner.tok).values
            m, lo, hi = cluster_boot(gain, cl, n=500)
            sw.append(dict(mode=mode, eps=val, lam=lam_, theta=th, inv=float(inv.mean()), U_single=u(ps), U_team=u(pt),
                           U_ours=u(po), gain_over_best_corner=m, gain_lo=lo, gain_hi=hi,
                           U_ft=float((ts.feas_ft - lam_ * ts.tok_ft).mean()),
                           U_oracle=float((ts.feas_ft - lam_ * ts.tok_oracle).mean())))
    swd = pd.DataFrame(sw)
    swd.to_csv(os.path.join(RES, "lambda_sweep.csv"), index=False)
    fig, ax = plt.subplots(1, 2, figsize=(7.4, 3.0), dpi=300)
    for (mode, val), c, lab in [(("eps", 0.02), "#1f77b4", "eps=0.02"), (("loaded", 0.005), "#2ca02c", "load-dependent"),
                                (("flat", 0.30), "#d62728", "size-independent")]:
        q = swd[(swd["mode"] == mode) & (swd.eps == val)]
        ax[0].plot(q.lam * 1000, q.gain_over_best_corner, color=c, label=lab)
        ax[0].fill_between(q.lam * 1000, q.gain_lo, q.gain_hi, color=c, alpha=0.15, lw=0)
    ax[0].axhline(0, color="k", lw=0.6)
    ax[0].set_xscale("log")
    ax[0].set_xlabel("Token price lambda (feasibility per 1k tokens)")
    ax[0].set_ylabel("Utility gain of trigger over best of\nalways-single / always-team")
    ax[0].legend(frameon=False, fontsize=7)
    q = swd[(swd["mode"] == "eps") & (swd.eps == 0.02)]
    for col, lab, c in (("U_single", "always single", "gray"), ("U_team", "always team", "black"), ("U_ours", "dependency trigger", "#1f77b4"),
                        ("U_ft", "failure-triggered (150 tok validator)", "#d62728"), ("U_oracle", "oracle failure signal", "#2ca02c")):
        ax[1].plot(q.lam * 1000, q[col], label=lab, color=c, ls="-" if col != "U_oracle" else "--")
    ax[1].set_xscale("log")
    ax[1].set_xlabel("Token price lambda (feasibility per 1k tokens)")
    ax[1].set_ylabel("Utility = P(feasible) - lambda * tokens")
    ax[1].legend(frameon=False, fontsize=6)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig3_lambda_sweep.png"))
    plt.close(fig)
    print(swd.groupby(["mode", "eps"]).agg(max_gain=("gain_over_best_corner", "max"), lam_at_max=("lam", lambda x: x.iloc[int(np.argmax(swd.loc[x.index, "gain_over_best_corner"].values))])).to_string())
    print(res[(res.lam == HEADLINE) & (res.eps == 0.02) & (res["mode"] == "eps")].round(4).to_string())
    print(pd.read_csv(os.path.join(RES, "feature_auc.csv")).round(3).to_string())
    print(pd.read_csv(os.path.join(RES, "validator_breakeven.csv")).round(4).to_string())
    print(pd.read_csv(os.path.join(RES, "by_kind.csv")).round(3).to_string())


if __name__ == "__main__":
    main()
