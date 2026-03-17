"""
Draft - Zufällige Verteilung der Spieler auf Teams beim Spielstart
"""

import random
from engine.game_state import (
    Spieler, Team,
    lade_spieler_csv, lade_vereine_csv,
    staerke_label,
)
from engine.settings import getint as _cfg_int

def _startkapital() -> int:
    return _cfg_int("finanzen", "team_startbudget")

STARTKADER_GROESSE = 15
MINDEST_POSITIONEN = {"T": 2, "A": 4, "M": 5, "S": 4}
TEAMS_PRO_LIGA = 18  # Teamanzahl pro Spielklasse


def _draft_gewicht(staerke_wert: int, kapital: int) -> float:
    """
    Wahrscheinlichkeitsgewicht für einen Spieler beim Draft.
    Stärke-Schwelle steigt mit dem Kapital:
      6 Mio → Schwelle ~63   Weltklasse(85) hat Gewicht ~0.23
      9 Mio → Schwelle ~80   Weltklasse(85) hat Gewicht ~0.55
     12 Mio → Schwelle ~96   fast alle Spieler voll gewichtet
    """
    schwelle = 30.0 + (kapital / 1_000_000) * 5.5
    if staerke_wert <= schwelle:
        return 1.0
    ueber = staerke_wert - schwelle
    return max(0.05, 1.0 / (1.0 + ueber * 0.15))


def _ziehe_gewichtet(pool: list, kapital: int):
    """Wählt einen Spieler aus dem Pool, bevorzugt schwächere bei niedrigem Kapital."""
    if not pool:
        return None
    gewichte = [_draft_gewicht(s.staerke_wert, kapital) for s in pool]
    spieler = random.choices(pool, weights=gewichte, k=1)[0]
    pool.remove(spieler)
    return spieler


def _ziehe_pool(alle_vereine, liga_start, menschliche_teams, anzahl=TEAMS_PRO_LIGA):
    """
    Zieht zufällig `anzahl` Vereine aus dem Pool für eine Liga.
    Manager-Teams werden bevorzugt und zuerst eingeschlossen.
    """
    pool = [v for v in alle_vereine if v["liga_start"] == liga_start]
    # Menschliche Teams die diesem Pool zugeordnet sind zuerst sichern
    mgr_vereine = [v for v in pool if v["name"] in menschliche_teams]
    rest = [v for v in pool if v["name"] not in menschliche_teams]
    random.shuffle(rest)
    ausgewaehlt = mgr_vereine + rest
    return ausgewaehlt[:anzahl]


def draft_kader(game_state, menschliche_teams):
    STARTKAPITAL = _startkapital()
    alle_spieler = lade_spieler_csv()
    alle_vereine = lade_vereine_csv()
    inlaender = [s for s in alle_spieler if s.nationalitaet == "D"]
    random.shuffle(inlaender)
    inland_pools = {pos: [] for pos in ("T", "A", "M", "S")}
    for s in inlaender:
        inland_pools[s.position].append(s)

    # Zufällige Auswahl von je 18 Teams aus BL1- und BL2-Pool
    bl1_vereine = _ziehe_pool(alle_vereine, 1, menschliche_teams)
    bl2_vereine = _ziehe_pool(alle_vereine, 2, menschliche_teams)

    for verein in bl1_vereine + bl2_vereine:
        team = Team(
            name=verein["name"], liga=verein["liga_start"], kontostand=STARTKAPITAL,
            ist_menschlich=(verein["name"] in menschliche_teams),
            manager_id=menschliche_teams.get(verein["name"], ""),
        )
        team_spieler = []

        # Phase 1: Pflichtpositionen mit Inländern
        for pos, mindest in MINDEST_POSITIONEN.items():
            pool = inland_pools[pos]
            gezogen = 0
            while gezogen < mindest and pool:
                spieler = _ziehe_gewichtet(pool, STARTKAPITAL)
                if spieler is None:
                    break
                team_spieler.append(spieler)
                gezogen += 1

        # Phase 2: Restliche Plätze mit Inländern auffüllen
        while len(team_spieler) < STARTKADER_GROESSE:
            pos = _schwaechste_position(team_spieler)
            pool = inland_pools.get(pos, [])
            if not pool:
                for p in ("M", "A", "S", "T"):
                    if inland_pools[p]:
                        pool = inland_pools[p]
                        break
            if not pool:
                break
            spieler = _ziehe_gewichtet(pool, STARTKAPITAL)
            if spieler is None:
                break
            team_spieler.append(spieler)

        gesamtkosten = sum(int(s.marktwert * random.uniform(0.9, 1.2)) for s in team_spieler)
        if gesamtkosten > STARTKAPITAL:
            faktor = (STARTKAPITAL * 0.85) / max(gesamtkosten, 1)
            for spieler in team_spieler:
                spieler.marktwert = max(10_000, int(spieler.marktwert * faktor))
                spieler.gehalt = max(500, int(spieler.gehalt * faktor))
            gesamtkosten = sum(int(s.marktwert * random.uniform(0.9, 1.1)) for s in team_spieler)

        team.kontostand = STARTKAPITAL - gesamtkosten
        team.kader = team_spieler
        team.startelf = bestimme_startelf(team_spieler)
        game_state.teams[verein["name"]] = team

    # Liga-3-Pool: Als Dicts speichern (für Aufsteiger in BL2 und DFB-Pokal)
    game_state.liga3_pool = [
        {"name": v["name"],
         "staerke_min": v["staerke_min"], "staerke_max": v["staerke_max"]}
        for v in alle_vereine if v["liga_start"] == 3
    ]
    return game_state


def _schwaechste_position(kader):
    zaehler = {"T": 0, "A": 0, "M": 0, "S": 0}
    for s in kader:
        zaehler[s.position] = zaehler.get(s.position, 0) + 1
    bedarf = {pos: MINDEST_POSITIONEN.get(pos, 0) - zaehler.get(pos, 0) for pos in ("T","A","M","S")}
    return max(bedarf, key=bedarf.get)


def bestimme_startelf(kader):
    """
    Wählt 4-4-2 Startelf. Bevorzugt ausschließlich deutsche Spieler.
    Ausländer kommen nur rein wenn zu wenige Deutsche verfügbar (max 3).
    """
    verfuegbar_d = [s for s in kader if s.verfuegbar and s.nationalitaet == "D"]
    verfuegbar_a = [s for s in kader if s.verfuegbar]
    startelf = []
    gewaehlt = set()
    ziel = {"T": 1, "A": 4, "M": 4, "S": 2}

    for pos in ("T", "A", "M", "S"):
        kandidaten = sorted(
            [s for s in verfuegbar_d if s.position == pos and s.name not in gewaehlt],
            key=lambda s: -s.staerke_wert
        )
        for s in kandidaten[:ziel[pos]]:
            startelf.append(s)
            gewaehlt.add(s.name)

    # Lücken nur mit Ausländern füllen wenn keine Deutschen mehr da
    if len(startelf) < 11:
        uebrige = sorted([s for s in verfuegbar_a if s.name not in gewaehlt], key=lambda s: -s.staerke_wert)
        for s in uebrige:
            if len(startelf) >= 11:
                break
            ausl = sum(1 for x in startelf if x.nationalitaet == "A")
            if s.nationalitaet == "A" and ausl >= 3:
                continue
            startelf.append(s)
            gewaehlt.add(s.name)

    return [s.name for s in startelf[:11]]


def erstelle_cpu_team(name: str, liga: int, staerke_min: int, staerke_max: int, kontostand: int = 4_000_000) -> "Team":
    """Erstellt ein neues CPU-Team mit zufälligem Kader (für Liga-3-Aufsteiger)."""
    team_staerke = random.randint(staerke_min, staerke_max)
    cpu_namen = _generiere_cpu_namen(15)
    cpu_pos = ["T", "T", "A", "A", "A", "A", "M", "M", "M", "M", "S", "S", "S", "M", "S"]
    kader = [_generiere_cpu_spieler(team_staerke, cpu_pos[i], cpu_namen[i]) for i in range(15)]
    team = Team(name=name, liga=liga, ist_menschlich=False, kontostand=kontostand)
    team.kader = kader
    team.startelf = bestimme_startelf(kader)
    return team


def _generiere_cpu_spieler(team_staerke, position, name):
    wert = max(1, min(84, team_staerke + random.randint(-10, 10)))  # D-Spieler max 84
    return Spieler(name=name, position=position, staerke_label=staerke_label(wert), staerke_wert=wert, nationalitaet="D")


def _generiere_cpu_namen(anzahl):
    vornamen = ["Wolfgang","Helmut","Dieter","Manfred","Werner","Klaus","Hans","Peter","Michael","Thomas","Stefan","Andreas","Bernd","Ralf","Uwe","Detlef","Frank","Holger","Norbert","Rainer","Herbert","Horst","Heinz","Karl","Gerhard","Friedrich","Heinrich","Erwin","Lothar","Gerd","Siegfried","Walter","Bernhard","Christoph","Martin","Dirk","Olaf","Sven","Torsten","Matthias","Markus","Jens","Lars","Marc","Ingo","Heiko","Sascha","Axel","Carsten","Oliver","Kai"]
    nachnamen = ["Albrecht","Arnold","Bach","Bauer","Baumann","Beck","Becker","Berger","Bergmann","Braun","Brandt","Dietrich","Dorn","Ebert","Esser","Fischer","Franke","Fuchs","Graf","Hahn","Hartmann","Heinrich","Hoffmann","Horn","Huber","Kaiser","Keller","Klein","Koch","Kraft","Krause","Kuhn","Lang","Lehmann","Lindner","Lorenz","Ludwig","Marx","Meier","Neumann","Ott","Peters","Pfeiffer","Richter","Riedel","Roth","Sauer","Schmitz","Schneider","Schulz","Schwarz","Stahl","Stein","Sturm","Thiel","Vogel","Vogt","Wagner","Weber","Werner","Winkler","Winter","Wolf","Zimmermann"]
    namen = set()
    ergebnis = []
    random.shuffle(vornamen)
    random.shuffle(nachnamen)
    for v in vornamen:
        for n in nachnamen:
            name = f"{v} {n}"
            if name not in namen:
                namen.add(name)
                ergebnis.append(name)
                if len(ergebnis) >= anzahl:
                    return ergebnis
    while len(ergebnis) < anzahl:
        ergebnis.append(f"Spieler Nr. {len(ergebnis)+1}")
    return ergebnis
