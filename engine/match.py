"""
Match Engine - Simuliert ein Fußballspiel
Spielgeschwindigkeit konfigurierbar via settings.cfg → [match] sekunden_pro_minute
"""

import random
import asyncio
from dataclasses import dataclass, field
from engine.game_state import Team, Spieler, staerke_label
from engine.settings import getfloat as _cfg_float, getint as _cfg_int

# Formations-Malus
STANDARD_FORMATIONEN = {
    (4, 4, 2), (4, 3, 3), (3, 5, 2), (4, 5, 1),
    (5, 3, 2), (3, 4, 3), (5, 4, 1),
}

DIAGNOSEN = {
    1: "Leichte Zerrung",
    2: "Muskelfaserriss",
    3: "Knochenprellung",
    4: "Bänderriss",
    5: "Meniskusschaden",
    6: "Wadenbeinbruch",
    7: "Kreuzbandriss",
    8: "Kreuzbandriss",
}

GELB_WAHRSCHEINLICHKEIT = {
    "T": _cfg_float("match", "gelb_torwart"),
    "A": _cfg_float("match", "gelb_abwehr"),
    "M": _cfg_float("match", "gelb_mittelfeld"),
    "S": _cfg_float("match", "gelb_sturm"),
}


@dataclass
class MatchEreignis:
    minute: int
    typ: str        # tor, eigentor, gelb, rot, verletzung
    spieler: str
    team: str
    detail: str = ""


@dataclass
class MatchErgebnis:
    heim_team: str
    gast_team: str
    heim_tore: int = 0
    gast_tore: int = 0
    ereignisse: list = field(default_factory=list)
    heim_rote_karten: int = 0
    gast_rote_karten: int = 0
    abbruch: bool = False          # Spiel abgebrochen wegen zu wenig Spieler
    abbruch_team: str = ""         # Team das den Abbruch verursacht hat


def berechne_formation(startelf_positionen: list) -> tuple:
    """Gibt (abwehr, mittelfeld, sturm) zurück"""
    a = startelf_positionen.count("A")
    m = startelf_positionen.count("M")
    s = startelf_positionen.count("S")
    return (a, m, s)


def formations_malus(formation: tuple) -> float:
    """Gibt Malus-Faktor zurück (1.0 = kein Malus)"""
    if formation in STANDARD_FORMATIONEN:
        return 1.0
    summe = sum(formation)
    if summe == 10:  # genau 10 Feldspieler (ohne TW)
        malus = random.uniform(
            _cfg_float("match", "formations_malus_min"),
            _cfg_float("match", "formations_malus_max"),
        )
    else:
        malus = random.uniform(
            _cfg_float("match", "formations_malus_extrem_min"),
            _cfg_float("match", "formations_malus_extrem_max"),
        )
    return 1.0 - malus


def team_staerken(team: Team) -> dict:
    """Berechnet Sturm-, Mittelfeld- und Abwehrstärke aus der Startelf"""
    startelf_spieler = [s for s in team.kader if s.name in team.startelf]

    # Not-Torwart Check
    hat_torwart = any(s.position == "T" for s in startelf_spieler)
    if not hat_torwart:
        schwächster = min(startelf_spieler, key=lambda s: s.staerke_wert)
        tw_wert = int(schwächster.staerke_wert * _cfg_float("match", "not_torwart_faktor"))
    else:
        tw = next(s for s in startelf_spieler if s.position == "T")
        tw_wert = tw.staerke_wert

    feldspieler = [s for s in startelf_spieler if s.position != "T"]
    positionen = [s.position for s in startelf_spieler]
    formation = berechne_formation(positionen)
    malus = formations_malus(formation)

    sturm = sum(s.staerke_wert for s in feldspieler if s.position == "S")
    mittelfeld = sum(s.staerke_wert for s in feldspieler if s.position == "M")
    abwehr = sum(s.staerke_wert for s in feldspieler if s.position == "A")


    return {
        "sturm": int(sturm * malus),
        "mittelfeld": int(mittelfeld * malus),
        "abwehr": int(abwehr * malus),
        "torwart": tw_wert,
        "spieler": startelf_spieler,
        "formation": formation,
    }


def mittelfeld_bonus(mf_wert: int) -> float:
    """Gibt prozentualen Bonus basierend auf MF-Durchschnitt"""
    if mf_wert >= 85:
        return 0.40
    elif mf_wert >= 70:
        return 0.30
    elif mf_wert >= 55:
        return 0.20
    elif mf_wert >= 40:
        return 0.10
    elif mf_wert >= 20:
        return 0.05
    return 0.0


async def simulate_match(
    heim: Team,
    gast: Team,
    callback=None,  # async callback für Live-Ticker
    ist_menschlich_heim: bool = False,
    ist_menschlich_gast: bool = False,
    instant: bool = False,   # True = kein Echtzeit-Delay (für CPU-only Pokalspiele)
    skip_ref: list = None,   # [False] -> auf [True] setzen um laufende Sim zu beschleunigen
    ist_pokal: bool = False, # True = Tore als Pokaltore zählen
    start_minute: int = 1,   # Startminute (91 für Verlängerung)
    end_minute: int = 90,    # Endminute (120 für Verlängerung)
) -> MatchErgebnis:
    """
    Simuliert ein vollständiges Spiel Minute für Minute.
    callback(minute, ereignis) wird für Ticker-Meldungen aufgerufen.
    """
    ergebnis = MatchErgebnis(heim_team=heim.name, gast_team=gast.name)

    heim_staerken = team_staerken(heim)
    gast_staerken = team_staerken(gast)

    heim_start_anzahl = len(heim_staerken["spieler"])
    gast_start_anzahl = len(gast_staerken["spieler"])
    heim_rote = 0
    gast_rote = 0
    heim_ausgefallen = 0   # Rot + Verletzt während des Spiels
    gast_ausgefallen = 0
    letzte_tor_minute = -99  # Abkühlphase nach Toren
    _MIN_SPIELER = 7          # Mindestspielerzahl; bei weniger → Abbruch

    # Gelbe Karten pro Spieler in diesem Spiel
    heim_gelb = {s.name: 0 for s in heim_staerken["spieler"]}
    gast_gelb = {s.name: 0 for s in gast_staerken["spieler"]}
    # Spieler die bereits Rot gesehen haben – keine weiteren Karten möglich
    heim_rot_raus: set = set()
    gast_rot_raus: set = set()
    # Letzte Minute in der ein Spieler eine Gelbe bekam (Cooldown)
    gelb_zuletzt: dict = {}
    _GELB_ABSTAND = _cfg_int("match", "gelb_abstand_min")

    # Fixer Heimvorteil (konfigurierbar in settings.cfg)
    heimvorteil = _cfg_float("match", "heimvorteil_fest")

    # Anpfiff (nur bei regulärer Spielzeit)
    if callback and start_minute == 1:
        e_anpfiff = MatchEreignis(minute=0, typ="info", spieler="ANPFIFF", team="", detail="")
        await callback(0, e_anpfiff, ergebnis)

    for minute in range(start_minute, end_minute + 1):
        # Minuten-Tick für Live-Anzeige (jede Minute, kein Spielereignis)
        if callback:
            e_tick = MatchEreignis(minute=minute, typ="tick", spieler="", team="", detail="")
            await callback(minute, e_tick, ergebnis)

        # Halbzeit (nur in regulärer Spielzeit)
        if minute == 46 and callback and start_minute == 1:
            e_halb = MatchEreignis(minute=45, typ="info", spieler="HALBZEIT", team="",
                                   detail=f"{ergebnis.heim_tore}:{ergebnis.gast_tore}")
            await callback(45, e_halb, ergebnis)

        # Unterzahl-Malus
        _rot_malus = _cfg_float("match", "rot_staerke_malus")
        heim_staerke_faktor = max(0.1, 1.0 - (heim_rote * _rot_malus))
        gast_staerke_faktor = max(0.1, 1.0 - (gast_rote * _rot_malus))

        # SCHRITT 1: Ballkontrolle (Mittelfeld vs Mittelfeld)
        heim_mf = heim_staerken["mittelfeld"] * heim_staerke_faktor
        gast_mf = gast_staerken["mittelfeld"] * gast_staerke_faktor
        gesamt_mf = heim_mf + gast_mf if (heim_mf + gast_mf) > 0 else 1

        heim_hat_ball = random.random() < (heim_mf / gesamt_mf)

        # SCHRITT 2: Angriff vs Abwehr
        if heim_hat_ball:
            angreifer_sturm = heim_staerken["sturm"] * heim_staerke_faktor
            mf_bon = mittelfeld_bonus(heim_mf / max(1, len([s for s in heim_staerken["spieler"] if s.position == "M"])))
            # MF-Dominanz Bonus
            mf_dominanz = max(0, (heim_mf - gast_mf) / gesamt_mf * _cfg_float("match", "mf_dominanz_faktor"))
            angriff_staerke = angreifer_sturm * (1 + mf_bon + mf_dominanz) * (1 + heimvorteil)
            verteidigungs_staerke = gast_staerken["abwehr"] * gast_staerke_faktor
            torwart_staerke = gast_staerken["torwart"]
            tor_team = "heim"
            tor_spieler_pool = [s for s in heim_staerken["spieler"] if s.position != "T"]
        else:
            angreifer_sturm = gast_staerken["sturm"] * gast_staerke_faktor
            mf_bon = mittelfeld_bonus(gast_mf / max(1, len([s for s in gast_staerken["spieler"] if s.position == "M"])))
            mf_dominanz = max(0, (gast_mf - heim_mf) / gesamt_mf * _cfg_float("match", "mf_dominanz_faktor"))
            angriff_staerke = angreifer_sturm * (1 + mf_bon + mf_dominanz)
            verteidigungs_staerke = heim_staerken["abwehr"] * heim_staerke_faktor
            torwart_staerke = heim_staerken["torwart"]
            tor_team = "gast"
            tor_spieler_pool = [s for s in gast_staerken["spieler"] if s.position != "T"]

        # Schusswahrscheinlichkeit ~12% bei gleich starken Teams
        verh = angriff_staerke / max(1, verteidigungs_staerke)
        schuss_chance = _cfg_float("match", "schuss_chance_basis") * verh
        schuss_chance = min(schuss_chance, _cfg_float("match", "schuss_chance_cap"))
        # Harter Mindestabstand nach Tor: in den ersten N Minuten kein weiteres Tor möglich
        if minute - letzte_tor_minute < _cfg_float("match", "tor_abstand_min"):
            schuss_chance = 0

        if random.random() < schuss_chance:
            # SCHRITT 3: Schuss vs Torwart (~18% Basis)
            _tw_gew = _cfg_float("match", "torwart_abwehr_gewicht")
            tor_chance = _cfg_float("match", "tor_chance_basis") * (angriff_staerke / max(1, torwart_staerke + verteidigungs_staerke * _tw_gew))
            tor_chance = min(tor_chance, _cfg_float("match", "tor_chance_cap"))

            if random.random() < tor_chance:
                # Eigentor?
                gewichte_angriff = {"S": 5, "M": 2, "A": 0.5}
                if random.random() < _cfg_float("match", "eigentor_chance"):
                    typ = "eigentor"
                    tor_team_real = "gast" if tor_team == "heim" else "heim"
                    # Verteidiger-Pool des angreifenden Teams (die das Eigentor schießen)
                    verteidigungs_pool = [
                        s for s in (gast_staerken if tor_team == "heim" else heim_staerken)["spieler"]
                        if s.position != "T"
                    ]
                    eigentor_gew = {"A": 5, "M": 2, "S": 0.5}
                    eigentor_spieler = random.choices(
                        verteidigungs_pool,
                        weights=[eigentor_gew.get(s.position, 1) for s in verteidigungs_pool]
                    )[0] if verteidigungs_pool else None
                    # Angerechneter Spieler: letzter Berührer des angreifenden Teams
                    angerechnet = random.choices(
                        tor_spieler_pool,
                        weights=[gewichte_angriff.get(s.position, 1) for s in tor_spieler_pool]
                    )[0] if tor_spieler_pool else None
                    schütze = angerechnet  # bekommt das Tor gutgeschrieben
                    spieler_anzeige = f"{eigentor_spieler.name if eigentor_spieler else '?'} [{angerechnet.name if angerechnet else '?'}]"
                else:
                    typ = "tor"
                    tor_team_real = tor_team
                    schütze = random.choices(
                        tor_spieler_pool,
                        weights=[gewichte_angriff.get(s.position, 1) for s in tor_spieler_pool]
                    )[0] if tor_spieler_pool else None
                    spieler_anzeige = schütze.name if schütze else "Unbekannt"

                if tor_team_real == "heim":
                    ergebnis.heim_tore += 1
                else:
                    ergebnis.gast_tore += 1
                letzte_tor_minute = minute

                if schütze and typ in ("tor", "eigentor"):
                    if ist_pokal:
                        schütze.tore_pokal += 1
                    else:
                        schütze.tore_liga += 1

                ereignis = MatchEreignis(
                    minute=minute,
                    typ=typ,
                    spieler=spieler_anzeige,
                    team=heim.name if tor_team_real == "heim" else gast.name,
                    detail=f"{ergebnis.heim_tore}:{ergebnis.gast_tore}",
                )
                ergebnis.ereignisse.append(ereignis)
                if callback:
                    await callback(minute, ereignis, ergebnis)

        # Gelbe Karten
        for spieler in heim_staerken["spieler"]:
            if spieler.name in heim_rot_raus:
                continue
            if minute - gelb_zuletzt.get(spieler.name, -99) < _GELB_ABSTAND:
                continue
            if random.random() < GELB_WAHRSCHEINLICHKEIT.get(spieler.position, 0.05) / 90:
                heim_gelb[spieler.name] = heim_gelb.get(spieler.name, 0) + 1
                spieler.gelbe_karten += 1
                if not ist_pokal:
                    spieler.gelbe_karten_zyklus += 1
                ereignis_typ = "gelb"
                gelb_zuletzt[spieler.name] = minute

                # 2. Gelbe = Rot (im Spiel)
                if heim_gelb[spieler.name] >= 2:
                    ereignis_typ = "rot"
                    heim_rote += 1
                    heim_ausgefallen += 1
                    ergebnis.heim_rote_karten += 1
                    spieler.rote_karten += 1
                    heim_rot_raus.add(spieler.name)
                    if not ist_pokal:
                        dauer = random.randint(_cfg_int("match", "rot_sperre_min"), _cfg_int("match", "rot_sperre_max"))
                        spieler.gesperrt_wochen = dauer

                # Zyklus-Sperre: immer prüfen, auch wenn gleichzeitig Gelb-Rot
                if not ist_pokal and spieler.gelbe_karten_zyklus >= _cfg_int("match", "gelb_zyklus_schwelle"):
                    spieler.gelbe_karten_zyklus = 0
                    if ereignis_typ != "rot":  # Sperre nur wenn kein Gelb-Rot
                        spieler.gesperrt_wochen = 1
                        ereignis_typ = "gelb_sperre"

                e = MatchEreignis(minute=minute, typ=ereignis_typ, spieler=spieler.name, team=heim.name)
                ergebnis.ereignisse.append(e)
                if callback and (ist_menschlich_heim or ist_menschlich_gast):
                    await callback(minute, e, ergebnis)

        for spieler in gast_staerken["spieler"]:
            if spieler.name in gast_rot_raus:
                continue
            if minute - gelb_zuletzt.get(spieler.name, -99) < _GELB_ABSTAND:
                continue
            if random.random() < GELB_WAHRSCHEINLICHKEIT.get(spieler.position, 0.05) / 90:
                gast_gelb[spieler.name] = gast_gelb.get(spieler.name, 0) + 1
                spieler.gelbe_karten += 1
                if not ist_pokal:
                    spieler.gelbe_karten_zyklus += 1
                ereignis_typ = "gelb"
                gelb_zuletzt[spieler.name] = minute

                if gast_gelb[spieler.name] >= 2:
                    ereignis_typ = "rot"
                    gast_rote += 1
                    gast_ausgefallen += 1
                    ergebnis.gast_rote_karten += 1
                    spieler.rote_karten += 1
                    gast_rot_raus.add(spieler.name)
                    if not ist_pokal:
                        dauer = random.randint(_cfg_int("match", "rot_sperre_min"), _cfg_int("match", "rot_sperre_max"))
                        spieler.gesperrt_wochen = dauer

                # Zyklus-Sperre: immer prüfen, auch wenn gleichzeitig Gelb-Rot
                if not ist_pokal and spieler.gelbe_karten_zyklus >= _cfg_int("match", "gelb_zyklus_schwelle"):
                    spieler.gelbe_karten_zyklus = 0
                    if ereignis_typ != "rot":  # Sperre nur wenn kein Gelb-Rot
                        spieler.gesperrt_wochen = 1
                        ereignis_typ = "gelb_sperre"

                e = MatchEreignis(minute=minute, typ=ereignis_typ, spieler=spieler.name, team=gast.name)
                ergebnis.ereignisse.append(e)
                if callback and (ist_menschlich_heim or ist_menschlich_gast):
                    await callback(minute, e, ergebnis)

        # Verletzungen (~2.75% pro Spieler pro Spiel = ~0.03% pro Minute)
        _abbruch = False
        for spieler in heim_staerken["spieler"] + gast_staerken["spieler"]:
            if spieler.verletzt_wochen > 0:  # bereits verletzt → kein zweites Mal
                continue
            if random.random() < _cfg_float("match", "verletzung_wahrscheinlichkeit") / 90:
                basis = random.randint(1, 8)
                delta = random.choice([-1, 0, 0, 1])
                dauer = max(1, min(8, basis + delta))
                spieler.verletzt_wochen = dauer
                spieler.diagnose = DIAGNOSEN.get(dauer, "Verletzung")
                ist_heim_spieler = spieler in heim_staerken["spieler"]
                team_name = heim.name if ist_heim_spieler else gast.name
                if ist_heim_spieler:
                    heim_ausgefallen += 1
                else:
                    gast_ausgefallen += 1
                e = MatchEreignis(
                    minute=minute,
                    typ="verletzung",
                    spieler=spieler.name,
                    team=team_name,
                    detail=f"{spieler.diagnose} ({dauer} Wo.)",
                )
                ergebnis.ereignisse.append(e)
                if callback and (ist_menschlich_heim or ist_menschlich_gast):
                    await callback(minute, e, ergebnis)

        # Abbruch-Prüfung: weniger als 7 Spieler → Spielabbruch
        for team_name, ausgefallen, start_anz in (
            (heim.name, heim_ausgefallen, heim_start_anzahl),
            (gast.name, gast_ausgefallen, gast_start_anzahl),
        ):
            if start_anz - ausgefallen < _MIN_SPIELER:
                ergebnis.abbruch = True
                ergebnis.abbruch_team = team_name
                if callback:
                    e_ab = MatchEreignis(minute=minute, typ="info",
                                        spieler="SPIELABBRUCH", team=team_name,
                                        detail=f"Zu wenig Spieler ({start_anz - ausgefallen})")
                    await callback(minute, e_ab, ergebnis)
                _abbruch = True
                break
        if _abbruch:
            break

        # Konfigurierbare Sekunden pro Spielminute (entfällt bei CPU-only oder Vorspulen)
        if not instant and not (skip_ref and skip_ref[0]):
            await asyncio.sleep(_cfg_float("match", "sekunden_pro_minute"))

    # Abpfiff
    if callback:
        e_abpfiff = MatchEreignis(minute=end_minute, typ="info", spieler="ABPFIFF", team="",
                                  detail=f"{ergebnis.heim_tore}:{ergebnis.gast_tore}")
        await callback(end_minute, e_abpfiff, ergebnis)

    return ergebnis
