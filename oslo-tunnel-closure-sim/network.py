"""
Simplified strategic road network for the Oslo metropolitan area.

All numbers (capacities, lengths, zone sizes, AADT-like volumes) are rounded
planning estimates intended for scenario analysis, NOT validated data.
For decision-grade work, replace with NVDB / Statens vegvesen traffic counts,
the regional transport model (RTM/Tramod) and Ruter ridership data.
"""

# ---------------------------------------------------------------------------
# Nodes: id -> (name, lat, lon, area)
# "area" is used to report how congestion spreads geographically.
# ---------------------------------------------------------------------------
NODES = {
    "SEN": ("Sentrum / Jernbanetorget", 59.911, 10.750, "Sentrum"),
    "BJV": ("Bjørvika", 59.906, 10.758, "Sentrum"),
    "VAT": ("Vaterland / Ring 1 NE", 59.915, 10.758, "Sentrum"),
    "FIL": ("Filipstad / Vika", 59.910, 10.722, "Sentrum"),
    "FRO": ("Frogner / Solli", 59.917, 10.712, "Indre vest"),
    "MAJ": ("Majorstua", 59.929, 10.715, "Indre vest"),
    "SKO": ("Skøyen", 59.921, 10.680, "Ytre vest"),
    "SME": ("Smestad / Vinderen", 59.937, 10.690, "Ytre vest"),
    "ULN": ("Ullern / Granfoss", 59.926, 10.650, "Ytre vest"),
    "LYS": ("Lysaker / Fornebu", 59.913, 10.637, "Bærum"),
    "SAN": ("Sandvika (Bærum)", 59.890, 10.525, "Bærum"),
    "E16": ("Bærum nord / E16 (Ringerike)", 59.935, 10.470, "Bærum"),
    "ASK": ("Asker", 59.835, 10.435, "Asker"),
    "ULL": ("Ullevål", 59.940, 10.735, "Indre nord"),
    "TAS": ("Tåsen / Blindern", 59.951, 10.748, "Indre nord"),
    "STO": ("Storo / Nydalen", 59.946, 10.772, "Indre nord"),
    "SIN": ("Sinsen / Aker", 59.937, 10.782, "Indre nord"),
    "GRU": ("Grünerløkka / St. Hanshaugen", 59.927, 10.755, "Indre øst"),
    "TOY": ("Tøyen / Carl Berner", 59.922, 10.777, "Indre øst"),
    "ENS": ("Ensjø", 59.914, 10.787, "Indre øst"),
    "KVA": ("Kværnerdalen / Gamlebyen", 59.905, 10.775, "Indre øst"),
    "HEL": ("Helsfyr", 59.912, 10.802, "Indre øst"),
    "BRY": ("Bryn", 59.909, 10.822, "Ytre øst"),
    "OKE": ("Økern / Hasle", 59.929, 10.806, "Ytre øst"),
    "ALN": ("Alnabru", 59.932, 10.842, "Ytre øst"),
    "GRO": ("Grorud / Linderud", 59.958, 10.870, "Groruddalen"),
    "FUR": ("Furuset / Stovner", 59.941, 10.892, "Groruddalen"),
    "NIT": ("Nittedal (Rv4)", 60.010, 10.880, "Nittedal"),
    "LOR": ("Lørenskog / Ahus", 59.930, 10.960, "Romerike"),
    "ROM": ("Romerike / Gardermoen (E6)", 60.010, 11.010, "Romerike"),
    "SJU": ("Sydhavna / Sjursøya", 59.893, 10.765, "Søndre"),
    "RYE": ("Ryen", 59.896, 10.805, "Søndre"),
    "MAN": ("Manglerud / Østensjø", 59.898, 10.818, "Søndre"),
    "LJA": ("Nordstrand / Ljan", 59.865, 10.790, "Søndre"),
    "KLE": ("Mortensrud / Klemetsrud", 59.843, 10.835, "Søndre"),
    "FOL": ("Nordre Follo (Ski/Kolbotn)", 59.740, 10.835, "Follo"),
    "ASV": ("Ås / Vestby (E6 sør)", 59.665, 10.790, "Follo"),
}

# ---------------------------------------------------------------------------
# Links (undirected spec, expanded to both directions).
# (a, b, length_km, capacity_veh_per_h_per_direction, free_flow_kmh, lanes,
#  tunnel_name or None, road label)
# ---------------------------------------------------------------------------
LINKS = [
    # --- E18 west / Operatunnelen system -----------------------------------
    ("FIL", "BJV", 1.8, 5000, 70, 3, "Festningstunnelen (E18)", "E18"),
    ("BJV", "SJU", 1.1, 5400, 70, 3, "Bjørvikatunnelen (E18)", "E18"),
    ("SJU", "RYE", 1.6, 4000, 70, 2, "Ekebergtunnelen (E18/Rv190)", "E18"),
    ("RYE", "KVA", 1.3, 3600, 70, 2, "Svartdalstunnelen (E6/Rv190)", "E6"),
    ("KVA", "ENS", 0.8, 3600, 60, 2, "Vålerengatunnelen (E6)", "E6"),
    ("FIL", "SKO", 3.2, 4400, 70, 3, None, "E18"),
    ("SKO", "LYS", 2.6, 4400, 80, 3, None, "E18"),
    ("LYS", "SAN", 8.5, 5000, 80, 3, None, "E18"),
    ("SAN", "ASK", 10.0, 4400, 90, 3, None, "E18"),
    ("SAN", "E16", 6.0, 2200, 80, 2, "Bjørnegårdtunnelen (E16)", "E16"),
    # --- Ring 1 ---------------------------------------------------------------
    ("BJV", "VAT", 1.0, 2600, 50, 2, "Ibsentunnelen (Ring 1)", "Ring 1"),
    ("VAT", "FRO", 1.9, 2400, 50, 2, "Vaterland-/Hammersborgtunnelen (Ring 1)", "Ring 1"),
    ("VAT", "SEN", 0.5, 1400, 30, 1, None, "Sentrumsgater"),
    ("SEN", "BJV", 0.6, 1400, 30, 1, None, "Sentrumsgater"),
    ("SEN", "FRO", 1.8, 1100, 30, 1, None, "Sentrumsgater"),
    ("SEN", "FIL", 1.2, 1000, 30, 1, None, "Sentrumsgater"),
    ("VAT", "GRU", 1.2, 1400, 40, 1, None, "Sentrumsgater"),
    # --- Ring 2 and inner arterials ------------------------------------------
    ("FRO", "FIL", 1.4, 1800, 40, 2, None, "Ring 1/Drammensveien"),
    ("FRO", "MAJ", 1.5, 1600, 40, 2, None, "Ring 2"),
    ("FRO", "SKO", 3.0, 1600, 50, 2, None, "Drammensveien"),
    ("MAJ", "ULL", 1.6, 1800, 40, 2, None, "Ring 2"),
    ("ULL", "GRU", 1.9, 1800, 40, 2, None, "Ring 2"),
    ("GRU", "TOY", 1.3, 1800, 40, 2, None, "Ring 2"),
    ("TOY", "ENS", 1.0, 2000, 40, 2, None, "Ring 2"),
    ("ENS", "KVA", 1.2, 1300, 40, 1, None, "Strømsveien/Vålerenga"),
    ("KVA", "BJV", 1.6, 1600, 40, 2, None, "Ring 2/Gamlebyen"),
    ("BJV", "SJU", 2.0, 1500, 50, 1, None, "Mosseveien"),
    ("TOY", "VAT", 1.4, 1300, 40, 1, None, "Hovedgater øst"),
    ("ENS", "HEL", 1.2, 1800, 50, 2, None, "Strømsveien"),
    ("ENS", "OKE", 2.0, 3600, 70, 2, None, "E6 Ensjø–Økern"),
    ("KVA", "HEL", 1.9, 1200, 40, 1, None, "Hovedgater øst"),
    ("MAJ", "SME", 2.0, 1200, 40, 1, None, "Sørkedalsveien"),
    ("SIN", "GRU", 1.6, 1400, 40, 2, None, "Trondheimsveien"),
    ("STO", "GRU", 2.0, 1200, 40, 1, None, "Vogts gate/Maridalsveien"),
    ("OKE", "TOY", 2.0, 1400, 50, 2, None, "Økernveien"),
    # --- Ring 3 ----------------------------------------------------------------
    ("RYE", "MAN", 1.3, 4000, 70, 2, None, "Ring 3/E6"),
    ("MAN", "BRY", 1.4, 4000, 70, 2, "Brynstunnelen (Ring 3/E6)", "Ring 3"),
    ("BRY", "OKE", 2.0, 4000, 70, 2, None, "Ring 3"),
    ("OKE", "SIN", 1.2, 5000, 70, 3, "Lørentunnelen (Ring 3)", "Ring 3"),
    ("SIN", "STO", 1.4, 4000, 70, 2, None, "Ring 3"),
    ("STO", "TAS", 1.3, 3600, 70, 2, "Tåsentunnelen (Ring 3)", "Ring 3"),
    ("TAS", "ULL", 1.4, 4000, 70, 2, None, "Ring 3"),
    ("ULL", "SME", 2.4, 3600, 70, 2, "Smestadtunnelen (Ring 3)", "Ring 3"),
    ("SME", "ULN", 2.4, 3600, 70, 2, None, "Ring 3"),
    ("ULN", "LYS", 2.0, 3200, 70, 2, "Granfosstunnelen (Rv150)", "Rv150"),
    # --- Surface alternatives to tunnels --------------------------------------
    ("MAN", "HEL", 2.0, 1400, 50, 1, None, "Østensjøveien"),
    ("HEL", "BRY", 1.1, 1600, 50, 2, None, "Strømsveien"),
    ("RYE", "HEL", 1.8, 1200, 50, 1, None, "Ryenbergveien"),
    ("OKE", "SIN", 1.8, 1300, 40, 1, None, "Økern–Sinsen lokalveier"),
    ("STO", "TAS", 1.9, 900, 40, 1, None, "Sognsveien/Kapellveien"),
    ("ULL", "SME", 3.0, 1000, 40, 1, None, "Slemdalsveien/Vinderen"),
    ("SME", "SKO", 2.2, 1200, 50, 1, None, "Hoffsveien"),
    ("ULN", "SKO", 2.0, 1200, 50, 1, None, "Ullernchausseen"),
    ("ULN", "LYS", 2.6, 1000, 50, 1, None, "Mustads vei/lokalveier"),
    ("LYS", "SAN", 9.5, 1300, 60, 1, None, "Gamle Drammensvei/Rv160"),
    ("SAN", "ASK", 11.0, 1200, 60, 1, None, "Gamle E18/Slependen"),
    ("SAN", "E16", 7.0, 900, 60, 1, None, "Gamle E16"),
    # --- East / north-east -----------------------------------------------------
    ("BRY", "ALN", 2.5, 4400, 80, 3, None, "E6"),
    ("ALN", "FUR", 3.0, 4400, 80, 3, "Furusettunnelen (E6)", "E6"),
    ("ALN", "FUR", 3.4, 1400, 50, 1, None, "Tvetenveien/Furusetveien"),
    ("FUR", "LOR", 4.0, 4400, 80, 3, None, "E6"),
    ("LOR", "ROM", 20.0, 4400, 100, 3, None, "E6"),
    ("OKE", "ALN", 2.0, 2400, 60, 2, None, "Østre Aker vei"),
    ("ALN", "GRO", 3.0, 2000, 60, 2, None, "Rv163 Østre aksevei"),
    ("OKE", "GRO", 5.0, 2000, 60, 2, None, "Trondheimsveien (Rv4)"),
    ("GRO", "NIT", 8.0, 2200, 80, 2, "Gjelleråstunnelen (Rv4)", "Rv4"),
    ("GRO", "NIT", 9.0, 700, 50, 1, None, "Gamle Hadelandsvei"),
    ("GRO", "FUR", 3.0, 1200, 50, 1, None, "Lokalveier Groruddalen"),
    ("LOR", "ROM", 22.0, 1500, 70, 1, None, "Rv159/Rv120"),
    # --- South -----------------------------------------------------------------
    ("RYE", "KLE", 6.0, 5000, 80, 3, None, "E6/E18"),
    ("KLE", "FOL", 12.0, 5000, 100, 3, None, "E6/E18"),
    ("FOL", "ASV", 10.0, 3600, 100, 2, "Nordbytunnelen (E6)", "E6"),
    ("FOL", "ASV", 11.0, 800, 60, 1, None, "Fv152/lokalveier"),
    ("SJU", "LJA", 5.0, 1600, 50, 1, None, "Mosseveien"),
    ("LJA", "KLE", 4.0, 900, 50, 1, None, "Lokalveier Ljan–Hauketo"),
    ("MAN", "KLE", 5.5, 1000, 50, 1, None, "Enebakkveien"),
    ("LJA", "FOL", 14.0, 800, 60, 1, None, "Ljabruveien/Kolbotn"),
]

# ---------------------------------------------------------------------------
# Zones: id -> (residents_k, jobs_k, car_share_of_departures)
# ---------------------------------------------------------------------------
ZONES = {
    "SEN": (15, 120, 0.12), "BJV": (10, 30, 0.15), "FIL": (8, 40, 0.15),
    "FRO": (60, 30, 0.20), "MAJ": (40, 25, 0.20), "SKO": (20, 30, 0.30),
    "SME": (40, 10, 0.35), "ULN": (35, 10, 0.40), "LYS": (30, 50, 0.40),
    "SAN": (120, 50, 0.50), "E16": (40, 8, 0.60), "ASK": (95, 30, 0.50),
    "ULL": (30, 25, 0.25), "TAS": (30, 25, 0.25), "STO": (30, 30, 0.30),
    "SIN": (25, 10, 0.30), "GRU": (70, 20, 0.15), "TOY": (50, 15, 0.20),
    "ENS": (15, 15, 0.30), "KVA": (15, 8, 0.25), "HEL": (20, 25, 0.35),
    "BRY": (15, 15, 0.40), "OKE": (40, 25, 0.40), "ALN": (10, 20, 0.55),
    "GRO": (80, 15, 0.40), "FUR": (60, 10, 0.45), "NIT": (25, 5, 0.60),
    "LOR": (60, 25, 0.55), "ROM": (150, 60, 0.35), "SJU": (10, 12, 0.45),
    "RYE": (30, 10, 0.40), "MAN": (50, 10, 0.40), "LJA": (45, 5, 0.45),
    "KLE": (50, 8, 0.45), "FOL": (70, 20, 0.55), "ASV": (40, 15, 0.55),
}
# Parking / access restriction factor for car attraction (central = low)
ATTRACTION_FACTOR = {"SEN": 0.30, "BJV": 0.40, "FIL": 0.40, "FRO": 0.55,
                     "GRU": 0.55, "MAJ": 0.60, "TOY": 0.65}
# Freight / commercial generators (relative weights)
FREIGHT = {"ALN": 6, "SJU": 5, "ROM": 4, "FOL": 3, "LOR": 3, "OKE": 2,
           "SAN": 2, "BRY": 2, "KLE": 2, "SEN": 2, "LYS": 1, "GRO": 2}

# Zones with good rail/metro access towards Oslo centre (mode-shift potential)
RAIL_SERVED = {"ASK", "SAN", "LYS", "SKO", "FOL", "ASV", "ROM", "LOR", "GRO",
               "FUR", "MAN", "KLE", "LJA", "STO", "TAS", "ULL", "MAJ", "SME",
               "OKE", "HEL", "BRY", "TOY", "GRU", "SEN", "BJV", "SIN", "NIT"}

# ---------------------------------------------------------------------------
# Emergency facilities (approximate - aggregated to nearest network node)
# ---------------------------------------------------------------------------
FIRE_STATIONS = {"SEN": "Sentrum", "MAJ": "Vest/Majorstua", "SKO": "Skøyen",
                 "RYE": "Ryen", "STO": "Nord (Grefsen/Storo)", "BRY": "Øst (Bryn)",
                 "GRO": "Groruddalen", "KLE": "Søndre", "SAN": "Bærum",
                 "ASK": "Asker", "LOR": "Lørenskog", "FOL": "Follo"}
AMBULANCE_BASES = {"ULL": "Ullevål", "SEN": "Sentrum", "SKO": "Skøyen",
                   "BRY": "Bryn", "SIN": "Aker", "LOR": "Ahus",
                   "SAN": "Bærum", "KLE": "Søndre", "FOL": "Follo",
                   "ASK": "Asker", "GRO": "Groruddalen"}
HOSPITALS = {"ULL": "OUS Ullevål", "TAS": "OUS Rikshospitalet",
             "SIN": "Aker sykehus", "LOR": "Ahus", "SAN": "Bærum sykehus",
             "SME": "Diakonhjemmet", "BJV": "Lovisenberg/Sentrum (approx.)"}

# ---------------------------------------------------------------------------
# Bus corridors (illustrative, not exact Ruter line numbers)
# sequence of nodes, buses per hour per direction, avg passengers per bus
# ---------------------------------------------------------------------------
BUS_LINES = {
    "Asker/Bærum – Oslo bussterminal (E18)": (["ASK", "SAN", "LYS", "SKO", "FIL", "BJV"], 40, 45),
    "Follo – Oslo (E6/E18 via Ekeberg)": (["FOL", "KLE", "RYE", "SJU", "BJV"], 30, 40),
    "Romerike – Oslo (E6)": (["ROM", "LOR", "FUR", "ALN", "BRY", "HEL", "ENS", "TOY", "VAT"], 25, 40),
    "Flybuss Gardermoen – Oslo": (["ROM", "LOR", "FUR", "ALN", "OKE", "SIN", "GRU", "VAT"], 8, 25),
    "Nittedal – Oslo (Rv4)": (["NIT", "GRO", "OKE", "TOY", "VAT"], 10, 35),
    "Ring 3 tverrlinje (Lysaker–Helsfyr)": (["LYS", "ULN", "SME", "ULL", "TAS", "STO", "SIN", "OKE", "BRY", "HEL"], 12, 35),
    "Bærum nord – Lysaker (E16/E18)": (["E16", "SAN", "LYS"], 12, 35),
    "Indre by vest–øst (overflate)": (["MAJ", "FRO", "SEN", "VAT", "TOY"], 20, 40),
    "Søndre – Sentrum (Mosseveien)": (["KLE", "LJA", "SJU", "BJV"], 8, 35),
}
# Tram corridors (share of route in mixed traffic)
TRAM_LINES = {
    "Trikk Majorstua–Sentrum–Grünerløkka": (["MAJ", "FRO", "SEN", "VAT", "GRU"], 0.5),
    "Trikk Sentrum–Sinsen/Storo": (["SEN", "VAT", "GRU", "SIN", "STO"], 0.4),
    "Trikk Sentrum–Ljabru (Ekebergbanen)": (["SEN", "BJV", "SJU", "LJA"], 0.2),
    "Trikk Skøyen/Frogner–Sentrum": (["SKO", "FRO", "SEN"], 0.6),
}

# Representative car trips for travel-time reporting
KEY_TRIPS = [("ASK", "SEN"), ("SAN", "HEL"), ("FOL", "MAJ"), ("LOR", "LYS"),
             ("NIT", "SEN"), ("KLE", "SKO"), ("ROM", "FIL"), ("TAS", "RYE"),
             ("GRO", "ULL"), ("LJA", "SEN")]


# ---------------------------------------------------------------------------
# Published traffic counts used for calibration (ÅDT = annual average daily
# traffic, both directions). Collected via web search 19.11.2026 because the
# Statens vegvesen data API / NVDB were not reachable from this environment.
# quality: A = Statens vegvesen / official, B = official but old or indirect,
#          C = secondary source (e.g. Wikipedia, press)
# ---------------------------------------------------------------------------
COUNTS = {
    "Bjørvikatunnelen (E18)": (100000, "2023", "B",
        "Statens vegvesen press release 2023: Operatunnelen >100 000 vehicles/day",
        "https://www.vegvesen.no/om-oss/presse/aktuelt/2023/01/soker-elektroentreprenor-til-norges-mest-trafikkerte-tunneler/"),
    "Festningstunnelen (E18)": (80000, "2013", "B",
        "Statsforvalteren application document: ÅDT ca. 80 000 (2013)",
        "https://www.statsforvalteren.no/contentassets/18d5fa31e96c422ba60c3af34d920d42/soknad---festningstunnelen.pdf"),
    "Ekebergtunnelen (E18/Rv190)": (75000, "≈2017", "C",
        "Teknisk Ukeblad (rehabilitation project): highest level ca. 75 000",
        "https://www.tu.no/artikler/ekeberg-og-svartdalstunnelene-forbilledlig-tunnelprosjekt/469251"),
    "Lørentunnelen (Ring 3)": (68240, "2023", "C",
        "Norwegian Wikipedia: 68 240 (2023)",
        "https://wikiwand.com/no/articles/L%C3%B8rentunnelen"),
    "Tåsentunnelen (Ring 3)": (58000, "2018", "B",
        "Statnett planning note: avg. 58 000 vehicles/day on Ring 3 at Tåsentunnelen",
        "https://www.statnett.no/globalassets/her-er-vare-prosjekter/region-ost/nettplan-stor-oslo/sogn-ulven/arbeidsfaser-og-konsekvenser-for-3.-part.pdf"),
    "Vålerengatunnelen (E6)": (56000, "2018", "C",
        "Teknisk Ukeblad: ÅDT ca. 56 000 (2018)",
        "https://www.tu.no/artikler/na-blir-det-ko-i-oslo-ett-lop-av-valerengatunnelen-stenges-ett-ar/492359"),
    "Granfosstunnelen (Rv150)": (28500, "2024", "A",
        "Statens vegvesen byindeks Oslo 2024: 13 340 + 12 650 light vehicles (<5.6 m); +~8 % heavy",
        "https://vegvesen.no/globalassets/fag/trafikk/trafikkdata/byindeks_oslo_2018-2024-12.pdf"),
    "Vaterland-/Hammersborgtunnelen (Ring 1)": (17400, "2019", "A",
        "Statens vegvesen Ring 1 supplementary traffic analysis: Hammersborgtunnelen 17 400 (2019)",
        "https://www.vegvesen.no/globalassets/vegprosjekter/utbygging/tunneleroslo/vedlegg/ring-1---supplerende-trafikkanalyse-.pdf"),
}
# Weekday AM peak hour (both directions) as share of ÅDT. Typical Norwegian
# urban main roads: 7-10 % of ÅDT in the peak hour; weekday traffic ~8 % above
# ÅDT. Assumption: 0.085 * 1.08 ≈ 0.092.
PEAK_HOUR_SHARE = 0.092
