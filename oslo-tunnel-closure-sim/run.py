"""Run the 10 closure simulations (+ matching no-closure baselines), save
results.json, figures/*.png and tables.md."""
import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

import network as net
import sim as S

SCALE = 48000
OUT = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(OUT, "figures")
os.makedirs(FIG, exist_ok=True)

# Chart tokens (reference palette, light mode)
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
C1, C2, MUTED = "#2a78d6", "#eb6834", "#b9b8b2"
SEQ = ["#fcfcfb", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "text.color": INK, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.6, "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "lines.linewidth": 2})

DEP_BINS = [("08:15", 105), ("08:30", 120), ("09:30", 180), ("10:30", 240),
            ("11:30", 300), ("12:30", 360), ("13:30", 420)]


def tick_clock(ax):
    ticks = list(range(30, S.T_END + 1, 60))
    ax.set_xticks(ticks)
    ax.set_xticklabels([S.clock(t) for t in ticks])
    ax.axvspan(S.T_CLOSE, S.T_REOPEN, color="#f0efec", zorder=0, lw=0)


def bus_tunnel_exposure(sim):
    """Buses (and passengers) inside tunnels at the moment of closure."""
    buses, pax = 0.0, 0.0
    for name, (nodes, freq, load) in net.BUS_LINES.items():
        for a, b in zip(nodes[:-1], nodes[1:]):
            for lid in sim.out_links[a]:
                L = sim.links[lid]
                if L.b == b and L.tunnel:
                    nb = freq / 60.0 * sim.link_tt_hist[lid, S.T_CLOSE]
                    buses += nb
                    pax += nb * load
                    break
    return buses, pax


def recovery_time(sim, base):
    """First time after reopening when local-street queues and jams are back near baseline."""
    for t in range(S.T_REOPEN, S.T_END - 15):
        ok = all(sim.ts["in_orig"][k] <= base.ts["in_orig"][k] + 300 and
                 sim.ts["jam_lane_km"][k] <= base.ts["jam_lane_km"][k] + 8
                 for k in range(t, t + 15))
        if ok:
            return t
    return None


def summarise(p, sim, base):
    r = {"name": p["name"], "short": p["short"], "desc": p["desc"]}
    trapped_veh = sum(sim.trapped.values())
    b_n, b_pax = bus_tunnel_exposure(sim)
    r["trapped_veh"] = trapped_veh
    r["trapped_buses"] = b_n
    r["trapped_persons"] = trapped_veh * S.CAR_OCC + b_pax
    r["trapped_by_tunnel"] = {k: round(v) for k, v in sim.trapped.items()}
    r["last_out"] = {k: S.clock(v) for k, v in sim.trapped_time.items()}
    r["max_trapped_min"] = max(v - S.T_CLOSE for v in sim.trapped_time.values())
    tr = np.array(sim.ts["trapped"])
    r["trapped_after_60"] = float(tr[60]) if len(tr) > 60 else 0
    lq = np.array(sim.ts["in_orig"]) / S.JAM_DENSITY  # local street queue (lane-km)
    jam = np.array(sim.ts["jam_lane_km"])
    r["peak_jam_lane_km"] = float(jam.max())
    r["peak_local_queue_lane_km"] = float(lq.max())
    r["peak_total_queue_lane_km"] = float((jam + lq).max())
    r["peak_total_t"] = S.clock(int((jam + lq).argmax()))
    r["peak_waiting_veh"] = float(np.max(sim.ts["in_orig"]))
    r["grid_link_minutes"] = int(np.sum(sim.ts["grid_links"]))
    r["peak_grid_links"] = int(np.max(sim.ts["grid_links"]))
    r["veh_hours_delay"] = S.total_delay(sim, base)
    r["person_hours_delay"] = r["veh_hours_delay"] * S.CAR_OCC
    r["cost_mnok"] = r["veh_hours_delay"] * 300 / 1e6  # blended value of time incl. freight
    r["cancelled_trips"] = sim.cancelled
    r["abandoned_trips"] = sim.abandoned - base.abandoned
    r["modeshift_persons"] = sim.modeshift
    r["modeshift_peak_hour"] = max(sim.modeshift_by_hour.values()) if sim.modeshift_by_hour else 0
    rec = recovery_time(sim, base)
    r["recovery"] = S.clock(rec) if rec is not None else "after 16:00"
    r["recovery_min_after_reopen"] = (rec - S.T_REOPEN) if rec is not None else None
    # area spread: first time >=25% of area lane-km congested, and max share
    first, mx = {}, {}
    for (t, row), (_, brow) in zip(sim.area_hist, base.area_hist):
        for a, v in row.items():
            mx[a] = max(mx.get(a, 0), v)
            if t >= S.T_CLOSE and v >= 0.25 and v > brow[a] + 0.1 and a not in first:
                first[a] = S.clock(t)
    r["area_first_congested"] = first
    r["area_max_share"] = mx
    # emergency services during the closure window
    ev = [e for e in sim.ev_hist if S.T_CLOSE <= e["t"] <= S.T_REOPEN]
    evb = [e for e in base.ev_hist if S.T_CLOSE <= e["t"] <= S.T_REOPEN]
    r["amb12_min"] = min(e["amb12"] for e in ev)
    r["amb12_mean"] = float(np.mean([e["amb12"] for e in ev]))
    r["amb12_base"] = float(np.mean([e["amb12"] for e in evb]))
    r["fire10_min"] = min(e["fire10"] for e in ev)
    r["fire10_base"] = float(np.mean([e["fire10"] for e in evb]))
    r["amb_mean_max"] = max(e["amb_mean"] for e in ev)
    r["amb_mean_base"] = float(np.mean([e["amb_mean"] for e in evb]))
    w = max(ev, key=lambda e: e["worst_t"])
    r["worst_zone"] = net.NODES[w["worst"]][0]
    r["worst_zone_t"] = w["worst_t"]
    r["worst_zone_clock"] = S.clock(w["t"])
    # hospital access (nearest hospital, resident weighted) at 09:30 / 10:30
    def hosp(simx, t):
        e = next(e for e in simx.ev_hist if e["t"] == t)
        h = e["hosp"]
        tot = sum(net.ZONES[z][0] for z in h)
        return sum(net.ZONES[z][0] * min(h[z], 120) for z in h) / tot, max(h.items(), key=lambda kv: kv[1])
    for lab, t in (("0930", 180), ("1030", 240)):
        m, (z, v) = hosp(sim, t)
        mb, _ = hosp(base, t)
        r[f"hosp_{lab}"] = m
        r[f"hosp_{lab}_base"] = mb
        r[f"hosp_{lab}_worst"] = (net.NODES[z][0], v)
    # key car trips
    kt = {}
    for (o, d) in net.KEY_TRIPS:
        row = {}
        for lab, t in DEP_BINS:
            b = t // 15
            row[lab] = (S.trip_tt(sim, o, d, b), S.trip_tt(base, o, d, b))
        kt[f"{o}-{d}"] = row
    r["key_trips"] = kt
    # buses and trams
    bus = {}
    for name, (nodes, freq, load) in net.BUS_LINES.items():
        row = {}
        for lab, t in [("07:45", 75)] + DEP_BINS:
            tt, det = sim.corridor_time(nodes, t)
            tb, _ = base.corridor_time(nodes, t)
            row[lab] = (tt, tb, det)
        bus[name] = row
    r["bus"] = bus
    tram = {}
    for name, (nodes, share) in net.TRAM_LINES.items():
        row = {}
        for lab, t in DEP_BINS:
            tt, _ = sim.corridor_time(nodes, t, bus=False, mixed_share=share)
            tb, _ = base.corridor_time(nodes, t, bus=False, mixed_share=share)
            row[lab] = (tt, tb)
        tram[name] = row
    r["tram"] = tram
    return r


def main():
    results, sims, bases = [], [], []
    for p in S.SCENARIOS:
        base = S.Sim(p, closure=False, scale=SCALE).run()
        sim = S.Sim(p, closure=True, scale=SCALE).run()
        r = summarise(p, sim, base)
        print(f"{p['short']:4s} delay {r['veh_hours_delay']:9.0f} vh  queue {r['peak_total_queue_lane_km']:6.0f} lane-km "
              f"amb12 min {r['amb12_min']:.2f} recovery {r['recovery']}")
        results.append(r)
        sims.append(sim)
        bases.append(base)
    with open(os.path.join(OUT, "results.json"), "w") as f:
        json.dump(results, f, indent=1, ensure_ascii=False, default=float)
    figures(sims, bases, results)


# ---------------------------------------------------------------------------
def figures(sims, bases, results):
    t = np.arange(S.T_END + 1)
    # 1) total queue lane-km (network jams + local-street queues), highlight S1 & S10
    fig, ax = plt.subplots(figsize=(9, 4.2))
    tick_clock(ax)
    for i, s in enumerate(sims):
        y = np.array(s.ts["jam_lane_km"]) + np.array(s.ts["in_orig"]) / S.JAM_DENSITY
        if i in (0, 9):
            continue
        ax.plot(t, y, color=MUTED, lw=1.2)
    yb = np.array(bases[0].ts["jam_lane_km"]) + np.array(bases[0].ts["in_orig"]) / S.JAM_DENSITY
    ax.plot(t, yb, color=INK2, lw=1.5, ls="--")
    for i, c in ((0, C1), (9, C2)):
        s = sims[i]
        y = np.array(s.ts["jam_lane_km"]) + np.array(s.ts["in_orig"]) / S.JAM_DENSITY
        ax.plot(t, y, color=c)
    ax.text(S.T_CLOSE + 3, ax.get_ylim()[1] * 0.95, "All tunnels closed 08:05–12:05", color=INK2, va="top")
    ax.plot([], [], color=C1, label="S1 Reference")
    ax.plot([], [], color=C2, label="S10 Compound worst case")
    ax.plot([], [], color=MUTED, lw=1.2, label="S2–S9")
    ax.plot([], [], color=INK2, ls="--", lw=1.5, label="Normal day (S1 baseline)")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=4)
    ax.set_ylabel("Queued lane-km (main roads + local streets)")
    ax.set_title("Queue build-up across the Oslo area", loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "01_queue_lane_km.png"), dpi=150)
    plt.close(fig)

    # 2) area heatmaps S1 and S10
    cmap = LinearSegmentedColormap.from_list("seq", SEQ)
    areas = list(sims[0].area_hist[0][1].keys())
    order = ["Sentrum", "Indre vest", "Indre øst", "Indre nord", "Ytre vest", "Ytre øst", "Søndre",
             "Groruddalen", "Bærum", "Asker", "Follo", "Romerike", "Nittedal"]
    areas = [a for a in order if a in areas]
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
    for ax, i in zip(axs, (0, 9)):
        h = sims[i].area_hist
        M = np.array([[row[a] for (_, row) in h] for a in areas])
        ts = [x for (x, _) in h]
        im = ax.imshow(M, aspect="auto", cmap=cmap, vmin=0, vmax=1,
                       extent=[ts[0], ts[-1], len(areas) - 0.5, -0.5], interpolation="nearest")
        ax.set_yticks(range(len(areas)))
        ax.set_yticklabels(areas)
        ticks = list(range(30, S.T_END + 1, 90))
        ax.set_xticks(ticks)
        ax.set_xticklabels([S.clock(x) for x in ticks])
        ax.axvline(S.T_CLOSE, color=C2, lw=1.2)
        ax.axvline(S.T_REOPEN, color=C2, lw=1.2, ls="--")
        ax.grid(False)
        ax.set_title(results[i]["name"], loc="left", fontsize=10)
    cb = fig.colorbar(im, ax=axs, shrink=0.85)
    cb.set_label("Share of area's road lane-km congested (>60 % of jam density)")
    fig.suptitle("How congestion spreads by area (solid line: closure, dashed: reopening)",
                 x=0.01, ha="left", fontsize=11)
    fig.savefig(os.path.join(FIG, "02_area_spread.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 3) network maps (S1) at 4 moments
    def draw_map(sim, times, fname, title):
        fig, axs = plt.subplots(1, len(times), figsize=(4 * len(times), 4.6))
        for ax, tm in zip(axs, times):
            occ = sim.occ_hist[tm]
            for l in sim.links:
                if l.id % 2:  # draw each physical link once, worst direction
                    continue
                v = max(occ[l.id], occ[l.id + 1])
                closed = sim.tunnel_closed_in(l, tm)
                a, b = net.NODES[l.a], net.NODES[l.b]
                col = cmap(min(v, 1.0) * 0.85 + 0.15)
                ax.plot([a[2], b[2]], [a[1], b[1]], color=("#e34948" if closed else col),
                        lw=(1.2 + l.lanes * 0.9), ls=(":" if closed else "-"),
                        solid_capstyle="round", zorder=2)
            for k, (nm, la, lo, ar) in net.NODES.items():
                ax.plot(lo, la, "o", ms=2.5, color=INK2, zorder=3)
            ax.set_xlim(10.60, 10.98)
            ax.set_ylim(59.83, 59.99)
            ax.set_aspect(1 / np.cos(np.radians(59.9)))
            ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
            ax.set_title(S.clock(tm), loc="left", fontsize=10)
            for k in ("SEN", "LYS", "RYE", "OKE", "ULL", "ALN"):
                nm, la, lo, _ = net.NODES[k]
                ax.text(lo, la + 0.004, nm.split(" /")[0].split(" (")[0], fontsize=6.5, color=INK2, ha="center")
        fig.suptitle(title + "  (red dotted = closed tunnel; darker blue = fuller road)",
                     x=0.01, ha="left", fontsize=11)
        fig.tight_layout()
        fig.savefig(os.path.join(FIG, fname), dpi=150)
        plt.close(fig)
    draw_map(sims[0], [90, 135, 210, 360], "03_map_S1.png", "S1 Reference – inner Oslo")
    draw_map(sims[9], [90, 135, 210, 360], "04_map_S10.png", "S10 Compound worst case – inner Oslo")

    # 4) ambulance coverage
    fig, ax = plt.subplots(figsize=(9, 4))
    tick_clock(ax)
    for i, s in enumerate(sims):
        ts = [e["t"] for e in s.ev_hist]
        ys = [e["amb12"] * 100 for e in s.ev_hist]
        if i not in (0, 9):
            ax.plot(ts, ys, color=MUTED, lw=1.2)
    b = bases[0]
    ax.plot([e["t"] for e in b.ev_hist], [e["amb12"] * 100 for e in b.ev_hist], color=INK2, ls="--", lw=1.5)
    for i, c in ((0, C1), (9, C2)):
        s = sims[i]
        ax.plot([e["t"] for e in s.ev_hist], [e["amb12"] * 100 for e in s.ev_hist], color=c)
    ax.plot([], [], color=C1, label="S1 Reference")
    ax.plot([], [], color=C2, label="S10 Compound worst case")
    ax.plot([], [], color=MUTED, lw=1.2, label="S2–S9")
    ax.plot([], [], color=INK2, ls="--", lw=1.5, label="Normal day")
    ax.set_ylim(0, 100)
    ax.set_xlim(70, S.T_END)
    ax.set_ylabel("% of residents reachable within 12 min")
    ax.set_title("Ambulance coverage (12-minute target)", loc="left", fontsize=11)
    ax.legend(frameon=False, loc="lower left")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "05_ambulance_coverage.png"), dpi=150)
    plt.close(fig)

    # 5) trapped vehicles remaining
    fig, ax = plt.subplots(figsize=(9, 3.6))
    tick_clock(ax)
    for i, s in enumerate(sims):
        y = s.ts["trapped"]
        x = np.arange(S.T_CLOSE, S.T_CLOSE + len(y))
        col = C1 if i == 0 else (C2 if i == 9 else MUTED)
        ax.plot(x, y, color=col, lw=2 if i in (0, 9) else 1.2)
    ax.plot([], [], color=C1, label="S1 (held, then escorted out)")
    ax.plot([], [], color=C2, label="S10 (held for whole closure)")
    ax.plot([], [], color=MUTED, lw=1.2, label="Other simulations (S7 = held)")
    ax.legend(frameon=False)
    ax.set_xlim(80, S.T_END)
    ax.set_ylabel("Vehicles still inside tunnels")
    ax.set_title("Vehicles trapped inside closed tunnels", loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "06_trapped.png"), dpi=150)
    plt.close(fig)

    # 6) delay per simulation (bar)
    fig, ax = plt.subplots(figsize=(9, 3.6))
    names = [r["short"] for r in results]
    vals = [r["veh_hours_delay"] / 1000 for r in results]
    ax.bar(names, vals, color=C1, width=0.6)
    for x, v in zip(names, vals):
        ax.text(x, v, f"{v:.0f}", ha="center", va="bottom", fontsize=8, color=INK2)
    ax.set_ylabel("Extra vehicle-hours (thousands)")
    ax.set_title("Total extra delay for road users, 08:05–16:00", loc="left", fontsize=11)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "07_delay.png"), dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
