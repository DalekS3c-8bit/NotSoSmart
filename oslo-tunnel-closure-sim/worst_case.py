"""Search for the scenario that produces the worst and longest-lasting gridlock
inside the Oslo basin (Oslogryta). Simulates 06:30-22:00 so that the full
recovery, including the afternoon peak, is captured."""
import itertools
import json
import os

import numpy as np

import sim as S

S.T_END = 22 * 60 - S.T_START_CLOCK   # extend horizon to 22:00
HERE = os.path.dirname(os.path.abspath(__file__))
SCALE = 48000

WEATHER = {"rain": dict(cap=0.92, speed=0.92, demand=1.03),
           "snow": dict(cap=0.80, speed=0.75, p_modeshift=0.12, ev_factor=0.85)}
INFO = {"slow": dict(app_delay=25, Imax=0.55, tau=45, p_cancel=0.15, p_modeshift=0.10),
        # VTS/DATEX feed down as well (e.g. cyber incident): apps keep routing to
        # closed tunnels for an hour, very few drivers informed
        "none": dict(app_delay=60, Imax=0.45, tau=60, p_cancel=0.08, p_modeshift=0.06)}
INCIDENTS = {
    "E18": [(("SKO", "FIL"), 35, 60, 0.4), (("FIL", "SKO"), 35, 60, 0.6)],
    # collisions on the basin's internal relief routes
    "basin": [(("ENS", "HEL"), 25, 90, 0.4), (("HEL", "ENS"), 25, 90, 0.5),
              (("GRU", "TOY"), 55, 75, 0.5), (("TOY", "GRU"), 55, 75, 0.5),
              (("BJV", "SJU"), 70, 60, 0.3), (("SJU", "BJV"), 70, 60, 0.3)],
}
DEMAND = {"normal": 1.0, "high": 1.08}


def basin_resolution(sim, base):
    bs, bb = np.array(sim.ts["basin_stuck"]), np.array(base.ts["basin_stuck"])
    for t in range(S.T_REOPEN, len(bs) - 30):
        if np.all(bs[t:t + 30] <= bb[t:t + 30] + 300):
            return t
    return None


def evaluate(p, base):
    sim = S.Sim(p, closure=True, scale=SCALE).run()
    bs = np.array(sim.ts["basin_stuck"])
    res = basin_resolution(sim, base)
    return sim, dict(
        basin_stuck_peak=float(bs.max()), basin_stuck_peak_t=S.clock(int(bs.argmax())),
        basin_vh_stuck=float((bs - np.array(base.ts["basin_stuck"])).clip(0).sum() / 60),
        basin_grid_peak=int(max(sim.ts["basin_grid"])),
        basin_grid_link_min=int(sum(sim.ts["basin_grid"])),
        resolved=S.clock(res) if res else "not by 22:00",
        resolve_min_after_reopen=(res - S.T_REOPEN) if res else None,
        still_stuck_2200=float(bs[-1] - base.ts["basin_stuck"][-1]),
        total_vh=S.total_delay(sim, base), abandoned=sim.abandoned - base.abandoned)


def main():
    bases, rows = {}, []
    for w, i, inc, d in itertools.product(WEATHER, INFO, INCIDENTS, DEMAND):
        p = dict(S.BASE)
        p.update(WEATHER[w]); p.update(INFO[i])
        p["demand"] = p.get("demand", 1.0) * DEMAND[d]
        p.update(halt_all=True, evac_on_foot=(35, 90), clear_delay=(30, 60),
                 incidents=INCIDENTS[inc], seed=100)
        p["name"] = f"{w}/{i}-info/{inc}-crash/{d}-demand"
        key = (w, d)
        if key not in bases:
            bases[key] = S.Sim(p, closure=False, scale=SCALE).run()
        _, r = evaluate(p, bases[key])
        r["name"] = p["name"]
        rows.append(r)
        print(f"{p['name']:40s} peak stuck {r['basin_stuck_peak']:7.0f} ({r['basin_stuck_peak_t']}) "
              f"grid-min {r['basin_grid_link_min']:5d} resolved {r['resolved']}", flush=True)
    rows.sort(key=lambda r: (r["resolve_min_after_reopen"] is None,
                             r["resolve_min_after_reopen"] or 0, r["basin_vh_stuck"]), reverse=True)
    json.dump(rows, open(os.path.join(HERE, "worst_case_search.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
