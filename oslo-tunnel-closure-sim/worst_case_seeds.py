"""Robustness check: re-run the top worst-case candidates with 3 random seeds,
then plot the basin time series for the confirmed worst case."""
import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import sim as S
import worst_case as W

HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = [("snow", "slow", "basin", "high"), ("snow", "slow", "E18", "high"),
              ("snow", "none", "basin", "high")]
SEEDS = [201, 202, 203]


def params(w, i, inc, d, seed):
    p = dict(S.BASE)
    p.update(W.WEATHER[w]); p.update(W.INFO[i])
    p["demand"] = p.get("demand", 1.0) * W.DEMAND[d]
    p.update(halt_all=True, evac_on_foot=(35, 90), clear_delay=(30, 60),
             incidents=W.INCIDENTS[inc], seed=seed)
    return p


def main():
    out, keep = [], {}
    for c in CANDIDATES:
        runs = []
        for sd in SEEDS:
            p = params(*c, sd)
            base = S.Sim(p, closure=False, scale=W.SCALE).run()
            sim, r = W.evaluate(p, base)
            runs.append(r)
            keep[(c, sd)] = (sim, base)
            print(c, sd, r["resolved"], round(r["basin_stuck_peak"]), r["basin_grid_link_min"], flush=True)
        res = [r["resolve_min_after_reopen"] or (S.T_END - S.T_REOPEN) for r in runs]
        out.append(dict(name="/".join(c), runs=runs, mean_resolve_min=float(np.mean(res)),
                        mean_peak=float(np.mean([r["basin_stuck_peak"] for r in runs])),
                        mean_vh=float(np.mean([r["basin_vh_stuck"] for r in runs])),
                        mean_grid=float(np.mean([r["basin_grid_link_min"] for r in runs]))))
    out.sort(key=lambda x: x["mean_resolve_min"], reverse=True)
    json.dump(out, open(os.path.join(HERE, "worst_case_seeds.json"), "w"), indent=1, ensure_ascii=False)
    # plot worst candidate (median seed) vs its baseline
    best = tuple(out[0]["name"].split("/"))
    fig, ax = plt.subplots(figsize=(9, 4))
    t = np.arange(S.T_END + 1)
    ticks = list(range(30, S.T_END + 1, 120))
    ax.set_xticks(ticks); ax.set_xticklabels([S.clock(x) for x in ticks])
    ax.axvspan(S.T_CLOSE, S.T_REOPEN, color="#f0efec", lw=0, zorder=0)
    for k, sd in enumerate(SEEDS):
        sim, base = keep[(best, sd)]
        ax.plot(t, np.array(sim.ts["basin_stuck"]) / 1000, color="#2a78d6" if k == 0 else "#86b6ef",
                lw=2 if k == 0 else 1.2)
    ax.plot(t, np.array(base.ts["basin_stuck"]) / 1000, color="#52514e", ls="--", lw=1.5)
    ax.plot([], [], color="#2a78d6", label="Worst case (3 random seeds)")
    ax.plot([], [], color="#52514e", ls="--", label="Same day, no closure")
    ax.legend(frameon=False, loc="upper right")
    ax.set_ylabel("Vehicles stuck in the Oslo basin (thousands)")
    ax.set_title("Worst case: snow + slow info + basin collisions + high demand + held tunnels",
                 loc="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "figures", "08_worst_case_basin.png"), dpi=150)
    # map of the worst case at 13:00, 16:30, 18:30
    W_sim = keep[(best, SEEDS[0])][0]
    import run as R
    R_draw = R.__dict__
    # reuse map drawing from run.py by temporarily setting times
    from matplotlib.colors import LinearSegmentedColormap
    import network as net
    cmap = LinearSegmentedColormap.from_list("seq", R.SEQ)
    times = [390, 600, 720]
    fig, axs = plt.subplots(1, 3, figsize=(12, 4.6))
    for ax, tm in zip(axs, times):
        occ = W_sim.occ_hist[tm]
        for l in W_sim.links:
            if l.id % 2:
                continue
            v = max(occ[l.id], occ[l.id + 1])
            closed = W_sim.tunnel_closed_in(l, tm)
            a, b = net.NODES[l.a], net.NODES[l.b]
            ax.plot([a[2], b[2]], [a[1], b[1]], color=("#e34948" if closed else cmap(min(v, 1) * 0.85 + 0.15)),
                    lw=1.2 + l.lanes * 0.9, ls=(":" if closed else "-"), solid_capstyle="round")
        for k, (nm, la, lo, ar) in net.NODES.items():
            ax.plot(lo, la, "o", ms=2.5, color="#52514e")
        for k in ("SEN", "LYS", "RYE", "OKE", "ULL", "ALN"):
            nm, la, lo, _ = net.NODES[k]
            ax.text(lo, la + 0.004, nm.split(" /")[0].split(" (")[0], fontsize=6.5, color="#52514e", ha="center")
        ax.set_xlim(10.60, 10.98); ax.set_ylim(59.83, 59.99)
        ax.set_aspect(1 / np.cos(np.radians(59.9)))
        ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
        ax.set_title(S.clock(tm), loc="left", fontsize=10)
    fig.suptitle("Worst case – inner Oslo after reopening (darker blue = fuller road; red dotted = still closed)",
                 x=0.01, ha="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "figures", "09_worst_case_map.png"), dpi=150)


if __name__ == "__main__":
    main()
