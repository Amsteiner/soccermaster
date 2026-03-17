"""
GameState - Zentraler Spielzustand
Verwaltet alle Daten einer laufenden Spielsession
"""

import random
import csv
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import configparser
from engine.settings import getint as _cfg_int, getfloat as _cfg_float

DATA_DIR = Path(__file__).parent.parent / "data"

# Namen einmalig aus namen.cfg laden
_namen_cfg = configparser.ConfigParser()
_namen_cfg.read(Path(__file__).parent.parent / "namen.cfg", encoding="utf-8")
_VORNAMEN = [n.strip() for n in _namen_cfg.get("vornamen", "liste", fallback="").splitlines() if n.strip()]
_NACHNAMEN = [n.strip() for n in _namen_cfg.get("nachnamen", "liste", fallback="").splitlines() if n.strip()]

# Mapping: Land (aus internationale_vereine.csv) → Sektion-Suffix in namen.cfg
_LAND_SEKTION = {
    "England":          "england",
    "Schottland":       "schottland",
    "Italien":          "italien",
    "Spanien":          "spanien",
    "Niederlande":      "niederlande",
    "Frankreich":       "frankreich",
    "Belgien":          "belgien",
    "Portugal":         "portugal",
    "UdSSR":            "udssr",
    "Polen":            "polen",
    "Jugoslawien":      "jugoslawien",
    "Tschechoslowakei": "tschechoslowakei",
    "Rumänien":         "rumaenien",
    "Bulgarien":        "bulgarien",
    "Griechenland":     "griechenland",
    "Schweden":         "schweden",
    "Türkei":           "tuerkei",
    "Ungarn":           "ungarn",
}
_LAND_NAMEN_CACHE: dict = {}

def _lade_land_namen(land: str):
    """Gibt (vornamen, nachnamen) für ein Land aus namen.cfg zurück."""
    if land in _LAND_NAMEN_CACHE:
        return _LAND_NAMEN_CACHE[land]
    sek = _LAND_SEKTION.get(land)
    if not sek:
        _LAND_NAMEN_CACHE[land] = (_VORNAMEN, _NACHNAMEN)
        return _VORNAMEN, _NACHNAMEN
    vn = [n.strip() for n in _namen_cfg.get(f"vornamen_{sek}", "liste", fallback="").splitlines() if n.strip()]
    nn = [n.strip() for n in _namen_cfg.get(f"nachnamen_{sek}", "liste", fallback="").splitlines() if n.strip()]
    if not vn: vn = _VORNAMEN
    if not nn: nn = _NACHNAMEN
    _LAND_NAMEN_CACHE[land] = (vn, nn)
    return vn, nn

# Stärke-Ranges (versteckt)
STAERKE_RANGES = {
    "Weltklasse":  (85, 100),
    "Sehr stark":  (70, 90),
    "Stark":       (55, 75),
    "Durchschnitt":(40, 60),
    "Schwach":     (20, 45),
    "Sehr schwach":(1,  25),
}

# Gehaltsskala pro Monat (DM), basierend auf verstecktem Wert 1-100
def berechne_gehalt(staerke_wert: int) -> int:
    """Berechnet Monatsgehalt basierend auf verstecktem Stärkewert"""
    if staerke_wert >= 85:
        basis = random.randint(36_000, 60_000)   # Weltklasse: ~40-60 TDM/Monat
    elif staerke_wert >= 70:
        basis = random.randint(18_000, 36_000)   # Sehr stark: ~18-36 TDM/Monat
    elif staerke_wert >= 55:
        basis = random.randint(9_000, 18_000)    # Stark: ~9-18 TDM/Monat
    elif staerke_wert >= 40:
        basis = random.randint(4_000,  9_000)    # Durchschnitt: ~4-9 TDM/Monat
    elif staerke_wert >= 20:
        basis = random.randint(2_000,  4_000)    # Schwach: ~2-4 TDM/Monat
    else:
        basis = random.randint(  500,  2_000)    # Sehr schwach
    # +/- 10% Spielraum + konfigurierbarer Globalfaktor
    faktor = random.uniform(0.9, 1.1) * _cfg_float("finanzen", "gehalt_faktor")
    return int(basis * faktor)


def berechne_marktwert(staerke_wert: int) -> int:
    """Berechnet Marktwert linear basierend auf verstecktem Stärkewert"""
    if staerke_wert >= 85:
        basis = int(3_500_000 + (staerke_wert - 85) / 15 * 7_500_000)
    elif staerke_wert >= 70:
        basis = int(1_200_000 + (staerke_wert - 70) / 15 * 2_800_000)
    elif staerke_wert >= 55:
        basis = int(500_000 + (staerke_wert - 55) / 15 * 1_000_000)
    elif staerke_wert >= 40:
        basis = int(250_000 + (staerke_wert - 40) / 15 * 350_000)
    elif staerke_wert >= 20:
        basis = int(80_000 + (staerke_wert - 20) / 20 * 220_000)
    else:
        basis = int(20_000 + staerke_wert / 20 * 80_000)
    return basis


def staerke_label(wert: int) -> str:
    """Gibt den angezeigten Stärkenamen zurück, bei Überschneidungen zufällig"""
    kandidaten = []
    for label, (lo, hi) in STAERKE_RANGES.items():
        if lo <= wert <= hi:
            kandidaten.append(label)
    if not kandidaten:
        return "Sehr schwach"
    return random.choice(kandidaten)


def wuerfel_staerke(label: str) -> int:
    """Würfelt einen versteckten Zahlenwert für ein Stärke-Label"""
    lo, hi = STAERKE_RANGES[label]
    return random.randint(lo, hi)


@dataclass
class Spieler:
    name: str
    position: str          # T, A, M, S
    staerke_label: str     # angezeigter Name
    staerke_wert: int      # versteckter Zahlenwert
    nationalitaet: str     # D oder A
    marktwert: int = 0
    gehalt: int = 0        # pro Monat
    verletzt_wochen: int = 0
    gesperrt_wochen: int = 0
    gelbe_karten: int = 0
    gelbe_karten_zyklus: int = 0  # Karten im aktuellen Zyklus (wird bei Sperre zurückgesetzt)
    diagnose: str = ""
    tore_liga: int = 0
    tore_pokal: int = 0
    rote_karten: int = 0
    staerke_wert_basis: int = 0   # >0 = Ausländer temporär abgeschwächt, Original hier gespeichert

    def __post_init__(self):
        if self.marktwert == 0:
            self.marktwert = berechne_marktwert(self.staerke_wert)
        if self.gehalt == 0:
            self.gehalt = berechne_gehalt(self.staerke_wert)

    @property
    def verfuegbar(self) -> bool:
        return self.verletzt_wochen == 0 and self.gesperrt_wochen == 0

    @property
    def ist_auslaender(self) -> bool:
        return self.nationalitaet == "A"

    def wochentick(self):
        """Verringert Sperr- und Verletzungswochen um 1"""
        if self.verletzt_wochen > 0:
            self.verletzt_wochen -= 1
        if self.gesperrt_wochen > 0:
            self.gesperrt_wochen -= 1


@dataclass
class Team:
    name: str
    liga: int              # 1, 2, oder 0 (Oberliga/CPU)
    kader: list = field(default_factory=list)
    startelf: list = field(default_factory=list)   # 11 Spieler-Namen
    kontostand: int = field(default_factory=lambda: _cfg_int("finanzen", "team_startbudget"))
    saisons_negativ: int = 0
    punkte: int = 0
    tore: int = 0
    gegentore: int = 0
    spiele: int = 0
    siege: int = 0
    unentschieden: int = 0
    niederlagen: int = 0
    ist_menschlich: bool = False
    manager_id: str = ""
    kontostand_verlauf: list = field(default_factory=list)

    @property
    def tordifferenz(self) -> int:
        return self.tore - self.gegentore

    def wochentick(self):
        """Wöchentliche Gehaltsabzüge und Status-Updates"""
        wochenlohn = sum(s.gehalt // 4 for s in self.kader)
        self.kontostand -= wochenlohn
        if self.kontostand < 0:
            zinsen = int(abs(self.kontostand) * _cfg_float("finanzen", "kontozins_faktor"))
            self.kontostand -= zinsen
        for spieler in self.kader:
            spieler.wochentick()


POSITIONEN_STANDARD = ["T", "A", "A", "A", "A", "M", "M", "M", "M", "S", "S"]


def _generiere_zufallsnamen(anzahl: int, land: str = "") -> list:
    """Generiert zufällige Spielernamen – länderspezifisch wenn land angegeben."""
    vn_base, nn_base = _lade_land_namen(land) if land else (_VORNAMEN, _NACHNAMEN)
    used = set()
    result = []
    vn = vn_base[:]
    nn = nn_base[:]
    random.shuffle(vn)
    random.shuffle(nn)
    for v in vn:
        for n in nn:
            name = f"{v} {n}"
            if name not in used:
                used.add(name)
                result.append(name)
                if len(result) >= anzahl:
                    return result
    # Fallback: weitere zufällige Kombinationen aus derselben Länderliste
    while len(result) < anzahl:
        name = f"{random.choice(vn_base)} {random.choice(nn_base)}"
        if name not in used:
            used.add(name)
            result.append(name)
    return result


def erstelle_international_team(name: str, staerke_min: int, staerke_max: int,
                                 auslaender: bool = True, land: str = "") -> "Team":
    """
    Erstellt ein temporäres Team-Objekt für internationale oder CPU-Pokal-Gegner.
    auslaender=True  → alle Spieler Nationalität "A" (internationale Clubs)
    auslaender=False → alle Spieler Nationalität "D" (deutsche BL2/Oberliga-Teams)
    land             → Ländername für länderspezifische Spielernamen
    """
    nat = "A" if auslaender else "D"
    namen = _generiere_zufallsnamen(len(POSITIONEN_STANDARD), land=land if auslaender else "")
    kader = []
    for i, pos in enumerate(POSITIONEN_STANDARD):
        wert = random.randint(staerke_min, staerke_max)
        s = Spieler(
            name=namen[i],
            position=pos,
            staerke_label=staerke_label(wert),
            staerke_wert=wert,
            nationalitaet=nat,
        )
        kader.append(s)
    team = Team(name=name, liga=0, kader=kader)
    team.startelf = [s.name for s in kader]
    return team


@dataclass
class GameState:
    lobby_code: str
    saison: int = 1
    spieltag: int = 1
    phase: str = "management"   # management, liga, pokal, europa
    teams: dict = field(default_factory=dict)      # name -> Team (BL1-Teams)
    europa_teams: dict = field(default_factory=dict)  # name -> Team (int. + BL2/Oberliga)
    transferpool_inland: list = field(default_factory=list)
    transferpool_ausland: list = field(default_factory=list)
    # Cup-Brackets (plain dicts, JSON-serialisierbar)
    dfb_pokal_bracket: dict = field(default_factory=dict)
    europa_brackets: dict = field(default_factory=dict)  # ecl / pokalsieger / uefacup
    zusatz_spieler: list = field(default_factory=list)  # saisonweise generierte Nachwuchsspieler
    # Pro Team: letzte 2 Saisonabschlüsse [{saison, position, end_kontostand, liga}]
    finanzen_verlauf: dict = field(default_factory=dict)  # team_name -> [...]

    def get_tabelle(self, liga: int) -> list:
        """Gibt sortierte Tabelle für eine Liga zurück"""
        teams = [t for t in self.teams.values() if t.liga == liga]
        return sorted(teams, key=lambda t: (-t.punkte, -t.tordifferenz, -t.tore))

    def get_team(self, name: str) -> "Team":
        """Gibt Team-Objekt zurück – sucht in BL-Teams und Europa-Teams"""
        return self.teams.get(name) or self.europa_teams.get(name)

    def naechster_spieltag(self):
        self.spieltag += 1
        for team in self.teams.values():
            team.wochentick()
            if team.ist_menschlich:
                team.kontostand_verlauf.append(team.kontostand)
                if len(team.kontostand_verlauf) > 34:
                    team.kontostand_verlauf.pop(0)


def lade_spieler_csv() -> list:
    """Lädt alle Spieler aus der CSV"""
    spieler = []
    csv_path = Path(__file__).parent.parent / "data" / "spieler.csv"
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            wert = wuerfel_staerke(row["staerke"])
            if row["nationalitaet"] == "D":
                wert = min(wert, 84)  # Inländer max "Sehr stark"
            s = Spieler(
                name=row["name"],
                position=row["position"],
                staerke_label=staerke_label(wert),
                staerke_wert=wert,
                nationalitaet=row["nationalitaet"],
            )
            spieler.append(s)
    return spieler


def lade_vereine_csv() -> list:
    """Lädt alle Vereine aus der CSV"""
    vereine = []
    csv_path = Path(__file__).parent.parent / "data" / "vereine.csv"
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vereine.append({
                "name": row["name"],
                "liga_start": int(row["liga_start"]),
                "staerke_min": int(row["staerke_min"]),
                "staerke_max": int(row["staerke_max"]),
            })
    return vereine


def lade_internationale_vereine_csv() -> list:
    """Lädt internationale Vereine für Europapokale"""
    vereine = []
    csv_path = DATA_DIR / "internationale_vereine.csv"
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(filter(lambda r: not r.startswith('#'), f))
        for row in reader:
            vereine.append({
                "name": row["name"],
                "land": row["land"],
                "staerke_min": int(row["staerke_min"]),
                "staerke_max": int(row["staerke_max"]),
                "tier": int(row["tier"]),
            })
    return vereine


def generiere_nachwuchs(game_state: "GameState", anzahl_de: int = None, anzahl_a: int = None):
    """
    Generiert neue Nachwuchsspieler am Saisonstart und fügt sie zu gs.zusatz_spieler hinzu.
    Stärkeverteilung: überwiegend Schwach–Stark (keine Weltklasse-Inländer).
    Namen werden so gewählt, dass keine Dopplungen mit bestehenden Spielern entstehen.
    """
    if anzahl_de is None:
        anzahl_de = _cfg_int("nachwuchs", "neue_spieler_de")
    if anzahl_a is None:
        anzahl_a = _cfg_int("nachwuchs", "neue_spieler_a")

    _nw_de_min = _cfg_int("nachwuchs", "nachwuchs_min_de")
    _nw_de_max = _cfg_int("nachwuchs", "nachwuchs_max_de")
    _nw_a_min  = _cfg_int("nachwuchs", "nachwuchs_min_a")
    _nw_a_max  = _cfg_int("nachwuchs", "nachwuchs_max_a")

    bereits_vergeben = {s.name for t in game_state.teams.values() for s in t.kader}
    bereits_vergeben |= {s.name for s in game_state.zusatz_spieler}

    alle_namen = _generiere_zufallsnamen(anzahl_de + anzahl_a + 60)
    freie_namen = [n for n in alle_namen if n not in bereits_vergeben]

    def _wuerfel_nachwuchs_de():
        return random.randint(_nw_de_min, _nw_de_max)

    def _wuerfel_nachwuchs_a():
        return random.randint(_nw_a_min, _nw_a_max)

    neu = []
    namen_iter = iter(freie_namen)
    positionen_pool = POSITIONEN_STANDARD * 4  # genug Positionen

    for i in range(anzahl_de):
        try:
            name = next(namen_iter)
        except StopIteration:
            break
        pos = positionen_pool[i % len(positionen_pool)]
        wert = min(_wuerfel_nachwuchs_de(), 84)
        s = Spieler(
            name=name,
            position=pos,
            staerke_label=staerke_label(wert),
            staerke_wert=wert,
            nationalitaet="D",
        )
        neu.append(s)

    for i in range(anzahl_a):
        try:
            name = next(namen_iter)
        except StopIteration:
            break
        pos = positionen_pool[i % len(positionen_pool)]
        wert = _wuerfel_nachwuchs_a()
        s = Spieler(
            name=name,
            position=pos,
            staerke_label=staerke_label(wert),
            staerke_wert=wert,
            nationalitaet="A",
        )
        neu.append(s)

    game_state.zusatz_spieler.extend(neu)


def ziehe_europa_gegner(tier_filter: list, anzahl: int, ausschluss: list = None) -> list:
    """
    Zieht zufällige internationale Gegner aus dem Pool.
    tier_filter: Liste erlaubter Tiers, z.B. [1, 2] für ECL
    ausschluss: Vereinsnamen die nicht gezogen werden sollen
    Gibt Liste von Vereins-Dicts zurück (mit zufällig gewürfelter Stärke).
    """
    pool = lade_internationale_vereine_csv()
    ausschluss = ausschluss or []
    pool = [v for v in pool if v["tier"] in tier_filter and v["name"] not in ausschluss]
    random.shuffle(pool)

    # Erster Durchgang: max. 1 Verein pro Land
    laender_gesehen = set()
    kandidaten = []
    rest = []
    for v in pool:
        if v["land"] not in laender_gesehen:
            kandidaten.append(v)
            laender_gesehen.add(v["land"])
        else:
            rest.append(v)
        if len(kandidaten) >= anzahl:
            break

    # Zweiter Durchgang: Länder auffüllen falls nicht genug (historisch: England
    # hatte in den 80ern oft 3+ Klubs gleichzeitig in Europapokalen)
    for v in rest:
        if len(kandidaten) >= anzahl:
            break
        kandidaten.append(v)

    # Stärke würfeln
    for v in kandidaten:
        v["staerke_wert"] = random.randint(v["staerke_min"], v["staerke_max"])
    return kandidaten
