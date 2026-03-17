"""
Spielplan - Spielpläne und Pokal-Brackets für alle Wettbewerbe
"""

import random
from dataclasses import dataclass


@dataclass
class Paarung:
    """Einfache Liga-Paarung mit Attributzugriff (für Kompatibilität mit lobby.py)"""
    heim: str
    gast: str
    wettbewerb: str

# ---------------------------------------------------------------------------
# Kalender: Spieltag → [(wettbewerb, runde, leg)]
# leg: "einzel" | "hin" | "rueck"
# ---------------------------------------------------------------------------
EUROPA_KALENDER = {
    # Spieltage 1-4: pokaltfrei
    5:  [("dfb",         "1. Runde",     "einzel")],
    6:  [("ecl",         "1. Runde",     "hin")],
    7:  [("ecl",         "1. Runde",     "rueck")],
    8:  [("pokalsieger", "1. Runde",     "hin")],
    9:  [("dfb",         "2. Runde",     "einzel")],
    10: [("pokalsieger", "1. Runde",     "rueck")],
    11: [("uefacup",     "1. Runde",     "hin")],
    12: [("uefacup",     "1. Runde",     "rueck")],
    13: [("uefacup",     "2. Runde",     "hin")],
    14: [("uefacup",     "2. Runde",     "rueck")],
    15: [("uefacup",     "Achtelfinale", "hin")],
    16: [("uefacup",     "Achtelfinale", "rueck")],
    17: [("dfb",         "Achtelfinale", "einzel")],
    18: [("ecl",         "Viertelfinale","hin")],
    19: [("ecl",         "Viertelfinale","rueck")],
    20: [("pokalsieger", "Halbfinale",   "hin")],
    21: [("pokalsieger", "Halbfinale",   "rueck")],
    22: [("dfb",         "Viertelfinale","einzel")],
    23: [("uefacup",     "Viertelfinale","hin")],
    24: [("uefacup",     "Viertelfinale","rueck")],
    25: [("ecl",         "Halbfinale",   "hin")],
    26: [("ecl",         "Halbfinale",   "rueck")],
    27: [("uefacup",     "Halbfinale",   "hin")],
    28: [("dfb",         "Halbfinale",   "einzel")],
    29: [("uefacup",     "Halbfinale",   "rueck")],
    30: [("pokalsieger", "Finale",       "einzel")],
    31: [("ecl",         "Finale",       "einzel")],
    32: [("uefacup",     "Finale",       "hin")],
    33: [("uefacup",     "Finale",       "rueck")],
    34: [("dfb",         "Finale",       "einzel")],
}

# Runden in Reihenfolge pro Wettbewerb
RUNDEN_FOLGE = {
    "ecl":        ["1. Runde", "Viertelfinale", "Halbfinale", "Finale"],
    "pokalsieger": ["1. Runde", "Halbfinale", "Finale"],
    "uefacup":    ["1. Runde", "2. Runde", "Achtelfinale", "Viertelfinale", "Halbfinale", "Finale"],
    "dfb":        ["1. Runde", "2. Runde", "Achtelfinale", "Viertelfinale", "Halbfinale", "Finale"],
}

# ECL/Pokalsieger: Finale ist Einzelspiel; UEFA-Pokal: Finale ist Hin+Rück
FINALE_EINZEL = {"ecl", "pokalsieger"}  # nur diese Cups haben Einzel-Finale (DFB immer einzel)

# Historische Vorbelegung für Saison 1 (Ergebnisse 1982/83)
HISTORISCHE_SAISON_0 = {
    "meister_bl1":              "Hamburger SV",
    "dfb_pokalsieger":          "1. FC Köln",
    "dfb_pokalfinalist":        "Fortuna Köln",
    "ist_pokalsieger_meister":  False,
    "uefacup_qualifikanten":    [
        "SV Werder Bremen",
        "1. FC Köln",
        "FC Bayern München",
        "Borussia Mönchengladbach",
    ],
}


# ---------------------------------------------------------------------------
# Paarung-Dicts (plain dicts, JSON-serialisierbar)
# ---------------------------------------------------------------------------

def _paarung_hinrueck(heim: str, gast: str) -> dict:
    return {"heim": heim, "gast": gast,
            "hin_heim": None, "hin_gast": None,
            "rueck_heim": None, "rueck_gast": None,
            "sieger": None, "typ": "hinrueck"}


def _paarung_einzel(heim: str, gast: str) -> dict:
    return {"heim": heim, "gast": gast,
            "heim_tore": None, "gast_tore": None,
            "sieger": None, "typ": "einzel"}


# ---------------------------------------------------------------------------
# Sieger-Bestimmung
# ---------------------------------------------------------------------------

def bestimme_sieger_einzel(p: dict) -> str:
    """Sieger eines Einzelspiels. Elfmeter-Sieger hat Vorrang."""
    if p.get("elfmeter_sieger"):
        return p["elfmeter_sieger"]
    if p["heim_tore"] > p["gast_tore"]:
        return p["heim"]
    elif p["gast_tore"] > p["heim_tore"]:
        return p["gast"]
    return random.choice([p["heim"], p["gast"]])  # Fallback


def bestimme_sieger_hinrueck(p: dict) -> str:
    """
    Sieger einer Hin/Rück-Paarung mit Auswärtstorregel.
    heim = Heim-Team im Hinspiel, gast = Gast-Team im Hinspiel.
    Elfmeter-Sieger hat Vorrang (wurde nach Verlängerung gesetzt).
    """
    if p.get("elfmeter_sieger"):
        return p["elfmeter_sieger"]
    heim_ges = p["hin_heim"] + p["rueck_gast"]
    gast_ges = p["hin_gast"] + p["rueck_heim"]
    if heim_ges > gast_ges:
        return p["heim"]
    if gast_ges > heim_ges:
        return p["gast"]
    # Auswärtstorregel: heim's away goals = rueck_gast, gast's away goals = hin_gast
    if p["rueck_gast"] > p["hin_gast"]:
        return p["heim"]
    if p["hin_gast"] > p["rueck_gast"]:
        return p["gast"]
    # Noch immer gleich → Fallback (sollte durch VL+Elfmeter nicht mehr vorkommen)
    return random.choice([p["heim"], p["gast"]])


# ---------------------------------------------------------------------------
# Nächste Runde befüllen (Auslosung der Sieger)
# ---------------------------------------------------------------------------

def naechste_runde_befuellen(bracket: dict, wettbewerb: str):
    """
    Ermittelt Sieger der aktiven Runde und lost die nächste Runde aus.
    Aktualisiert bracket in-place.
    """
    folge = RUNDEN_FOLGE[wettbewerb]
    aktiv = bracket["aktive_runde"]
    idx = folge.index(aktiv)
    if idx + 1 >= len(folge):
        return  # schon im Finale

    naechste = folge[idx + 1]
    sieger = [p["sieger"] for p in bracket["runden"][aktiv] if p["sieger"]]
    random.shuffle(sieger)

    ist_finale = (naechste == folge[-1])
    # DFB-Pokal: alle Runden sind Einzelspiele (KO ohne Hin/Rück)
    # ECL/Pokalsieger: nur das Finale ist ein Einzelspiel
    ist_einzel = wettbewerb == "dfb" or (wettbewerb in FINALE_EINZEL and ist_finale)

    neue_paarungen = []
    for i in range(0, len(sieger) - 1, 2):
        if ist_einzel:
            neue_paarungen.append(_paarung_einzel(sieger[i], sieger[i + 1]))
        else:
            neue_paarungen.append(_paarung_hinrueck(sieger[i], sieger[i + 1]))

    bracket["runden"][naechste] = neue_paarungen
    bracket["aktive_runde"] = naechste


# ---------------------------------------------------------------------------
# Liga-Spielplan
# ---------------------------------------------------------------------------

def erstelle_liga_spielplan(teams: list, liga_name: str) -> list:
    """
    Doppelrunden-Spielplan mit ausgeglichener Heim/Auswärts-Abfolge.
    - Hinrunde (Spieltage 1-17): greedy H/A-Zuweisung → möglichst H-A-H-A-Wechsel
    - Rückrunde (Spieltage 18-34): exakt gespiegelte Hinrunde (H/A vertauscht)
      → Spieltag N und N+17 sind immer dieselbe Paarung mit gewechselten Rollen
    - Gesamt: genau 17 Heim- und 17 Auswärtsspiele pro Mannschaft
    """
    teams = list(teams)
    if len(teams) % 2 != 0:
        teams = teams + ["Freilos"]
    n = len(teams)
    runden = n - 1

    # Schritt 1: Reihenfolge der Paarungen per Standard-Rotation (ohne H/A-Zuweisung)
    ring = list(teams)
    paarungen_runden = []
    for _ in range(runden):
        runde = []
        for i in range(n // 2):
            a, b = ring[i], ring[n - 1 - i]
            if a != "Freilos" and b != "Freilos":
                runde.append((a, b))
        paarungen_runden.append(runde)
        ring = [ring[0]] + [ring[-1]] + ring[1:-1]

    # Schritt 2: H/A greedy zuweisen – Abwechslung maximieren
    letztes_heim = {}   # team → True = letztes Spiel war Heim
    heim_zaehler = {}   # team → Anzahl Heimspiele (Ausgleich bei Gleichstand)

    hinrunde = []
    for paare in paarungen_runden:
        spieltag = []
        for (a, b) in paare:
            a_will = letztes_heim.get(a) is not True   # will Heim: letztes war Auswärts/erstes Spiel
            b_will = letztes_heim.get(b) is not True
            if a_will and not b_will:
                heim, gast = a, b
            elif b_will and not a_will:
                heim, gast = b, a
            elif heim_zaehler.get(a, 0) <= heim_zaehler.get(b, 0):
                heim, gast = a, b
            else:
                heim, gast = b, a
            letztes_heim[heim] = True
            letztes_heim[gast] = False
            heim_zaehler[heim] = heim_zaehler.get(heim, 0) + 1
            spieltag.append(Paarung(heim=heim, gast=gast, wettbewerb=liga_name))
        hinrunde.append(spieltag)

    # Schritt 3: Rückrunde = Hinrunde mit exakt vertauschten H/A-Rollen
    rueckrunde = [
        [Paarung(heim=p.gast, gast=p.heim, wettbewerb=liga_name) for p in spieltag]
        for spieltag in hinrunde
    ]

    return hinrunde + rueckrunde


# ---------------------------------------------------------------------------
# DFB-Pokal Bracket
# ---------------------------------------------------------------------------

def erstelle_dfb_pokal_bracket(bl1_teams: list, bl2_teams: list,
                                oberliga_teams: list) -> dict:
    """
    DFB-Pokal: alle 18 BL1 + 20 BL2 + Oberligisten (bis 64 Teams).
    Einzelspiele, Unentschieden → Verlängerung → Elfmeter.
    """
    alle = bl1_teams + bl2_teams
    oberliga_sample = random.sample(oberliga_teams, min(len(oberliga_teams), 64 - len(alle)))
    alle += oberliga_sample
    random.shuffle(alle)

    if len(alle) % 2 != 0:
        alle.append("Freilos")

    paarungen = []
    for i in range(0, len(alle), 2):
        h, g = alle[i], alle[i + 1]
        if h != "Freilos" and g != "Freilos":
            paarungen.append(_paarung_einzel(h, g))

    return {
        "aktive_runde": "1. Runde",
        "runden": {
            "1. Runde":    paarungen,
            "2. Runde":    [],
            "Achtelfinale":  [],
            "Viertelfinale": [],
            "Halbfinale":    [],
            "Finale":        [],
        }
    }


# ---------------------------------------------------------------------------
# Europa-Brackets erstellen
# ---------------------------------------------------------------------------

def erstelle_europa_saison(gs, qualifikanten: dict):
    """
    Erstellt alle Europa-Cup-Brackets für eine Saison und befüllt gs.europa_teams
    mit synthetischen Team-Objekten für internationale Gegner.

    qualifikanten = {
        "meister_bl1": str,
        "dfb_pokalsieger": str,
        "dfb_pokalfinalist": str,
        "ist_pokalsieger_meister": bool,
        "uefacup_qualifikanten": [str, str, str, str],  # BL1-Plätze 2-5
    }
    """
    from engine.game_state import ziehe_europa_gegner, erstelle_international_team

    meister      = qualifikanten["meister_bl1"]
    pokalsieger  = qualifikanten["dfb_pokalsieger"]
    pokalfinalist = qualifikanten["dfb_pokalfinalist"]
    ist_ps_meister = qualifikanten["ist_pokalsieger_meister"]

    # Pokalsieger-Cup-Teilnehmer bestimmen (Double: Finalist rückt nach)
    de_ps_vorschau = pokalfinalist if ist_ps_meister else pokalsieger

    # UEFA-Cup: Vereine, die bereits für ECL oder Pokalsieger qualifiziert sind,
    # dürfen nicht gleichzeitig im UEFA-Cup stehen (hist. korrekte Bereinigung)
    ecl_ps_vergeben = {meister, de_ps_vorschau}
    uefacup_de = list(dict.fromkeys(
        t for t in qualifikanten["uefacup_qualifikanten"] if t not in ecl_ps_vergeben
    ))[:4]

    bereits_vergeben = {meister, pokalsieger, pokalfinalist} | set(uefacup_de)

    # ── ECL: Meister + 15 Tier-1/2-Gegner ──────────────────────────────────
    ecl_gegner = ziehe_europa_gegner([1, 2], 15, ausschluss=list(bereits_vergeben))
    for g in ecl_gegner:
        gs.europa_teams[g["name"]] = erstelle_international_team(
            g["name"], g["staerke_min"], g["staerke_max"], land=g.get("land", ""))

    ecl_teams = [meister] + [g["name"] for g in ecl_gegner]
    while len(ecl_teams) < 16:
        ecl_teams.append(f"ECL-Qualifier {len(ecl_teams)}")
    ecl_teams = ecl_teams[:16]
    random.shuffle(ecl_teams)

    ecl_r1 = [_paarung_hinrueck(ecl_teams[i], ecl_teams[i + 1])
               for i in range(0, 16, 2)]

    gs.europa_brackets["ecl"] = {
        "deutsche_teams": [meister],
        "aktive_runde": "1. Runde",
        "runden": {"1. Runde": ecl_r1, "Viertelfinale": [],
                   "Halbfinale": [], "Finale": []},
    }

    # ── Pokalsieger-Cup: 8 Teams ─────────────────────────────────────────
    de_ps = pokalfinalist if ist_ps_meister else pokalsieger
    ps_ausschluss = list(bereits_vergeben) + [g["name"] for g in ecl_gegner]
    ps_gegner = ziehe_europa_gegner([1, 2, 3], 7, ausschluss=ps_ausschluss)
    for g in ps_gegner:
        gs.europa_teams[g["name"]] = erstelle_international_team(
            g["name"], g["staerke_min"], g["staerke_max"], land=g.get("land", ""))

    ps_teams = [de_ps] + [g["name"] for g in ps_gegner]
    while len(ps_teams) < 8:
        ps_teams.append(f"PS-Qualifier {len(ps_teams)}")
    ps_teams = ps_teams[:8]
    random.shuffle(ps_teams)

    ps_r1 = [_paarung_hinrueck(ps_teams[i], ps_teams[i + 1])
              for i in range(0, 8, 2)]

    gs.europa_brackets["pokalsieger"] = {
        "deutsche_teams": [de_ps],
        "aktive_runde": "1. Runde",
        "runden": {"1. Runde": ps_r1, "Halbfinale": [], "Finale": []},
    }

    # ── UEFA-Pokal: 32 Teams ──────────────────────────────────────────────
    uefa_ausschluss = ps_ausschluss + [g["name"] for g in ps_gegner]
    uefa_gegner = ziehe_europa_gegner([2, 3], 28, ausschluss=uefa_ausschluss)
    for g in uefa_gegner:
        gs.europa_teams[g["name"]] = erstelle_international_team(
            g["name"], g["staerke_min"], g["staerke_max"], land=g.get("land", ""))

    uefa_teams = uefacup_de + [g["name"] for g in uefa_gegner]
    # Auffüllen falls nötig
    while len(uefa_teams) < 32:
        uefa_teams.append(f"Qualifier {len(uefa_teams)}")
    random.shuffle(uefa_teams)
    uefa_teams = uefa_teams[:32]

    uefa_r1 = [_paarung_hinrueck(uefa_teams[i], uefa_teams[i + 1])
               for i in range(0, 32, 2)]

    gs.europa_brackets["uefacup"] = {
        "deutsche_teams": uefacup_de,
        "aktive_runde": "1. Runde",
        "runden": {
            "1. Runde":    uefa_r1,
            "2. Runde":    [],
            "Achtelfinale":  [],
            "Viertelfinale": [],
            "Halbfinale":    [],
            "Finale":        [],
        },
    }
