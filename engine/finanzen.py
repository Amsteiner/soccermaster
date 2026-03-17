"""
Finanzen - Einnahmen, Gehälter, Bilanz
"""

import random
from engine.game_state import Team, GameState
from engine.settings import getint, getfloat

TICKETPREIS = getint("finanzen", "ticketpreis")

_POKAL_MULTIPLIKATOR = {
    "dfb":          getfloat("finanzen", "einnahmen_multiplikator_dfb"),
    "uefacup":      getfloat("finanzen", "einnahmen_multiplikator_uefacup"),
    "pokalsieger":  getfloat("finanzen", "einnahmen_multiplikator_pokalsieger"),
    "ecl":          getfloat("finanzen", "einnahmen_multiplikator_ecl"),
}

ZUSCHAUER_MAX = {
    1: getint("finanzen", "zuschauer_max_bl1"),
    2: getint("finanzen", "zuschauer_max_bl2"),
}

_HEIM_GEWICHT  = getfloat("finanzen", "zuschauer_heim_gewicht")
_GAST_GEWICHT  = getfloat("finanzen", "zuschauer_gast_gewicht")
_ZUFALL_MIN    = getfloat("finanzen", "zuschauer_zufall_min")
_ZUFALL_MAX    = getfloat("finanzen", "zuschauer_zufall_max")


def berechne_zuschauer(heim: Team, gast: Team, tabelle_heim: int, tabelle_gast: int, liga: int) -> int:
    """
    Berechnet Zuschauerzahl basierend auf Tabellenplätzen + Zufall.
    Niedrigerer Tabellenplatz (z.B. Platz 1) = mehr Zuschauer.
    """
    max_zuschauer = ZUSCHAUER_MAX.get(liga, 20000)

    # Basis: je besser die Platzierung, desto mehr Zuschauer
    heim_faktor = 1 - (tabelle_heim - 1) / 20  # Platz 1 = 1.0, Platz 18/20 = ~0.15
    gast_faktor = 1 - (tabelle_gast - 1) / 20

    basis = max_zuschauer * (heim_faktor * _HEIM_GEWICHT + gast_faktor * _GAST_GEWICHT)

    zufall = random.uniform(_ZUFALL_MIN, _ZUFALL_MAX)
    zuschauer = int(basis * zufall)

    return max(500, min(max_zuschauer, zuschauer))


def heimspiel_einnahmen(heim: Team, gast: Team, tabelle_heim: int, tabelle_gast: int, liga: int) -> int:
    """Berechnet Einnahmen aus einem Heimspiel"""
    zuschauer = berechne_zuschauer(heim, gast, tabelle_heim, tabelle_gast, liga)
    einnahmen = zuschauer * TICKETPREIS
    return einnahmen


# Zuschauer-Spannbreiten (min, max) nach Wettbewerb und Runde (1983er Realität)
# ECL = Landesmeisterpokal (prestige + reiche Klubs), deutlich mehr als UEFA-Pokal
ZUSCHAUER_OBERGRENZEN = {
    "ecl": {
        "1. runde":      (20000, 35000),
        "viertelfinale": (30000, 50000),
        "halbfinale":    (40000, 60000),
        "finale":        (55000, 80000),
    },
    "pokalsieger": {
        "1. runde":      (15000, 26000),
        "halbfinale":    (25000, 40000),
        "finale":        (40000, 55000),
    },
    "uefacup": {
        "1. runde":      (12000, 22000),
        "2. runde":      (15000, 28000),
        "achtelfinale":  (18000, 32000),
        "viertelfinale": (25000, 40000),
        "halbfinale":    (30000, 48000),
        "finale":        (42000, 62000),
    },
}


def internationale_einnahmen(heim: Team, gast: Team, wettbewerb: str, runde: str) -> tuple:
    """
    Pokal-Einnahmen nach Wettbewerb und Runde (1983er Basis).
    Gibt (gesamt, anteil) zurück; anteil = gesamt // 2.
    Der Aufrufer entscheidet, welche Teams welchen Anteil erhalten.
    """
    tabelle = ZUSCHAUER_OBERGRENZEN.get(wettbewerb, {})
    grenzen = tabelle.get(runde.lower(), (12000, 22000))
    zuschauer = int(random.uniform(grenzen[0], grenzen[1]))
    multiplikator = _POKAL_MULTIPLIKATOR.get(wettbewerb, 1.0)
    gesamt = int(zuschauer * TICKETPREIS * multiplikator)
    anteil = gesamt // 2
    return gesamt, anteil


def saison_abschluss(team: Team):
    """Prüft Insolvenz am Saisonende"""
    if team.kontostand < 0:
        team.saisons_negativ += 1
    else:
        team.saisons_negativ = 0

    if team.saisons_negativ >= 3:
        return False, "INSOLVENZ! 3 Saisons in den roten Zahlen."
    return True, "OK"
