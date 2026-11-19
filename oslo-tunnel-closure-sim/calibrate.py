"""Calibrate the OD matrix so that simulated AM peak-hour tunnel volumes match
published ÅDT counts (network.COUNTS) converted with PEAK_HOUR_SHARE.

Method: iterative proportional link-count fitting. For each counted tunnel the
ratio target/simulated is computed; every OD pair's factor is updated with the
flow-weighted geometric mean of the ratios of the counted tunnels it uses.
"""
import json
import math
import os
from collections import defaultdict

import network as net
import sim as S

HERE = os.path.dirname(os.path.abspath(__file__))
SCALE = 48000


def peak_counts(sim):
    vol = defaultdict(float)
    for (tn, o, d), n in sim.tun_od.items():
        vol[tn] += n
    return vol


def main(iters=6):
    if os.path.exists(os.path.join(HERE, "calibration.json")):
        os.remove(os.path.join(HERE, "calibration.json"))
    S.OD_FACTORS.clear()
    target = {tn: c[0] * net.PEAK_HOUR_SHARE for tn, c in net.COUNTS.items()}
    p = dict(S.SCENARIOS[0])
    history = []
    for it in range(iters + 1):
        sim = S.Sim(p, closure=False, scale=SCALE).run()
        vol = peak_counts(sim)
        err = {tn: (vol[tn] - target[tn]) / target[tn] for tn in target}
        rmse = math.sqrt(sum(e * e for e in err.values()) / len(err))
        history.append({"iter": it, "rmse_pct": rmse * 100,
                        "rows": {tn: [round(vol[tn]), round(target[tn])] for tn in target}})
        print(f"iter {it}: RMSE {rmse*100:.1f} %  " +
              ", ".join(f"{tn.split(' (')[0]} {e*100:+.0f}%" for tn, e in err.items()))
        if it == iters:
            break
        ratio = {tn: max(0.4, min(2.5, target[tn] / max(vol[tn], 1))) for tn in target}
        acc = defaultdict(lambda: [0.0, 0.0])
        for (tn, o, d), n in sim.tun_od.items():
            if tn in ratio:
                acc[(o, d)][0] += n * math.log(ratio[tn])
                acc[(o, d)][1] += n
        for (o, d), (s_, w) in acc.items():
            f = math.exp(0.8 * s_ / w)  # damped update
            key = f"{o}|{d}"
            S.OD_FACTORS[key] = max(0.25, min(4.0, S.OD_FACTORS.get(key, 1.0) * f))
    json.dump({"od_factors": S.OD_FACTORS, "history": history,
               "peak_hour_share": net.PEAK_HOUR_SHARE}, open(os.path.join(HERE, "calibration.json"), "w"),
              indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
