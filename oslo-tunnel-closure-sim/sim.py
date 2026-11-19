"""
Mesoscopic dynamic traffic simulation of an unplanned closure of ALL road
tunnels in the Oslo metropolitan area (weekday, 08:05-12:05).

Model summary
-------------
* Time step: 1 minute, simulated window 06:30-16:00.
* Vehicles move as packets through a directed link network.  Each link is a
  point queue with a free-flow travel time, an outflow capacity and a finite
  storage (jam density 130 veh/km/lane).  When a downstream link is full the
  upstream link cannot discharge -> queues spill back and can create gridlock.
* Route choice is adaptive: "informed" drivers (apps, radio, VMS) follow
  shortest-path trees recomputed every 5 minutes from current travel times;
  "uninformed" drivers follow habitual routes and only re-route when they hit
  a closed tunnel portal.
* Demand: gravity-model OD matrix (home->work in the morning, reversed in the
  afternoon) plus freight.  After the closure, informed travellers who have
  not yet departed may cancel/postpone or shift to rail/metro.
* Emergency vehicles: multi-source shortest paths from stations using
  congestion-dependent blue-light speeds; closed tunnels are impassable.
* Buses / trams: travel times derived from simulated link travel times along
  their corridors (re-routed around closed tunnels).
"""
import heapq
import math
import random
from collections import deque, defaultdict

import numpy as np

import network as net

T_START_CLOCK = 6 * 60 + 30          # simulation minute 0 = 06:30
T_END = 16 * 60 - T_START_CLOCK       # 16:00
T_CLOSE = 8 * 60 + 5 - T_START_CLOCK  # 08:05
T_REOPEN = 12 * 60 + 5 - T_START_CLOCK  # 12:05 (4 hours)
JAM_DENSITY = 130.0                   # veh/km/lane
CAR_OCC = 1.15                        # persons per car (commute peak)
PACKET_MIN = 2.0                      # emit OD packet when >= 2 vehicles accumulated

# OD adjustment factors from calibrate.py (matrix calibrated to published counts)
import json as _json
import os as _os
_CAL = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "calibration.json")
OD_FACTORS = _json.load(open(_CAL))["od_factors"] if _os.path.exists(_CAL) else {}

# Areas regarded as "the Oslo basin" (Oslogryta) for gridlock metrics
BASIN = {"Sentrum", "Indre vest", "Indre øst", "Indre nord", "Ytre vest", "Ytre øst",
         "Søndre", "Groruddalen"}


def clock(t):
    """Convert simulation minute to HH:MM string."""
    m = int(round(t)) + T_START_CLOCK
    return f"{m // 60:02d}:{m % 60:02d}"


# ---------------------------------------------------------------------------
# Network construction
# ---------------------------------------------------------------------------
class Link:
    __slots__ = ("id", "a", "b", "length", "cap_h", "ff_kmh", "lanes", "tunnel",
                 "road", "storage", "q", "occ", "budget", "closed_in", "flow",
                 "out_factor", "cap_factor", "out_hist", "queued", "ev_block")

    def __init__(self, lid, a, b, length, cap_h, ff_kmh, lanes, tunnel, road):
        self.id, self.a, self.b = lid, a, b
        self.length, self.cap_h, self.ff_kmh = length, cap_h, ff_kmh
        self.lanes, self.tunnel, self.road = lanes, tunnel, road
        self.storage = length * lanes * JAM_DENSITY
        self.q = deque()
        self.occ = 0.0
        self.budget = 0.0
        self.closed_in = False
        self.out_factor = 1.0
        self.cap_factor = 1.0
        self.out_hist = deque([cap_h / 60.0] * 5, maxlen=5)
        self.queued = 0.0
        self.flow = []


def build_links():
    links = []
    for (a, b, length, cap, ff, lanes, tunnel, road) in net.LINKS:
        for (x, y) in ((a, b), (b, a)):
            links.append(Link(len(links), x, y, length, cap, ff, lanes, tunnel, road))
    return links


# ---------------------------------------------------------------------------
# Shortest paths
# ---------------------------------------------------------------------------
def tree_to(dest, links, in_links, cost):
    """Dijkstra on reversed graph: returns (dist, next_link) towards dest."""
    dist = {dest: 0.0}
    nxt = {}
    pq = [(0.0, dest)]
    while pq:
        d, v = heapq.heappop(pq)
        if d > dist.get(v, 1e18):
            continue
        for lid in in_links[v]:
            c = cost[lid]
            if c is None:
                continue
            u = links[lid].a
            nd = d + c
            if nd < dist.get(u, 1e18):
                dist[u] = nd
                nxt[u] = lid
                heapq.heappush(pq, (nd, u))
    return dist, nxt


def dist_from(sources, links, out_links, cost, delay0=0.0):
    """Multi-source Dijkstra (forward)."""
    dist = {s: delay0 for s in sources}
    pq = [(delay0, s) for s in sources]
    heapq.heapify(pq)
    while pq:
        d, v = heapq.heappop(pq)
        if d > dist.get(v, 1e18):
            continue
        for lid in out_links[v]:
            c = cost[lid]
            if c is None:
                continue
            u = links[lid].b
            nd = d + c
            if nd < dist.get(u, 1e18):
                dist[u] = nd
                heapq.heappush(pq, (nd, u))
    return dist


# ---------------------------------------------------------------------------
# Demand
# ---------------------------------------------------------------------------
def build_od(links, out_links, scale):
    """Gravity model OD for the morning (home->work) direction, veh/h at peak."""
    zones = list(net.ZONES)
    ff = {l.id: l.length / l.ff_kmh * 60 for l in links}
    od = {}
    tt = {}
    for o in zones:
        tt[o] = dist_from([o], links, out_links, ff)
    beta = 0.075
    total = 0.0
    for o in zones:
        R, J, cs = net.ZONES[o]
        P = R * cs
        w = {}
        for d in zones:
            if d == o:
                continue
            Rd, Jd, _ = net.ZONES[d]
            A = Jd * net.ATTRACTION_FACTOR.get(d, 1.0)
            w[d] = A * math.exp(-beta * (tt[o][d] + 6))
        s = sum(w.values())
        for d, x in w.items():
            od[(o, d)] = P * x / s
            total += od[(o, d)]
    # freight / commercial (~12% of traffic, symmetric)
    fw = {}
    for o, fo in net.FREIGHT.items():
        for d, fd in net.FREIGHT.items():
            if o != d:
                fw[(o, d)] = fo * fd * math.exp(-0.03 * tt[o][d])
    fs = sum(fw.values())
    for k, x in fw.items():
        od[k] = od.get(k, 0) + 0.12 * total * x / fs
    tot = sum(od.values())
    return {k: v * scale / tot for k, v in od.items()}, tt


def profile(t):
    """Relative departure intensity (minute t) for AM, midday and PM components."""
    clk = t + T_START_CLOCK
    h = clk / 60.0
    # morning peak (home->work)
    am = math.exp(-0.5 * ((h - 7.9) / 0.55) ** 2)
    # midday (both directions)
    md = 0.30 if 9 <= h <= 15 else 0.15
    # afternoon (work->home), starts building after 14:00
    pm = 0.95 * math.exp(-0.5 * ((h - 16.0) / 0.7) ** 2)
    return am, md, pm


# ---------------------------------------------------------------------------
# Scenario definitions (10 simulations)
# ---------------------------------------------------------------------------
BASE = dict(
    cap=1.0, speed=1.0, demand=1.0,
    app_delay=10, I0=0.35, Imax=0.75, tau=25,
    p_cancel=0.25, p_return=0.45, p_modeshift=0.15,
    hold=(15, 40), escort_factor=0.30, halt_all=False, evac_on_foot=None,
    clear_delay=(0, 10), incidents=[], atm_boost=0.0, atm_from=30,
    metering=0.0, ev_factor=1.0, seed=1,
)


def scen(name, short, desc, **kw):
    p = dict(BASE)
    p.update(kw)
    p["name"], p["short"], p["desc"] = name, short, desc
    return p


SCENARIOS = [
    scen("S1 Reference", "S1", "Dry roads, normal weekday demand, normal information spread. "
         "Vehicles inside tunnels held 15–40 min, then escorted out.", seed=11),
    scen("S2 Rain", "S2", "Wet roads: capacity −8 %, speeds −8 %, demand +3 % (more people drive).",
         cap=0.92, speed=0.92, demand=1.03, seed=12),
    scen("S3 Snow / winter", "S3", "Snowfall: capacity −20 %, speeds −25 %, emergency vehicles slower, "
         "less mode shift (crowded platforms).", cap=0.80, speed=0.75, p_modeshift=0.12,
         ev_factor=0.85, hold=(20, 50), seed=13),
    scen("S4 Fast coordinated information", "S4", "VTS/police/Ruter push alerts within 4 min, "
         "92 % reached, strong appeal to postpone trips / work from home.",
         app_delay=4, Imax=0.92, tau=10, p_cancel=0.38, p_modeshift=0.20, seed=14),
    scen("S5 Slow / fragmented information", "S5", "Unclear messages, apps update after 25 min, "
         "only 55 % of drivers ever informed.", app_delay=25, Imax=0.55, tau=45,
         p_cancel=0.15, p_modeshift=0.10, seed=15),
    scen("S6 Secondary collisions", "S6", "Rear-end collision on E18 Skøyen–Filipstad 08:40 "
         "(60 min, −60 % cap) and on Ring 2 Ullevål–Alexander Kiellands plass 09:30 (45 min, −50 %).",
         incidents=[(("SKO", "FIL"), 35, 60, 0.4), (("FIL", "SKO"), 35, 60, 0.6),
                    (("ULL", "GRU"), 85, 45, 0.5), (("GRU", "ULL"), 85, 45, 0.5)], seed=16),
    scen("S7 Prolonged tunnel evacuation", "S7", "Vehicles inside tunnels are not allowed out "
         "(ventilation/lighting failure). Occupants evacuated on foot; stranded cars cleared "
         "after reopening (+30–60 min before full inflow).", halt_all=True, evac_on_foot=(25, 70),
         clear_delay=(30, 60), seed=17),
    scen("S8 Active traffic management", "S8", "Police at key junctions and adaptive signal plans "
         "from 08:35 (+12 % arterial capacity), inflow metering on E18/E6/Rv4 entries, good info.",
         atm_boost=0.12, atm_from=30, metering=0.30, app_delay=6, Imax=0.85, tau=15,
         p_cancel=0.30, seed=18),
    scen("S9 High-demand day", "S9", "Demand +8 % (e.g. school start, event, Monday after holiday), "
         "otherwise as reference.", demand=1.08, seed=19),
    scen("S10 Compound worst case", "S10", "Snow + slow information + secondary collision + "
         "vehicles held in tunnels for the whole closure.",
         cap=0.80, speed=0.75, p_modeshift=0.10, ev_factor=0.85, app_delay=25, Imax=0.55,
         tau=45, p_cancel=0.15, halt_all=True, evac_on_foot=(35, 90), clear_delay=(30, 60),
         incidents=[(("SKO", "FIL"), 35, 60, 0.4), (("FIL", "SKO"), 35, 60, 0.6)], seed=20),
]


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
class Sim:
    def __init__(self, p, closure=True, scale=58000, baseline_tt=None):
        self.p = p
        self.closure = closure
        self.rng = random.Random(p["seed"] + (0 if closure else 1000))
        self.links = build_links()
        self.out_links = defaultdict(list)
        self.in_links = defaultdict(list)
        for l in self.links:
            self.out_links[l.a].append(l.id)
            self.in_links[l.b].append(l.id)
            l.cap_factor = p["cap"]
        self.ff = {l.id: l.length / (l.ff_kmh * p["speed"]) * 60 for l in self.links}
        self.od, _ = build_od(self.links, self.out_links, scale * p["demand"])
        # per-OD demand noise (day-to-day variation)
        self.od = {k: v * self.rng.uniform(0.93, 1.07) * OD_FACTORS.get(f"{k[0]}|{k[1]}", 1.0)
                   for k, v in self.od.items()}
        self.acc = defaultdict(float)
        self.origin_q = defaultdict(deque)
        self.baseline_tt = baseline_tt
        self.nv = 3  # route-choice variants
        # habitual trees (free flow * 1.25, unaware of closures)
        hab_cost = {l.id: self.ff[l.id] * 1.25 for l in self.links}
        self.hab = {}
        for d in net.ZONES:
            self.hab[d] = []
            for v in range(self.nv):
                c = {k: x * self.rng.uniform(0.9, 1.1) for k, x in hab_cost.items()}
                self.hab[d].append(tree_to(d, self.links, self.in_links, c)[1])
        self.smooth_cost = {l.id: self.ff[l.id] for l in self.links}
        self.cur = None
        # scenario state
        self.tunnel_links = [l for l in self.links if l.tunnel]
        self.release = {}
        self.reopen = {}
        self.evac = {}
        tunnels = sorted({l.tunnel for l in self.tunnel_links})
        for tn in tunnels:
            if p["halt_all"]:
                self.release[tn] = None
                self.evac[tn] = self.rng.uniform(*p["evac_on_foot"])
            else:
                self.release[tn] = T_CLOSE + self.rng.uniform(*p["hold"])
            self.reopen[tn] = T_REOPEN + self.rng.uniform(*p["clear_delay"])
        # bookkeeping
        self.trips = defaultdict(lambda: [0.0, 0.0])   # (o,d,bin) -> [veh, sum_tt]
        self.cancelled = 0.0
        self.tun_od = defaultdict(float)
        self.t_now = 0
        self.abandoned = 0.0
        self.postponed = []        # (time, o, d, n)
        self.modeshift = 0.0
        self.modeshift_by_hour = defaultdict(float)
        self.ts = defaultdict(list)
        self.link_tt_hist = np.zeros((len(self.links), T_END + 1))
        self.occ_hist = {}
        self.area_hist = []
        self.ev_hist = []
        self.trapped = {}
        self.trapped_time = {}
        self.trapped_rem = {}
        self.delay_vh = 0.0
        self.unfinished = 0.0
        self.road_area = {}

    # -- information share among drivers at time t -------------------------
    def informed_share(self, t):
        p = self.p
        if not self.closure or t < T_CLOSE + p["app_delay"]:
            return p["I0"]
        x = t - T_CLOSE - p["app_delay"]
        return p["I0"] + (p["Imax"] - p["I0"]) * (1 - math.exp(-x / p["tau"]))

    def closure_known(self, t):
        return self.closure and T_CLOSE + self.p["app_delay"] <= t

    def tunnel_closed_in(self, l, t):
        return self.closure and l.tunnel and T_CLOSE <= t < self.reopen[l.tunnel]

    # -- link travel-time estimate ---------------------------------------------
    def link_tt(self, l):
        rate = max(sum(l.out_hist) / len(l.out_hist), 0.05 * l.cap_h / 60)
        return self.ff[l.id] + l.queued / rate

    def update_trees(self, t):
        known = self.closure_known(t)
        cost = {}
        for l in self.links:
            c = 0.5 * self.smooth_cost[l.id] + 0.5 * self.link_tt(l)
            self.smooth_cost[l.id] = c
            if l.occ > 0.92 * l.storage:
                c += 5.0
            if known and self.tunnel_closed_in(l, t):
                cost[l.id] = None
            else:
                cost[l.id] = c
        self.cur = {}
        for d in net.ZONES:
            self.cur[d] = []
            for v in range(self.nv):
                c = {k: (x * self.rng.uniform(0.85, 1.15) if x is not None else None)
                     for k, x in cost.items()}
                self.cur[d].append(tree_to(d, self.links, self.in_links, c)[1])

    def next_link(self, pk, node, t, variant_override=None):
        """Choose next link for packet at node. pk = [n, o, d, dep, u, var]."""
        d = pk[2]
        var = pk[5] if variant_override is None else variant_override
        informed = pk[4] < self.informed_share(t)
        tree = self.cur[d][var] if informed else self.hab[d][var]
        lid = tree.get(node)
        if lid is None:
            lid = self.cur[d][var].get(node)
        if lid is not None and self.tunnel_closed_in(self.links[lid], t):
            # driver reaches closed portal / VMS -> becomes informed and re-routes
            pk[4] = -1.0
            lid = self.cur[d][var].get(node)
            if lid is not None and self.tunnel_closed_in(self.links[lid], t):
                # apps not yet updated: pick best open alternative out of node
                best, bc = None, 1e18
                for cand in self.out_links[node]:
                    L = self.links[cand]
                    if self.tunnel_closed_in(L, t):
                        continue
                    c = self.smooth_cost[cand] + self.rng.uniform(0, 2)
                    if c < bc:
                        best, bc = cand, c
                lid = best
        return lid

    # -- main loop -------------------------------------------------------------
    def run(self):
        p = self.p
        links = self.links
        areas = sorted({a for (_, _, _, a) in net.NODES.values()})
        for l in links:
            self.road_area[l.id] = net.NODES[l.a][3]
        inc = []
        for (ab, ts, dur, f) in p["incidents"]:
            for l in links:
                if (l.a, l.b) == ab and not l.tunnel:
                    inc.append((l, ts + T_CLOSE - 0, dur, f))
        for t in range(T_END + 1):
            # ---- scenario events ----
            if self.closure and t == T_CLOSE:
                for l in self.tunnel_links:
                    self.trapped[l.tunnel] = self.trapped.get(l.tunnel, 0) + l.occ
                    self.trapped_rem[l.id] = l.occ
                    self.trapped_time.setdefault(l.tunnel, t)
            for l in links:
                f = p["cap"]
                if self.closure and T_CLOSE + p["atm_from"] <= t < T_REOPEN + 60 and not l.tunnel:
                    if l.lanes <= 2 and l.ff_kmh <= 60:
                        f *= 1 + p["atm_boost"]
                for (il, ts, dur, ff) in inc:
                    if self.closure and il is l and ts <= t < ts + dur:
                        f *= ff
                l.cap_factor = f
                l.out_factor = 1.0
                if self.closure and l.tunnel and T_CLOSE <= t:
                    tn = l.tunnel
                    rel = self.release[tn]
                    if rel is None:
                        # halted until clearance after reopening
                        if t < self.reopen[tn]:
                            l.out_factor = 0.0
                        elif t < self.reopen[tn] + 20:
                            l.out_factor = 0.3
                    elif t < rel:
                        l.out_factor = 0.0
                    elif t < self.reopen[tn]:
                        l.out_factor = p["escort_factor"]
            self.t_now = t
            if t % 5 == 0:
                self.update_trees(t)
            # ---- demand generation ----
            self.generate(t)
            # ---- origin queues: travellers stuck >40 min before even reaching the
            # main road gradually give up (go home, park and ride, work remotely)
            if t % 5 == 0:
                for oq in self.origin_q.values():
                    for pk in oq:
                        if t - pk[3] > 40:
                            g = pk[0] * 0.08
                            pk[0] -= g
                            self.abandoned += g
            # ---- origin queues inject ----
            for node, oq in self.origin_q.items():
                held = []
                inj_budget = 400.0
                while oq and inj_budget > 0:
                    pk = oq.popleft()
                    lid = self.next_link(pk, node, t)
                    if lid is None:
                        held.append(pk)
                        continue
                    L = links[lid]
                    if self.tunnel_closed_in(L, t):
                        held.append(pk)
                        continue
                    meter = 1.0
                    if self.closure and p["metering"] and node in ("ASK", "ROM", "FOL", "NIT", "E16", "ASV") \
                            and T_CLOSE + 20 <= t < T_REOPEN:
                        meter = 1 - p["metering"]
                    space = (L.storage * 0.95 - L.occ) * meter
                    if space <= 0.5:
                        held.append(pk)
                        break
                    n = min(pk[0], space, inj_budget)
                    if n < pk[0]:
                        rest = list(pk)
                        rest[0] = pk[0] - n
                        held.append(rest)
                    mv = list(pk)
                    mv[0] = n
                    L.q.append([mv, t + self.ff[lid]])
                    L.occ += n
                    inj_budget -= n
                for pk in reversed(held):
                    oq.appendleft(pk)
            # ---- link discharge ----
            order = list(range(len(links)))
            self.rng.shuffle(order)
            for i in order:
                self.discharge(links[i], t)
            # ---- statistics ----
            self.record(t, areas)
        # unfinished vehicles at end of window
        for l in links:
            for (pk, _) in l.q:
                self.unfinished += pk[0]
                self.add_trip(pk, T_END)
        for oq in self.origin_q.values():
            for pk in oq:
                self.unfinished += pk[0]
                self.add_trip(pk, T_END)
        return self

    def generate(self, t):
        am, md, pm = profile(t)
        p = self.p
        I = self.informed_share(t)
        known = self.closure_known(t) and t < T_REOPEN
        for (o, d), v in self.od.items():
            rate = (v * am + v * md) / 60.0
            rev = self.od.get((d, o), 0) * (pm + md) / 60.0
            self.acc[(o, d)] += rate + rev
            if self.acc[(o, d)] >= PACKET_MIN:
                n = self.acc[(o, d)]
                self.acc[(o, d)] = 0.0
                u = self.rng.random()
                if known and u < I:
                    # informed traveller before departure
                    c = n * p["p_cancel"]
                    ms = 0.0
                    if o in net.RAIL_SERVED and d in net.RAIL_SERVED:
                        ms = n * p["p_modeshift"]
                    self.cancelled += c * (1 - p["p_return"])
                    if c * p["p_return"] > 0:
                        tr = self.reopen_time_guess() + self.rng.uniform(0, 100)
                        self.postponed.append((tr, o, d, c * p["p_return"]))
                    self.modeshift += ms * CAR_OCC
                    self.modeshift_by_hour[(t + T_START_CLOCK) // 60] += ms * CAR_OCC
                    n -= c + ms
                if n > 0:
                    self.origin_q[o].append([n, o, d, t, u, self.rng.randrange(self.nv)])
        # postponed trips re-entering after reopening
        if self.postponed:
            keep = []
            for (tr, o, d, n) in self.postponed:
                if tr <= t:
                    self.origin_q[o].append([n, o, d, t, 0.0, self.rng.randrange(self.nv)])
                else:
                    keep.append((tr, o, d, n))
            self.postponed = keep

    def reopen_time_guess(self):
        return T_REOPEN

    def add_trip(self, pk, t_arr):
        n, o, d, dep = pk[0], pk[1], pk[2], pk[3]
        b = int(dep // 15)
        rec = self.trips[(o, d, b)]
        rec[0] += n
        rec[1] += n * (t_arr - dep)

    def discharge(self, l, t):
        cap_min = l.cap_h / 60.0 * l.cap_factor * l.out_factor
        l.budget = min(l.budget + cap_min, cap_min * 1.5 + 0.5)
        moved = 0.0
        held = []
        scans = 0
        max_scan = l.lanes + 1
        while l.q and l.budget > 1e-6 and scans < max_scan:
            pk, ready = l.q[0]
            if ready > t:
                break
            if l.b == pk[2]:
                n = min(pk[0], l.budget)
                part = list(pk)
                part[0] = n
                self.add_trip(part, t)
                self.move_done(l, pk, n)
                moved += n
                continue
            lid = self.next_link(pk, l.b, t)
            if lid is None or lid == l.id ^ 1 and len(self.out_links[l.b]) > 1 and False:
                lid = None
            ok = False
            if lid is not None:
                L = self.links[lid]
                space = L.storage - L.occ
                if self.tunnel_closed_in(L, t):
                    space = 0
                if space <= 0.5 and t - ready > 3 and pk[4] < self.informed_share(t):
                    # informed driver stuck: try an alternative route variant
                    for v in range(self.nv):
                        alt = self.next_link(pk, l.b, t, v)
                        if alt is not None and alt != lid:
                            A = self.links[alt]
                            if not self.tunnel_closed_in(A, t) and A.storage - A.occ > 0.5:
                                lid, L, space = alt, A, A.storage - A.occ
                                break
                if space > 0.5:
                    n = min(pk[0], l.budget, space)
                    mv = list(pk)
                    mv[0] = n
                    L.q.append([mv, t + self.ff[lid]])
                    L.occ += n
                    self.move_done(l, pk, n)
                    moved += n
                    ok = True
            if not ok:
                held.append(l.q.popleft())
                scans += 1
        for item in reversed(held):
            l.q.appendleft(item)
        l.out_hist.append(moved)
        l.flow.append(moved)
        # queued vehicles (ready to leave but waiting)
        qd = 0.0
        for (pk, ready) in l.q:
            if ready <= t:
                qd += pk[0]
            else:
                break
        l.queued = qd
        if l.out_factor == 0.0 and l.tunnel:
            l.queued = l.occ

    def move_done(self, l, pk, n):
        if l.tunnel and 60 <= self.t_now < 120:
            self.tun_od[(l.tunnel, pk[1], pk[2])] += n
        l.budget -= n
        l.occ -= n
        if n >= pk[0] - 1e-9:
            l.q.popleft()
        else:
            pk[0] -= n

    # -- emergency services ----------------------------------------------------
    def ev_cost(self, t):
        cost = {}
        for l in self.links:
            if self.tunnel_closed_in(l, t):
                cost[l.id] = None
                continue
            rho = min(l.occ / l.storage, 1.0)
            v = l.ff_kmh * self.p["speed"] * 1.15 * self.p["ev_factor"]
            if rho > 0.2:
                v *= max(0.06, (1 - (rho - 0.2) / 0.8) ** 1.5)
            v = max(v, 6.0)
            cost[l.id] = l.length / v * 60
        return cost

    def ev_metrics(self, t, cost, committed):
        res_tot = sum(z[0] for z in net.ZONES.values())
        amb = dist_from(list(net.AMBULANCE_BASES), self.links, self.out_links, cost, 2.0)
        fire_src = [s for s in net.FIRE_STATIONS if s not in committed]
        fire = dist_from(fire_src, self.links, self.out_links, cost, 1.5)
        # local-street congestion: vehicles unable to enter the main network
        # queue on local streets around the zone and slow the last mile
        for z in net.ZONES:
            q = sum(pk[0] for pk in self.origin_q.get(z, ()))
            extra = min(8.0, q / 150.0) / self.p["ev_factor"]
            if z in amb:
                amb[z] += extra
            if z in fire:
                fire[z] += extra
        hosp = {}
        for z in net.ZONES:
            hosp[z] = min(dist_from([z], self.links, self.out_links, cost).get(h, 999)
                          for h in net.HOSPITALS) if t % 30 == 0 else None
        a12 = sum(net.ZONES[z][0] for z in net.ZONES if amb.get(z, 999) <= 12) / res_tot
        f10 = sum(net.ZONES[z][0] for z in net.ZONES if fire.get(z, 999) <= 10) / res_tot
        amb_mean = sum(net.ZONES[z][0] * min(amb.get(z, 90), 90) for z in net.ZONES) / res_tot
        worst = max(net.ZONES, key=lambda z: amb.get(z, 999))
        return dict(t=t, amb12=a12, fire10=f10, amb_mean=amb_mean,
                    worst=worst, worst_t=min(amb.get(worst, 999), 999),
                    amb=dict(amb), hosp=hosp)

    def record(self, t, areas):
        links = self.links
        in_net = sum(l.occ for l in links)
        in_orig = sum(pk[0] for oq in self.origin_q.values() for pk in oq)
        jam = [l for l in links if l.occ > 0.85 * l.storage and not (l.tunnel and l.out_factor == 0)]
        grid = [l for l in jam if sum(l.out_hist) < 0.15 * 5 * l.cap_h / 60]
        self.ts["t"].append(t)
        self.ts["in_net"].append(in_net)
        self.ts["in_orig"].append(in_orig)
        self.ts["jam_links"].append(len(jam))
        self.ts["jam_lane_km"].append(sum(l.length * l.lanes for l in jam))
        self.ts["grid_links"].append(len(grid))
        self.ts["queue_km"].append(sum(min(l.queued / (JAM_DENSITY * l.lanes), l.length)
                                       for l in links))
        self.delay_vh += (in_net + in_orig) / 60.0
        # vehicles stuck in the Oslo basin: on jammed basin links + waiting on
        # basin local streets (origin queues)
        b_jam = sum(l.occ for l in jam if self.road_area[l.id] in BASIN)
        b_orig = sum(pk[0] for z, oq in self.origin_q.items() if net.NODES[z][3] in BASIN for pk in oq)
        self.ts["basin_stuck"].append(b_jam + b_orig)
        self.ts["basin_grid"].append(sum(1 for l in grid if self.road_area[l.id] in BASIN))
        for l in links:
            self.link_tt_hist[l.id, t] = self.link_tt(l)
        if t % 5 == 0:
            self.occ_hist[t] = np.array([l.occ / l.storage for l in links])
            row = {}
            for a in areas:
                ls = [l for l in links if self.road_area[l.id] == a]
                tot = sum(l.length * l.lanes for l in ls)
                j = sum(l.length * l.lanes for l in ls if l.occ > 0.6 * l.storage
                        and not (l.tunnel and l.out_factor == 0))
                row[a] = j / tot if tot else 0
            self.area_hist.append((t, row))
        if t % 10 == 0 and T_CLOSE - 20 <= t:
            committed = set()
            if self.closure and T_CLOSE <= t:
                # fire stations committed to tunnel evacuation / traffic control
                for tn, ev in self.evac.items():
                    if t < T_CLOSE + ev + 30:
                        committed.add(self.nearest_fire_to_tunnel(tn))
                if not self.evac and t < T_CLOSE + 45:
                    for tn in ("Festningstunnelen (E18)", "Bjørvikatunnelen (E18)",
                               "Ekebergtunnelen (E18/Rv190)"):
                        committed.add(self.nearest_fire_to_tunnel(tn))
            self.ev_hist.append(self.ev_metrics(t, self.ev_cost(t), committed))
        if self.closure and t >= T_CLOSE:
            # remaining trapped vehicles per tunnel: inflow is zero while closed,
            # and FIFO means the trapped cohort leaves first after reopening
            for l in self.tunnel_links:
                rem = self.trapped_rem.get(l.id)
                if rem is None:
                    continue
                rem = max(0.0, rem - l.flow[-1])
                self.trapped_rem[l.id] = rem
                if rem > 0.5:
                    self.trapped_time[l.tunnel] = t + 1
            tot = sum(self.trapped_rem.values())
            self.ts["trapped"].append(tot)

    def nearest_fire_to_tunnel(self, tn):
        l = next(x for x in self.tunnel_links if x.tunnel == tn)
        ff = {x.id: self.ff[x.id] for x in self.links}
        d = dist_from([l.a], self.links, self.out_links, ff)
        return min(net.FIRE_STATIONS, key=lambda s: d.get(s, 999))

    # -- public transport --------------------------------------------------------
    def corridor_time(self, nodes, t_dep, bus=True, mixed_share=1.0):
        """Travel time along node sequence departing at t_dep; reroute around closures."""
        t = float(t_dep)
        detour = False
        for a, b in zip(nodes[:-1], nodes[1:]):
            ti = min(int(t), T_END)
            cands = [lid for lid in self.out_links[a] if self.links[lid].b == b]
            # prefer the main road; skip closed tunnels
            best = None
            for lid in sorted(cands, key=lambda x: -self.links[x].cap_h):
                if not self.tunnel_closed_in(self.links[lid], ti):
                    best = lid
                    break
            if best is None:
                cost = {}
                for l in self.links:
                    if self.tunnel_closed_in(l, ti):
                        cost[l.id] = None
                    else:
                        cost[l.id] = self.link_tt_hist[l.id, ti]
                dist, nxt = tree_to(b, self.links, self.in_links, cost)
                node = a
                while node != b and node in nxt:
                    lid = nxt[node]
                    t += self.seg_time(lid, min(int(t), T_END), bus, mixed_share)
                    node = self.links[lid].b
                detour = True
            else:
                t += self.seg_time(best, ti, bus, mixed_share)
            t += 0.5  # stop dwell
        return t - t_dep, detour

    def seg_time(self, lid, ti, bus, mixed_share):
        l = self.links[lid]
        ff = self.ff[lid]
        q = max(self.link_tt_hist[lid, ti] - ff, 0)
        if bus and l.ff_kmh <= 60:
            q *= 0.6  # bus lanes / priority on urban arterials
        return ff + q * mixed_share


# ---------------------------------------------------------------------------
# Helpers for post-processing
# ---------------------------------------------------------------------------
def trip_tt(sim, o, d, b):
    v, s = sim.trips.get((o, d, b), (0, 0))
    return s / v if v > 0 else None


def total_delay(sim, base):
    """Extra vehicle-hours vs baseline for trips departing in the same 15-min bin."""
    extra = 0.0
    for (o, d, b), (v, s) in sim.trips.items():
        bt = trip_tt(base, o, d, b)
        if bt is None or v <= 0:
            continue
        extra += max(s / v - bt, 0) * v
    return extra / 60.0
