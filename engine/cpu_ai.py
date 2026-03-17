"""
CPU-KI: Wöchentliche Aktionen für KI-Teams
- Startelf aktualisieren (Verletzte/Gesperrte rotieren)
- Schwache/überschüssige Spieler auf den Markt listen (kein Notverkauf)
- Spieler für schwache oder unterbesetzte Positionen kaufen
"""

import random
from engine.draft import bestimme_startelf, MINDEST_POSITIONEN
from engine.game_state import lade_spieler_csv
from engine.settings import getint, getfloat

_CPU_KAUF_TEXTE = [
    "{team} verpflichtet {spieler} ({pos})",
    "Neuzugang bei {team}: {spieler} kommt",
    "{team} holt {spieler} als Verstärkung",
    "{spieler} wechselt zu {team}",
    "Verstärkung für {team}: {spieler} unterschreibt",
    "{spieler} ist ab sofort Spieler bei {team}",
    "{team} reagiert auf dem Markt und holt {spieler}",
    "{team} sichert sich {spieler} auf dem Transfermarkt",
    "{spieler} ({pos}) verstärkt ab sofort {team}",
    "Vollzogen: {spieler} wechselt zu {team}",
    "{team} legt nach und verpflichtet {spieler}",
    "Transferaktiv: {team} holt {spieler} ({pos})",
    "{spieler} schlägt bei {team} auf",
    "Kaderplanung bei {team}: {spieler} wird verpflichtet",
    "{team} bringt {spieler} ({pos}) an Bord",
    "{spieler} – neuer Kicker bei {team}",
]

# Maximale Kadertiefe pro Position (darüber wird gelistet)
_POS_MAX = {"T": 2, "A": 5, "M": 6, "S": 5}

# Ab dieser Kadergröße wird nicht mehr gekauft
_KADER_MAX_KAUF = getint("cpu_ai", "kader_max_kauf")

# Unter dieser Kadergröße wird nicht mehr gelistet
_KADER_MIN_LIST = getint("cpu_ai", "kader_min_list")


def cpu_woche(game_state, transfermarkt, news_items=None):
    """
    Führt wöchentliche KI-Routine für alle CPU-Teams aus.
    Reihenfolge: Listen → Kaufen → Startelf.
    news_items: optionale Liste, in die notable CPU-Transfers eingetragen werden.
    """
    spieler_cache = transfermarkt._spieler_cache or lade_spieler_csv()

    for team_name, team in game_state.teams.items():
        if team.ist_menschlich:
            continue

        _cpu_listen(team, team_name, transfermarkt)
        _cpu_kaufen(team, team_name, game_state, transfermarkt, spieler_cache, news_items)
        team.startelf = bestimme_startelf(team.kader)


# ─── Verkauf ─────────────────────────────────────────────────────────────────

def _cpu_listen(team, team_name, transfermarkt):
    """Listet schwache Spieler: überfüllte Positionen + deutlich unterdurchschnittliche."""
    if len(team.kader) <= _KADER_MIN_LIST:
        return

    pos_spieler = {}
    for s in team.kader:
        pos_spieler.setdefault(s.position, []).append(s)

    bereits_gelistet = []

    # 1. Überfüllte Positionen: schwächsten listen
    for pos, spieler_liste in pos_spieler.items():
        max_erlaubt = _POS_MAX.get(pos, 3)
        if len(spieler_liste) <= max_erlaubt:
            continue
        if len(team.kader) - len(bereits_gelistet) <= _KADER_MIN_LIST:
            break

        verfuegbare = [s for s in spieler_liste if s.verfuegbar]
        mindest = MINDEST_POSITIONEN.get(pos, 1)
        if len(verfuegbare) <= mindest:
            continue

        schwächster = min(
            (s for s in spieler_liste if s not in bereits_gelistet),
            key=lambda s: s.staerke_wert, default=None
        )
        if schwächster:
            preis = int(schwächster.marktwert * random.uniform(0.8, 1.2))
            team.kader.remove(schwächster)
            transfermarkt.gelistete_spieler.append((schwächster, preis, team_name, 0))
            bereits_gelistet.append(schwächster)

    # 2. Deutlich unterdurchschnittliche Spieler listen (< 70% des Teamdurchschnitts)
    if len(team.kader) <= _KADER_MIN_LIST:
        return
    team_avg = sum(s.staerke_wert for s in team.kader) / len(team.kader)
    schwelle = team_avg * getfloat("cpu_ai", "listing_schwelle_faktor")
    kandidaten = [
        s for s in team.kader
        if s.staerke_wert < schwelle and s not in bereits_gelistet
    ]
    if kandidaten and random.random() < getfloat("cpu_ai", "listing_unterdurchschnitt_chance"):
        schwächster = min(kandidaten, key=lambda s: s.staerke_wert)
        preis = int(schwächster.marktwert * random.uniform(0.8, 1.2))
        team.kader.remove(schwächster)
        transfermarkt.gelistete_spieler.append((schwächster, preis, team_name, 0))


# ─── Kauf ─────────────────────────────────────────────────────────────────────

def _cpu_kaufen(team, team_name, game_state, transfermarkt, spieler_cache, news_items=None):
    """Kauft einen Spieler für eine schwache/unterbesetzte Position."""
    if len(team.kader) >= _KADER_MAX_KAUF:
        return

    kann_inland = team.kontostand >= -1_000_000
    auslaender_count = sum(1 for s in team.kader if s.nationalitaet == "A")
    kann_ausland = team.kontostand > 0 and auslaender_count < 3

    if not kann_inland and not kann_ausland:
        return

    # Nur mit konfigurierbarer Wahrscheinlichkeit aktiv werden
    if random.random() > getfloat("cpu_ai", "kauf_wahrscheinlichkeit"):
        return

    ziel_pos = _ziel_position(team)
    if not ziel_pos:
        return

    team_avg = sum(s.staerke_wert for s in team.kader) / max(len(team.kader), 1)
    bereits_vergeben = {s.name for t in game_state.teams.values() for s in t.kader}

    # Ausland: konfigurierbare Chance, nur wenn Budget es erlaubt
    if kann_ausland and random.random() < getfloat("cpu_ai", "ausland_kauf_chance"):
        pool = [
            s for s in spieler_cache
            if s.nationalitaet == "A"
            and s.position == ziel_pos
            and s.staerke_wert > team_avg
            and s.name not in bereits_vergeben
        ]
        if pool:
            kandidat = random.choice(pool)
            preis = int(kandidat.marktwert * random.uniform(0.9, 1.1))
            # Sicherheitspuffer: nach Kauf noch nicht zu tief ins Minus
            if team.kontostand - preis >= -500_000:
                team.kontostand -= preis
                team.kader.append(kandidat)
                if news_items is not None:
                    news_items.append(random.choice(_CPU_KAUF_TEXTE).format(
                        team=team_name, spieler=kandidat.name, pos=kandidat.position))
                return

    # Inland
    if kann_inland:
        mindest_staerke = max(25, int(team_avg * 0.80))
        pool = [
            s for s in spieler_cache
            if s.nationalitaet == "D"
            and s.position == ziel_pos
            and s.staerke_wert >= mindest_staerke
            and s.staerke_wert <= 84
            and s.name not in bereits_vergeben
        ]
        if not pool:
            return

        # Bevorzuge oberes Drittel der verfügbaren Kandidaten
        pool.sort(key=lambda s: s.staerke_wert)
        cutoff = max(0, len(pool) * 2 // 3)
        kandidat = random.choice(pool[cutoff:]) if cutoff < len(pool) else pool[-1]
        preis = int(kandidat.marktwert * random.uniform(0.9, 1.1))
        # Sicherheitspuffer: nicht unter -900k fallen
        if team.kontostand - preis >= -900_000:
            team.kontostand -= preis
            team.kader.append(kandidat)
            if news_items is not None and kandidat.staerke_wert >= 82:
                news_items.append(random.choice(_CPU_KAUF_TEXTE).format(
                    team=team_name, spieler=kandidat.name, pos=kandidat.position))


# ─── Hilfsfunktionen ──────────────────────────────────────────────────────────

def _ziel_position(team):
    """
    Gibt die Position zurück, die am dringendsten Verstärkung braucht.
    Priorität: 1) unter Mindestzahl, 2) niedrigste Durchschnittsstärke verfügbarer Spieler.
    """
    pos_daten = {}
    for s in team.kader:
        pos_daten.setdefault(s.position, []).append(s)

    # 1. Positionen unter Mindestzahl
    for pos, mindest in MINDEST_POSITIONEN.items():
        if len(pos_daten.get(pos, [])) < mindest:
            return pos

    # 2. Position mit niedrigster Durchschnittsstärke der verfügbaren Spieler
    verfuegbar_avg = {}
    for pos, spieler_liste in pos_daten.items():
        verfuegbare = [s for s in spieler_liste if s.verfuegbar]
        if verfuegbare:
            verfuegbar_avg[pos] = sum(s.staerke_wert for s in verfuegbare) / len(verfuegbare)

    return min(verfuegbar_avg, key=verfuegbar_avg.get) if verfuegbar_avg else None
