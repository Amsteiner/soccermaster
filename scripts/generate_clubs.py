#!/usr/bin/env python3
"""
Generiert vereine.csv mit deutschen Vereinen für Bundesliga, 2. Bundesliga und Oberliga.
Internationale Vereine gehören in internationale_vereine.csv.

Struktur:
  name,liga_start,staerke_min,staerke_max

- liga_start: Pool (1=BL1-Pool, 2=BL2-Pool, 3=Oberliga-Pool)
- staerke_min/max: Stärkewerte

Beim Spielstart werden aus jedem Pool zufällig 18 Teams gezogen.
"""

import csv
import os

# ─────────────────────────────────────────────────────────────────────────────
# Pool 1: Teams die zwischen 1975–1999 in der 1. Bundesliga gespielt haben
# Format: (name, liga_start, staerke_min, staerke_max)
# ─────────────────────────────────────────────────────────────────────────────
BUNDESLIGA_POOL = [
    # Dauergäste BL1
    ("FC Bayern München",          1, 78, 100),
    ("Hamburger SV",               1, 68, 95),
    ("Borussia Mönchengladbach",   1, 62, 90),
    ("VfB Stuttgart",              1, 58, 85),
    ("SV Werder Bremen",           1, 55, 85),
    ("Borussia Dortmund",          1, 52, 85),
    ("1. FC Köln",                 1, 50, 82),
    ("Bayer 04 Leverkusen",        1, 48, 80),
    ("Eintracht Frankfurt",        1, 45, 78),
    ("1. FC Kaiserslautern",       1, 45, 78),
    ("VfL Bochum",                 1, 42, 75),
    ("1. FC Nürnberg",             1, 40, 75),
    ("FC Schalke 04",              1, 45, 78),
    ("Hertha BSC",                 1, 42, 75),
    ("Arminia Bielefeld",          1, 40, 72),
    ("Fortuna Düsseldorf",         1, 38, 70),
    ("MSV Duisburg",               1, 38, 70),

    # Zeitweise in BL1 (mehrere Saisons)
    ("Eintracht Braunschweig",     1, 35, 68),
    ("Kickers Offenbach",          1, 35, 65),
    ("SV Waldhof Mannheim",        1, 35, 65),
    ("Bayer 05 Uerdingen",         1, 35, 68),
    ("Rot-Weiss Essen",            1, 33, 65),
    ("Fortuna Köln",               1, 33, 65),
    ("FC 08 Homburg",              1, 33, 65),
    ("SG Wattenscheid 09",         1, 30, 62),
    ("Karlsruher SC",              1, 38, 70),
    ("SC Freiburg",                1, 35, 65),
    ("FC Hansa Rostock",           1, 35, 65),
    ("Hannover 96",                1, 35, 68),
    ("Blau-Weiß 90 Berlin",        1, 28, 58),
]

# ─────────────────────────────────────────────────────────────────────────────
# Pool 2: Teams die zwischen 1975–1999 in der 2. Bundesliga gespielt haben
# (Keine Duplikate zu Liga-1-Pool)
# ─────────────────────────────────────────────────────────────────────────────
BUNDESLIGA2_POOL = [
    # Klassische BL2-Clubs
    ("SV Darmstadt 98",            2, 32, 62),
    ("1. FC Saarbrücken",          2, 32, 62),
    ("SSV Ulm 1846",               2, 28, 58),
    ("Alemannia Aachen",           2, 28, 58),
    ("Stuttgarter Kickers",        2, 25, 55),
    ("FC St. Pauli",               2, 25, 55),
    ("Wuppertaler SV",             2, 25, 55),
    ("Holstein Kiel",              2, 25, 55),
    ("KSV Hessen Kassel",          2, 22, 50),
    ("SG Union Solingen",          2, 20, 48),
    ("SC Fortuna Köln",            2, 22, 52),
    ("Rot-Weiß Oberhausen",        2, 20, 48),
    ("VfL Osnabrück",              2, 25, 55),
    ("Preußen Münster",            2, 25, 55),
    ("Tennis Borussia Berlin",     2, 25, 55),
    ("FK Pirmasens",               2, 18, 45),

    # Aufsteiger der 80er/90er
    ("TSV 1860 München",           2, 30, 62),
    ("SpVgg Greuther Fürth",       2, 25, 55),
    ("FC Augsburg",                2, 25, 55),
    ("VfL Wolfsburg",              2, 28, 58),
    ("FC Energie Cottbus",         2, 25, 55),

    # Ostdeutsche Clubs nach 1990
    ("Dynamo Dresden",             2, 28, 60),
    ("1. FC Union Berlin",         2, 22, 52),
    ("FC Erzgebirge Aue",          2, 20, 48),
    ("1. FC Magdeburg",            2, 25, 55),
    ("Hallescher FC",              2, 18, 45),

    # Weitere BL2-Vertreter
    ("Wormatia Worms",             2, 15, 42),
    ("AS Koblenz",                 2, 18, 45),
    ("SV Meppen",                  2, 18, 45),
    ("FC Remscheid",               2, 15, 42),
]

# ─────────────────────────────────────────────────────────────────────────────
# Pool 3: Oberliga / 3. Liga – Pool für DFB-Pokal und Aufsteiger in BL2
# ─────────────────────────────────────────────────────────────────────────────
OBERLIGA_POOL = [
    # Traditionsvereine Westdeutschland
    ("Rot-Weiß Frankfurt",         3, 10, 38),
    ("Kickers Würzburg",           3, 15, 42),
    ("SpVgg Bayreuth",             3, 12, 38),
    ("VfB Oldenburg",              3, 10, 35),
    ("SV Elversberg",              3, 15, 42),
    ("FC Gütersloh",               3, 12, 38),
    ("SV Rödinghausen",            3, 10, 35),
    ("Westfalia Herne",            3, 12, 38),
    ("SC Victoria Hamburg",        3, 10, 35),
    ("Altona 93",                  3, 10, 35),
    ("VfB Lübeck",                 3, 15, 42),
    ("SC Fortuna Hamburg",         3, 10, 35),
    ("SV Wilhelmshaven",           3, 10, 35),
    ("Kickers Emden",              3, 12, 38),
    ("FC Teutonia Ottensen",       3, 10, 35),
    ("SpVgg Erkenschwick",         3, 12, 40),
    ("Bonner SC 01",               3, 10, 38),
    ("Rot-Weiss Ahlen",            3, 10, 38),
    ("SSV Reutlingen 05",          3, 15, 42),
    ("Sportfreunde Siegen",        3, 12, 38),
    ("TuRU Düsseldorf",            3, 10, 35),
    ("FC 08 Villingen",            3, 12, 38),
    ("Bahlinger SC",               3, 10, 35),
    ("FC Villingen",               3, 12, 38),
    ("SV Wehen Wiesbaden",         3, 15, 42),
    ("Eintracht Trier",            3, 15, 42),
    ("TuS Koblenz",                3, 15, 42),
    ("Hamborn 07",                 3, 10, 35),
    ("SC Viktoria Köln",           3, 12, 38),

    # Ostdeutschland nach 1990
    ("BFC Dynamo Berlin",          3, 25, 55),
    ("Carl Zeiss Jena",            3, 18, 45),
    ("1. FC Heidenheim",           3, 15, 42),
    ("SV Sandhausen",              3, 15, 42),
    ("Rot-Weiß Erfurt",            3, 15, 42),
    ("FC Sachsen Leipzig",         3, 15, 42),
    ("Chemnitzer FC",              3, 18, 45),
    ("VfB Zittau",                 3, 10, 35),
    ("Stahl Brandenburg",          3, 10, 35),
    ("BSG Chemie Leipzig",         3, 12, 38),
    ("SC Eisenhüttenstadt",        3, 10, 35),
    ("Roter Stern Leipzig",        3, 10, 35),
    ("VfR Aalen",                  3, 15, 42),
    ("SC Paderborn",               3, 15, 42),
    ("SV Babelsberg 03",           3, 12, 38),
    ("FC Ingolstadt",              3, 15, 42),
]


def generate_clubs_csv(output_path: str = None):
    """Generiert die komplette vereine.csv"""

    # Pfad relativ zu diesem Script oder überschrieben
    if output_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(script_dir, "..", "data", "vereine.csv")

    all_clubs = []
    seen_names = set()

    def add_pool(pool):
        for name, liga_start, staerke_min, staerke_max in pool:
            if name in seen_names:
                print(f"  WARNUNG: Duplikat übersprungen: {name}")
                continue
            seen_names.add(name)
            all_clubs.append((name, liga_start, staerke_min, staerke_max))

    add_pool(BUNDESLIGA_POOL)
    add_pool(BUNDESLIGA2_POOL)
    add_pool(OBERLIGA_POOL)
    # Internationale Vereine gehören in internationale_vereine.csv, nicht hierher

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "liga_start", "staerke_min", "staerke_max"])
        for club in all_clubs:
            writer.writerow(club)

    # Statistik
    pool_counts = {}
    for _, liga_start, *_ in all_clubs:
        pool_counts[liga_start] = pool_counts.get(liga_start, 0) + 1

    print(f"vereine.csv generiert: {output_path}")
    print(f"  BL1-Pool   (liga_start=1): {pool_counts.get(1, 0)} Vereine")
    print(f"  BL2-Pool   (liga_start=2): {pool_counts.get(2, 0)} Vereine")
    print(f"  OL-Pool    (liga_start=3): {pool_counts.get(3, 0)} Vereine")
    print(f"  Gesamt: {len(all_clubs)} Vereine")


if __name__ == "__main__":
    generate_clubs_csv()
