"""
Lobby Server - WebSocket-basierter Multiplayer-Server
Verwaltet Räume, Spieler und Spielzustand
"""

import asyncio
import json
import logging
import random
import string
import time
import uuid
from datetime import datetime
from pathlib import Path
import websockets

log = logging.getLogger(__name__)

from engine.settings import getint as _cfg_int, getfloat as _cfg_float, getstr as _cfg_str, getlist as _cfg_list

_VERSION = (Path(__file__).parent.parent / "VERSION").read_text(encoding="utf-8").strip()
_SERVER_ID = str(uuid.uuid4())

_OWNER_EMAILS = set(_cfg_list("dev", "reserved_emails"))
_ADMINS_FILE   = Path(__file__).parent.parent / "data" / "admins.json"
_TESTERS_FILE  = Path(__file__).parent.parent / "data" / "testers.json"

def _ist_admin(google_id: str, email: str) -> bool:
    if email and email.lower() in _OWNER_EMAILS:
        return True
    try:
        if _ADMINS_FILE.exists():
            return google_id in json.loads(_ADMINS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return False

def _ist_tester(google_id: str) -> bool:
    try:
        if _TESTERS_FILE.exists():
            return google_id in json.loads(_TESTERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return False
from engine.game_state import GameState, _VORNAMEN, _NACHNAMEN
from engine.draft import draft_kader
from engine.transfer import Transfermarkt
from engine.spielplan import (
    erstelle_dfb_pokal_bracket, erstelle_europa_saison,
    EUROPA_KALENDER, RUNDEN_FOLGE, HISTORISCHE_SAISON_0,
    bestimme_sieger_einzel, bestimme_sieger_hinrueck, naechste_runde_befuellen,
)
from server.game_saver import GameSaver, MPSaveManager
from server.profile_manager import ProfileManager
from server.logger import log_connect, log_disconnect, log_reconnect, log_chat
import server.netstat as _netstat

# ---------------------------------------------------------------------------
# Elfmeterschießen – Meldungstexte
# {s} = Schütze, {tw} = Torwart
# ---------------------------------------------------------------------------
_ELF_ANLAUF = [
    "{s} legt den Ball auf den Elfmeterpunkt...",
    "{s} nimmt weiten Anlauf...",
    "{s} schaut kurz auf {tw} – dann der Schuss...",
    "{s} visiert die untere linke Ecke an...",
    "{s} visiert die obere rechte Ecke an...",
    "{s} rollt die Schultern, sammelt sich – Anlauf...",
    "{s} läuft langsam an – ein Panenka?",
    "{s} knallt den Ball mit voller Kraft aufs Tor...",
    "{s} nimmt kurzen Anlauf und zieht ab...",
    "{s} schaut links – schießt rechts...",
    "{s} dreht sich kurz zur Mannschaft – dann der Anlauf...",
    "{s} schießt halbhoch in die linke Ecke...",
    "{s} schießt flach unten rechts...",
    "{s} tippt den Ball mittig Richtung Tor...",
    "{s} schaut auf {tw} und wählt die Ecke...",
    "{s} schießt mit Schwung in den langen Winkel...",
    "{s} wuchtet den Ball aus der Drehung...",
    "{s} pumpt sich auf – ruhig, dann der Anlauf...",
    "{s} schaut einmal durch – dann Vollgas...",
    "{s} atmet tief durch und läuft an...",
]
_ELF_TOR = [
    "TOOOOOR! Der Ball ist im Netz!",
    "TREFFER! {tw} hatte keine Chance!",
    "TOR! Unhaltbar – in den Winkel!",
    "DRIN! Präzise in die obere Ecke!",
    "TOOOOOR! Unten links – {tw} greift ins Leere!",
    "Der Ball schlägt ins Netz – TOR!",
    "TREFFER! {tw} taucht in die falsche Ecke!",
    "Knapp unter der Latte – TOR!",
    "Eingeschlagen! Unten rechts – TOOOOOR!",
    "TOR! Der Schuss war nicht zu halten!",
    "DRIN! Das Netz bauscht sich!",
    "Panenka! Mitten rein – TOR!",
    "Eingeschlagen in den Winkel – TOR!",
    "TOR! Machtlos – {tw} greift ins Leere!",
    "Der Ball schlägt unten links ein – TOOOOOR!",
    "TREFFER! Keine Abwehrchance für {tw}!",
    "TOR! Wucht und Präzision – unaufhaltbar!",
    "DRIN! Ein Traumelfmeter!",
    "TOR! Der Ball fliegt unhaltbar in den Winkel!",
    "Knallhart unten rechts – TOOOOOR!",
]
_ELF_GEHALTEN = [
    "{tw} hält! Großartige Parade!",
    "{tw} fischt den Ball aus der Ecke – GEHALTEN!",
    "Der Ball klatscht gegen den Pfosten!",
    "DANEBEN! Der Ball fliegt am Pfosten vorbei!",
    "{tw} wirft sich und kratzt den Ball raus!",
    "PARIERT! {tw} ahnte die Ecke!",
    "Der Ball zischt über das Tor – draußen!",
    "Abgewehrt! {tw} war hellwach!",
    "{tw} hält mit einer Hand – was für ein Reflex!",
    "An die Latte! Und wieder raus!",
    "GEHALTEN! {tw} bleibt in der Mitte – Panenka abgefangen!",
    "Drüber! Der Ball geht über die Latte!",
    "{tw} taucht ab und lenkt den Ball zur Seite!",
    "GEHALTEN! {tw} lässt {s} verzweifeln!",
    "Der Ball klatscht gegen den linken Pfosten!",
    "{tw} streckt sich voll aus und hält!",
    "Vergeben! Der Schuss geht am Tor vorbei!",
    "{tw} reagiert blitzschnell und kratzt den Ball raus!",
    "Die Innenstange – und wieder raus!",
    "{tw} ahnt die Ecke und lenkt mit den Fingerspitzen ab!",
]


def _spieler_dict(s, gelistet=False):
    return {
        "name": s.name, "position": s.position,
        "staerke": s.staerke_label, "nationalitaet": s.nationalitaet,
        "verletzt_wochen": s.verletzt_wochen, "gesperrt_wochen": s.gesperrt_wochen,
        "diagnose": s.diagnose,
        "gelbe_karten": s.gelbe_karten, "gelbe_karten_zyklus": s.gelbe_karten_zyklus,
        "rote_karten": s.rote_karten,
        "gehalt": s.gehalt, "marktwert": s.marktwert,
        "tore_liga": s.tore_liga, "tore_pokal": s.tore_pokal,
        "gelistet": gelistet,
    }


def _gelistet_namen(lobby) -> set:
    """Set of player names currently listed on the transfer market."""
    if lobby and lobby.transfermarkt:
        return {s.name for s, p, vk, w in lobby.transfermarkt.gelistete_spieler}
    return set()


def _tab_data_gs(gs, liga: int) -> list:
    return [{"name": t.name, "spiele": t.spiele, "siege": t.siege,
             "unentschieden": t.unentschieden, "niederlagen": t.niederlagen,
             "tore": t.tore, "gegentore": t.gegentore, "punkte": t.punkte}
            for t in gs.get_tabelle(liga)]


def generiere_lobby_code(laenge: int = 6) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=laenge))


# ── News-Ticker Meldungsvorlagen ──────────────────────────────────────────────

_KAUF_TEXTE = [
    "{team} verpflichtet {spieler} ({pos}) – Wechsel für {preis} perfekt!",
    "Neuzugang bei {team}: {spieler} wechselt für {preis}",
    "{team} legt {preis} auf den Tisch und sichert sich {spieler}",
    "Transfercoup! {team} holt {spieler} für {preis}",
    "{spieler} wechselt für {preis} zu {team}",
    "{team} investiert {preis} und verpflichtet {spieler} ({pos})",
    "Deal ist durch: {spieler} kostet {team} stolze {preis}",
    "Überraschungstransfer: {team} holt {spieler} für {preis}",
    "{team} verstärkt sich mit {spieler} – Ablöse: {preis}",
    "{team} schlägt auf dem Transfermarkt zu – {spieler} für {preis}",
    "Einigung erzielt: {spieler} ({pos}) wechselt für {preis} zu {team}",
    "{preis} für {spieler}: {team} rüstet kräftig auf",
    "Vollzogen! {spieler} trägt künftig das Trikot von {team}",
    "{team} und {spieler} einigen sich – Ablöse: {preis}",
    "Schnelle Nummer: {team} schnappt sich {spieler} für {preis}",
    "Perfekt! {spieler} unterschreibt bei {team} für {preis}",
    "Der Hammer: {spieler} ({pos}) wechselt für {preis} zu {team}",
    "{preis} – so viel lässt sich {team} den Transfer von {spieler} kosten",
    "Frischer Wind bei {team}: {spieler} kommt für {preis}",
    "Offiziell: {spieler} ist ab sofort Spieler von {team} ({preis})",
    "Transfermarkt heiß gelaufen: {team} sichert sich {spieler} für {preis}",
    "{spieler} tauscht das Trikot – {team} zahlt {preis}",
    "Bombe geplatzt: {spieler} ({pos}) wechselt zu {team} für {preis}",
    "{team} greift tief in die Tasche: {spieler} für {preis} verpflichtet",
]

_LIST_TEXTE = [
    "{spieler} von {team} zum Verkauf angeboten",
    "Trennung bei {team}: {spieler} sucht neuen Verein",
    "{spieler} steht bei {team} nicht mehr im Plan",
    "{team} will {spieler} abgeben – Spieler auf der Transferliste",
    "Abgang bahnt sich an: {spieler} verlässt {team}",
    "{spieler} von {team} ab sofort auf der Transferliste",
    "{team} setzt {spieler} auf die Verkaufsliste",
    "Überraschende Trennung: {team} trennt sich von {spieler}",
    "{team} macht Platz im Kader – {spieler} steht zum Verkauf",
    "Wechselwunsch: {spieler} verlässt {team} auf eigenen Wunsch",
    "{spieler} verlässt {team} – Transfer gesucht",
    "Kaderbereinigung bei {team}: {spieler} wird abgegeben",
    "{team} listet {spieler} auf dem Markt – Angebote willkommen",
    "Kapitalmaßnahme: {team} verabschiedet sich von {spieler}",
    "{spieler} ist nicht mehr Teil der Planung bei {team}",
    "Frischer Schnitt: {team} bietet {spieler} feil",
    "Schaufenster: {team} stellt {spieler} zum Verkauf",
    "{spieler} sucht nach seiner Zeit bei {team} einen neuen Club",
    "Keine Zukunft mehr: {spieler} verlässt {team}",
    "{team} stößt {spieler} ab – Wechsel in Kürze erwartet",
]

_POKAL_WEITER_TEXTE = [
    "{team} zieht in die nächste Runde des {pokal} ein",
    "Weiterkommen für {team} im {pokal}!",
    "{team} übersteht die Hürde im {pokal}",
    "Knappe Kiste, aber {team} ist weiter im {pokal}",
    "{team} setzt sich durch und kommt weiter im {pokal}",
    "{team} überzeugt im {pokal} – nächste Runde gesichert!",
    "Souverän: {team} marschiert im {pokal} weiter",
    "Weiter! {team} bleibt im {pokal} am Ball",
    "{team} besteht die Prüfung im {pokal}",
    "{team} kämpft sich in die nächste {pokal}-Runde",
    "Nächste Runde für {team} im {pokal}!",
    "{team} meistert die Aufgabe im {pokal}",
    "Weiterhin dabei: {team} setzt sich im {pokal} durch",
    "Mission erfüllt: {team} im {pokal} weiter",
    "{team} ist noch dabei – {pokal}-Reise geht weiter",
    "Hart erkämpft: {team} schafft den Einzug in die nächste {pokal}-Runde",
    "{team} bleibt {pokal}-Teilnehmer – nächste Runde!",
    "Knapper Sieg reicht: {team} weiter im {pokal}",
    "Aufatmen bei {team} – {pokal}-Abenteuer geht weiter!",
    "Runde für Runde: {team} marschiert im {pokal}",
]

_POKAL_AUS_TEXTE = [
    "Bitteres Aus für {team} im {pokal}!",
    "{team} scheitert im {pokal}",
    "Überraschung! {team} fliegt aus dem {pokal}",
    "Enttäuschung bei {team}: Aus im {pokal}",
    "{team} muss den {pokal} vorzeitig beenden",
    "Drama im {pokal}: {team} ist draußen",
    "Früh ist Schluss: {team} scheidet im {pokal} aus",
    "Keine Chance: {team} im {pokal} gescheitert",
    "{team} stolpert im {pokal} und scheidet überraschend aus",
    "Trauriges Ende für {team} im {pokal}",
    "Vorzeitiges Ende der {pokal}-Reise für {team}",
    "{team} kann den {pokal} abhaken – Ausscheiden bestätigt",
    "Pleite im {pokal}: {team} ist raus!",
    "Das war's: {team} scheitert im {pokal}",
    "Niederlage besiegelt das {pokal}-Aus von {team}",
    "Herber Dämpfer: {team} fliegt aus dem {pokal}",
    "{team} ohne Glück im {pokal} – Aus in der aktuellen Runde",
    "Schluss, Aus, Ende: {team} im {pokal} ausgeschieden",
    "{team} muss die {pokal}-Hoffnungen begraben",
    "Kein Glück für {team} – {pokal}-Kampagne beendet",
]

_POKAL_SIEG_TEXTE = [
    "Pokalheld! {team} gewinnt den {pokal}!",
    "{team} triumphiert im {pokal}-Finale!",
    "Historisch: {team} krönt sich zum {pokal}-Sieger!",
    "{team} holt den Titel im {pokal}!",
    "Unvergesslich: {team} ist {pokal}-Champion!",
    "Der {pokal} geht an {team} – Titelgewinn!",
    "Was für ein Finale! {team} gewinnt den {pokal}!",
    "{team} steht oben! {pokal}-Titel für die Mannschaft!",
    "Jubel ohne Ende: {team} ist {pokal}-Sieger!",
    "Sensation! {team} holt den {pokal}!",
    "Endlich! {team} hebt den {pokal} in die Höhe!",
    "{team} ist unaufhaltbar – {pokal}-Triumph!",
    "Der Traum wird wahr: {team} gewinnt den {pokal}!",
    "Unsterblich: {team} krönt eine starke Saison mit dem {pokal}!",
]

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

# ── Pressestimmen & Spieltag-Schlagzeilen ─────────────────────────────────────

_PRESSE_SIEG_HOCH = [   # ≥3 Tore Unterschied
    "Torfestival! {heim} schlägt {gast} mit {ht}:{gt}",
    "Kantersieg: {heim} demontiert {gast} {ht}:{gt}",
    "'Wir haben heute alles richtig gemacht' – Stimmen nach dem {ht}:{gt} von {heim}",
    "Klatsche für {gast}: {heim} feiert {ht}:{gt}",
    "{gast} chancenlos – {heim} siegt souverän {ht}:{gt}",
    "Gala-Vorstellung: {heim} überrollt {gast} mit {ht}:{gt}",
    "Torshow in der Liga: {heim} lässt {gast} beim {ht}:{gt} keine Chance",
    "Machtdemonstration von {heim}: {gast} mit {ht}:{gt} abgefertigt",
    "{ht}:{gt}! {heim} schießt {gast} in Grund und Boden",
    "'So ein Ergebnis tut weh' – {gast} nach dem {ht}:{gt} bei {heim}",
]
_PRESSE_SIEG_KNAPP = [  # 1–2 Tore Unterschied
    "Knappe Kiste: {heim} setzt sich {ht}:{gt} gegen {gast} durch",
    "'Drei Punkte sind drei Punkte' – {heim} nach dem {ht}:{gt}",
    "Arbeitsieg für {heim}: {ht}:{gt} gegen {gast} reicht",
    "{heim} kämpft sich zu drei Punkten – {ht}:{gt} gegen {gast}",
    "Knapper Sieg: {heim} schlägt {gast} mit {ht}:{gt}",
    "Wichtige drei Punkte: {heim} setzt sich {ht}:{gt} durch",
    "'Ein hartes Stück Arbeit' – {heim} nach dem {ht}:{gt}-Sieg",
    "{ht}:{gt} – {heim} holt die Punkte, {gast} geht leer aus",
    "{heim} lässt sich nicht aus der Ruhe bringen: {ht}:{gt} gegen {gast}",
    "'Wir wussten, dass es schwer wird' – {heim} nach dem {ht}:{gt}",
]
_PRESSE_UNENTSCHIEDEN = [
    "Punkteteilung: {heim} und {gast} trennen sich {ht}:{gt}",
    "Unentschieden in der Bundesliga: {heim} – {gast} {ht}:{gt}",
    "'Gerecht geteilt' – {heim} und {gast} nach dem {ht}:{gt}",
    "Keine Sieger: {heim} gegen {gast} {ht}:{gt}",
    "Remis: {heim} und {gast} teilen die Punkte ({ht}:{gt})",
    "{heim} und {gast} einigen sich auf {ht}:{gt}",
    "'Für uns war mehr drin' – beide Seiten nach dem {ht}:{gt}",
    "Abgestecktes Gelände: {heim} gegen {gast} endet {ht}:{gt}",
    "{ht}:{gt} – keiner kann sich entscheidend durchsetzen",
    "Spannung ohne Sieger: {heim} – {gast} {ht}:{gt}",
]
_PRESSE_NIEDERLAGE_KNAPP = [  # 1–2 Tore Unterschied
    "Knappe Niederlage: {gast} bei {heim} mit {ht}:{gt} geschlagen",
    "Bitterer Abend für {gast}: {ht}:{gt} gegen {heim}",
    "'Wir haben heute zu wenig gezeigt' – {gast} nach dem {ht}:{gt}",
    "{ht}:{gt} – {gast} nimmt beim {heim} nichts mit",
    "Niederlage trotz Einsatz: {gast} verliert {ht}:{gt} bei {heim}",
    "'Das war nicht unser Tag' – {gast} nach dem {ht}:{gt} bei {heim}",
    "{heim} setzt sich durch: {gast} verliert knapp {ht}:{gt}",
    "'Wir müssen das schnell abhaken' – {gast} nach dem {ht}:{gt}",
    "{gast} trotz Kampf geschlagen: {heim} holt drei Punkte ({ht}:{gt})",
    "Miserable Ausbeute: {gast} kehrt mit einer {ht}:{gt}-Niederlage heim",
]
_PRESSE_NIEDERLAGE_HOCH = [  # ≥3 Tore Unterschied
    "Debakel! {gast} geht bei {heim} mit {ht}:{gt} unter",
    "Ernüchterung bei {gast}: {ht}:{gt} gegen {heim}",
    "'Das war nichts' – {gast} nach dem {ht}:{gt}-Debakel",
    "Schützenfest gegen {gast}: {heim} feiert {ht}:{gt}",
    "{gast} in der Krise: {ht}:{gt}-Klatsche bei {heim}",
    "Bundesliga-Spektakel: {heim} überrollt {gast} mit {ht}:{gt}",
    "Keine Gegenwehr: {gast} geht bei {heim} {ht}:{gt} unter",
    "Blamage für {gast}: {ht}:{gt}-Niederlage bei {heim}",
    "{ht}:{gt}! {gast} kann {heim} nicht stoppen",
    "'Wir müssen das schleunigst aufarbeiten' – {gast} nach dem {ht}:{gt}",
]
_HEADLINE_SPITZE = [
    "{leader} thront in der Bundesliga – {punkte} Punkte aus {spiele} Spielen",
    "Bundesliga-Führung: {leader} mit {abstand} Punkt(en) Vorsprung auf {zweiter}",
    "{leader} weiter vorne – Verfolger {zweiter} hat {abstand} Punkt(e) Rückstand",
    "Tabellenführer {leader}: die Konkurrenz schaut machtlos zu",
    "{leader} an der Spitze – {abstand} Punkte trennen vom Verfolger {zweiter}",
    "Spitzenreiter {leader} mit {punkte} Punkten – {zweiter} dahinter",
]
_HEADLINE_ABSTIEG = [
    "Abstiegskampf: {kellerkind} mit nur {punkte} Punkten auf Platz {platz}",
    "{kellerkind} im Keller – Abstieg droht nach {spiele} Spielen",
    "Wer steigt ab? {kellerkind} aktuell auf Relegationsplatz",
    "Krise im Tabellenkeller: {kellerkind} kämpft um den Ligaverbleib",
    "{kellerkind} zittert: zu wenige Punkte, zu wenig Zeit",
    "Bundesliga-Alarm bei {kellerkind}: Abstiegszone nicht verlassen",
]
_HEADLINE_SPIELTAG = [
    "{spieltag}. Spieltag: {tore_gesamt} Tore – Bundesliga-Runde mit Spektakel",
    "Rückblick Spieltag {spieltag}: {sieger} mit dem höchsten Sieg der Runde",
    "Spieltag {spieltag} abgehakt: {tore_gesamt} Treffer in der Bundesliga",
    "Runde {spieltag} abgeschlossen – {sieger} sorgt für Aufsehen",
]
_MEILENSTEIN_MEISTER = [
    "TITEL PERFEKT! {team} ist nicht mehr einzuholen – die Meisterschale gehört ihnen!",
    "MEISTER! {team} sichert die Meisterschale – der Bundesliga-Champion steht fest!",
    "ES IST VOLLBRACHT! {team} krönt eine überragende Saison – Meister 83/84, kein Aufholen mehr möglich!",
    "DIE SCHALE GEHÖRT {team}! Kein Rivale kann den Titel noch verhindern – Glückwunsch!",
    "BUNDESLIGA-CHAMPION {team}: Mit {punkte} Punkten uneinholbar an der Spitze – der Titel ist perfekt.",
    "HISTORISCHER MOMENT! {team} gewinnt die Meisterschaft – kein Restprogramm kann das noch ändern.",
    "MEISTER 83/84: {team} steht fest – kein Verfolger kommt mehr ran.",
    "Finale Grande für {team}: Der Meistertitel ist nicht mehr zu nehmen, Feierlaune gerechtfertigt!",
]
_MEILENSTEIN_UEFA = [
    "EUROPA-TICKET! {team} hat den UEFA-Pokal-Startplatz sicher – internationale Bühne wartet.",
    "QUALIFIKATION PERFEKT! {team} spielt nächste Saison im UEFA-Pokal – kein Verfolger holt mehr auf.",
    "{team} hat Europa gebucht – der UEFA-Pokal-Platz ist nicht mehr zu nehmen.",
    "EUROPACUP-GARANTIE für {team}: Der internationale Startplatz steht unwiderruflich fest.",
    "Kein Weg mehr dran vorbei: {team} ist für den UEFA-Pokal qualifiziert.",
    "{team} freut sich auf europäischen Fußball – das Ticket ist unverrückbar gelöst.",
    "INTERNAT. BÜHNE GESICHERT: {team} spielt nächste Saison im UEFA-Pokal – Platz nicht mehr zu nehmen.",
    "{team} hat sich den UEFA-Pokal-Platz gesichert – Glückwunsch nach Europa!",
]
_MEILENSTEIN_ABSTIEG = [
    "BITTERE WAHRHEIT: {team} steht als Absteiger fest – der Klassenerhalt ist nicht mehr möglich.",
    "DER ABSTIEG IST BESIEGELT! {team} verlässt die Bundesliga – kein Sieg kann das noch ändern.",
    "{team} geht in die 2. Liga – selbst mit allen Siegen ist die Rettung nicht mehr drin.",
    "SCHLUSSPFIFF IN DER BUNDESLIGA: {team} steigt ab – kein Wunder mehr möglich.",
    "Bitteres Ende: {team} ist abgestiegen – daran ändert sich nichts mehr.",
    "ABSTIEG STEHT FEST: {team} kann sich nicht mehr retten – der Gang in die 2. Liga steht fest.",
    "KEINE HOFFNUNG MEHR: {team} ist Bundesliga-Absteiger – die letzten Spieltage werden zur Abschiedsrunde.",
    "Trauriger Rekord für {team}: Der Abstieg ist besiegelt, das Restprogramm nur noch Formsache.",
]


class Lobby:
    def __init__(self, code: str, ersteller_id: str):
        self.code = code
        self.ersteller_id = ersteller_id
        self.spieler: dict = {}        # manager_id -> {ws, name, team, google_id, email}
        self.game_state: GameState = None
        self.transfermarkt: Transfermarkt = None
        self.phase = "warten"          # warten, vereinswahl, management, spiel
        self.max_spieler = 4
        self.bereit: set = set()       # manager_ids die "Weiter" geklickt haben
        # Aktuelle Transferangebote: manager_id -> {spieler_name: (Spieler, preis)}
        self.transfer_session: dict = {}
        # Game persistence
        self.game_key: str = None      # Eindeutiger Spielidentifier
        self.session_chat: list = []   # Chatverlauf für diese Session
        # Ausstehende Pokal-Events nach dem Liga-Spieltag (wettbewerb, runde, leg)
        self.pending_pokal_events: list = []
        # News-Ticker: gesammelte Meldungen für die nächste Management-Phase
        self.news_items: list = []
        # Ergebnisse des zuletzt gespielten Spieltags (für Pressestimmen)
        self.letzte_ergebnisse: list = []
        # Bereits gemeldete Tabellen-Meilensteine (verhindert Doppelanzeigen)
        self.gemeldet_tabellen_ereignisse: set = set()
        # Vorspul-Flag: [False] -> auf True setzen um laufende Simulation zu beschleunigen
        self.sim_skip: list = [False]
        # Stummgeschaltete Manager-IDs (chat_befehl /mute)
        self.muted: set = set()
        # Multiplayer-Spielstand: erwartete Manager [{google_id, name, team}]
        self.mp_erwartete_manager: list = []
        # True wenn diese Lobby aus einem MP-Speicherstand geladen wurde
        self.mp_ist_geladen: bool = False
        # Google-ID des Erstellers (für MP-Save-Berechtigung)
        self.ersteller_google_id: str = None
        # Laufender Phase-Task (für sauberes Shutdown)
        self.phase_task: "asyncio.Task | None" = None
        # Schließ-Task nach Ersteller-Disconnect (wartet auf Reconnect)
        self.close_task: "asyncio.Task | None" = None
        # Debug-Flags (nur Dev-Admin): Verlängerung / Elfmeter erzwingen
        self.debug_force_vl: list = [False]
        self.debug_force_elf: list = [False]
        # Zeitstempel wenn "weiter"-Phase begann (für Reconnect-Timer-Berechnung)
        self.weiter_ts: float = None

    def spieler_hinzufügen(self, manager_id: str, ws, name: str, google_id: str = None, email: str = None) -> bool:
        if len(self.spieler) >= self.max_spieler:
            return False
        self.spieler[manager_id] = {"ws": ws, "name": name, "team": None, "google_id": google_id, "email": email}
        return True

    def spieler_entfernen(self, manager_id: str):
        self.spieler.pop(manager_id, None)

    def spieler_disconnected(self, manager_id: str):
        """Markiert Spieler als offline (ws=None), behält ihn aber in der Lobby für Reconnect."""
        if manager_id in self.spieler:
            self.spieler[manager_id]["ws"] = None

    def online_spieler(self) -> dict:
        """Gibt nur Spieler zurück die aktuell verbunden sind (ws != None)."""
        return {mid: info for mid, info in self.spieler.items() if info.get("ws") is not None}

    def alle_bereit(self) -> bool:
        online = self.online_spieler()
        if not online:
            return False
        afk_mids = {mid for mid, info in online.items() if info.get("afk")}
        bereit_effektiv = self.bereit | afk_mids
        return len(bereit_effektiv) >= len(online)

    async def broadcast(self, nachricht: dict):
        """Sendet Nachricht an alle Spieler in der Lobby"""
        daten = json.dumps(nachricht, ensure_ascii=False)
        for info in self.spieler.values():
            try:
                await info["ws"].send(daten)
            except Exception:
                pass

    async def sende_an(self, manager_id: str, nachricht: dict):
        """Sendet Nachricht an einen einzelnen Spieler"""
        info = self.spieler.get(manager_id)
        if info:
            try:
                await info["ws"].send(json.dumps(nachricht, ensure_ascii=False))
            except Exception:
                pass

    def spiel_starten(self, team_auswahl: dict):
        """Initialisiert den Spielzustand und startet den Draft"""
        from engine.game_state import erstelle_international_team
        self.game_state = GameState(lobby_code=self.code)
        gs = self.game_state
        menschliche_teams = {team: mid for mid, team in team_auswahl.items()}
        draft_kader(gs, menschliche_teams)
        self.transfermarkt = Transfermarkt(gs)
        self.transfermarkt.neue_woche()
        from engine.cpu_ai import cpu_woche as _cpu_woche
        _cpu_woche(gs, self.transfermarkt, news_items=self.news_items)
        self.transfermarkt.neue_woche_angebote()
        self.phase = "management"

        # ── DFB-Pokal: Oberliga-Pool als synthetische Teams ─────────────────
        bl1_teams = [n for n, t in gs.teams.items() if t.liga == 1]
        bl2_teams = [n for n, t in gs.teams.items() if t.liga == 2]
        liga3_pool = getattr(gs, 'liga3_pool', [])
        oberliga_teams = []
        for entry in liga3_pool:
            name = entry["name"] if isinstance(entry, dict) else entry
            smin = entry["staerke_min"] if isinstance(entry, dict) else 20
            smax = entry["staerke_max"] if isinstance(entry, dict) else 50
            t = erstelle_international_team(name, smin, smax, auslaender=False)
            t.liga = 3
            gs.europa_teams[name] = t
            oberliga_teams.append(name)
        gs.dfb_pokal_bracket = erstelle_dfb_pokal_bracket(bl1_teams, bl2_teams, oberliga_teams)

        # ── Europapokale (historische Saison-0-Daten) ───────────────────────
        # Manager-Teams sind ausschließlich für den DFB-Pokal qualifiziert.
        # Jeder historische Qualifikant, der ein Manager-Team ist, wird durch
        # ein zufälliges starkes CPU-BL1-Team ersetzt.
        manager_teams = set(team_auswahl.values())
        cpu_bl1 = [n for n, t in gs.teams.items()
                   if t.liga == 1 and n not in manager_teams]
        benutzt: set = set()

        def _cpu_ersatz():
            """Wählt zufälliges noch nicht benutztes CPU-BL1-Team."""
            verfuegbar = [t for t in cpu_bl1 if t not in benutzt]
            if not verfuegbar:
                return None
            pick = random.choice(verfuegbar)
            benutzt.add(pick)
            return pick

        def _bereinige(name):
            """Ersetzt Manager-Team-Namen durch CPU-Ersatz."""
            if name in manager_teams:
                return _cpu_ersatz()
            benutzt.add(name)
            return name

        meister_q      = _bereinige(HISTORISCHE_SAISON_0["meister_bl1"])
        pokalsieger_q  = _bereinige(HISTORISCHE_SAISON_0["dfb_pokalsieger"])
        pokalfinalist_q = _bereinige(HISTORISCHE_SAISON_0["dfb_pokalfinalist"])

        uefacup_q = []
        for t in HISTORISCHE_SAISON_0["uefacup_qualifikanten"][:4]:
            ersatz = _bereinige(t)
            if ersatz:
                uefacup_q.append(ersatz)

        qualifikanten = {
            "meister_bl1":            meister_q,
            "dfb_pokalsieger":        pokalsieger_q,
            "dfb_pokalfinalist":      pokalfinalist_q,
            "ist_pokalsieger_meister": HISTORISCHE_SAISON_0["ist_pokalsieger_meister"],
            "uefacup_qualifikanten":  uefacup_q,
        }
        erstelle_europa_saison(gs, qualifikanten)

        # Create game save
        managers_info = {}
        for manager_id, sp_info in self.spieler.items():
            managers_info[manager_id] = {
                "google_id": sp_info.get("google_id"),
                "email": sp_info.get("email"),
                "name": sp_info.get("name"),
                "team": sp_info.get("team")
            }

        self.game_key = GameSaver.create_game_save(self, self.game_state, managers_info)

        # Add ongoing game to each manager's profile
        for google_id, sp_info in [(sp["google_id"], sp) for sp in self.spieler.values()]:
            if google_id:
                ProfileManager.add_ongoing_game(google_id, self.game_key)


GLOBAL_CHAT_FILE = Path(__file__).parent.parent / "data" / "global_chat.json"
GLOBAL_CHAT_MAX = 200


def _load_global_chat() -> list:
    try:
        if GLOBAL_CHAT_FILE.exists():
            with open(GLOBAL_CHAT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return data[-GLOBAL_CHAT_MAX:]
    except Exception:
        pass
    return []


def _save_global_chat(chat: list):
    try:
        GLOBAL_CHAT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(GLOBAL_CHAT_FILE, 'w', encoding='utf-8') as f:
            json.dump(chat, f, ensure_ascii=False)
    except Exception:
        pass


import re as _re
_LOBBY_CODE_RE = _re.compile(r'\b[A-Z0-9]{6}\b')

def _entferne_lobby_code_aus_chat(chat: list, code: str) -> bool:
    """Entfernt Nachrichten die einen bestimmten Lobby-Code enthalten aus dem Chat.
    Gibt True zurück wenn etwas entfernt wurde."""
    vorher = len(chat)
    chat[:] = [m for m in chat if code not in _LOBBY_CODE_RE.findall(m.get("text", ""))]
    return len(chat) < vorher


class LobbyServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.lobbys: dict = {}         # code -> Lobby
        self.verbindungen: dict = {}   # ws -> {lobby_code, manager_id, google_id}
        self.oauth_client = None       # Will be set by main.py
        self.online_users: dict = {}   # manager_id -> {ws, name, google_id, lobby_code}
        self.alle_ws: set = set()      # Alle aktiven WebSocket-Verbindungen (für Chat-Broadcast)
        self.global_chat: list = _load_global_chat()    # Letzte 30 globale Chat-Nachrichten (persistent)
        self.global_muted: set = set()  # Manager-IDs die im globalen Chat stummgeschaltet sind
        self._neustart = False         # True wenn shutdown durch Admin-Neustart ausgelöst
        self._grace_tasks: dict = {}   # manager_id -> asyncio.Task (AFK grace period)

    async def start(self):
        class _WsFilter(logging.Filter):
            def filter(self, record):
                msg = record.getMessage()
                if "opening handshake failed" in msg or "did not receive" in msg:
                    return False
                return True

        logging.getLogger("websockets.server").addFilter(_WsFilter())

        async def _process_request(connection, request):
            upgrade = request.headers.get("Upgrade", "")
            if upgrade.lower() != "websocket":
                ip = connection.remote_address[0] if connection.remote_address else "?"
                log.warning(f"HTTP-Anfrage auf WS-Port von {ip}: {request.method} {request.path}")
            return None

        log.info(f"WebSocket-Server startet auf {self.host}:{self.port}")
        self._shutdown_event = asyncio.Event()
        async with websockets.serve(self.handler, self.host, self.port, process_request=_process_request):
            await self._shutdown_event.wait()

    async def shutdown(self):
        """Speichert alle aktiven Spielstände und fährt den Server herunter."""
        log.info("Server wird beendet – speichere alle aktiven Spielstände...")
        if self._neustart:
            meldung = "Server wird neu gestartet. Gleich wieder da!"
        else:
            meldung = "Server wird heruntergefahren. Tschüss!"
        await self._broadcast_alle({
            "typ": "server_shutdown",
            "neustart": self._neustart,
            "nachricht": meldung,
        })

        # Läuft gerade eine Simulation? Zuerst zu Ende bringen (Anti-Cheat).
        for lobby in self.lobbys.values():
            task = lobby.phase_task
            if task and not task.done() and lobby.phase == "spiel":
                log.info(f"Simuliere laufenden Spieltag in Lobby {lobby.code} zu Ende...")
                lobby.sim_skip[0] = True
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=30.0)
                except (asyncio.TimeoutError, Exception):
                    pass

        saved = 0
        for lobby in self.lobbys.values():
            if lobby.game_key and lobby.game_state:
                try:
                    mp_label = f" (MP, Lobby {lobby.code})" if lobby.ersteller_google_id else ""
                    log.info(f"Speichere Spielstand {lobby.game_key}{mp_label}...")
                    GameSaver.save_game_state(lobby.game_key, lobby.game_state,
                                              session_chat=lobby.session_chat)
                    self._mp_autosave(lobby)
                    saved += 1
                except Exception as e:
                    log.error(f"Fehler beim Speichern von {lobby.game_key}: {e}")
        if saved:
            log.info(f"{saved} Spielstand{'e' if saved != 1 else ''} gespeichert.")
        else:
            log.info("Keine aktiven Spielstände zu speichern.")
        self._shutdown_event.set()

    async def save_all_games(self):
        """Speichert alle aktiven Spielstände ohne den Server herunterzufahren."""
        saved = 0
        for lobby in self.lobbys.values():
            if lobby.game_key and lobby.game_state:
                try:
                    mp_label = f" (MP, Lobby {lobby.code})" if lobby.ersteller_google_id else ""
                    log.info(f"[Manuell] Speichere Spielstand {lobby.game_key}{mp_label}...")
                    GameSaver.save_game_state(lobby.game_key, lobby.game_state,
                                              session_chat=lobby.session_chat)
                    self._mp_autosave(lobby)
                    saved += 1
                except Exception as e:
                    log.error(f"Fehler beim Speichern von {lobby.game_key}: {e}")
        if saved:
            log.info(f"[Manuell] {saved} Spielstand{'e' if saved != 1 else ''} gespeichert.")
        else:
            log.info("[Manuell] Keine aktiven Spielstände zu speichern.")

    def _verify_auth_token(self, token: str):
        """
        Verify auth token and return (manager_id, google_id) or (None, None)
        """
        if not self.oauth_client:
            # OAuth not configured - allow for backward compatibility
            return None, None
        return self.oauth_client.verify_auth_token(token)

    @staticmethod
    async def _ws_send(ws, daten: str):
        """ws.send mit TX-Zähler."""
        _netstat.tx += len(daten.encode())
        await ws.send(daten)

    async def _broadcast_alle(self, nachricht: dict):
        """Sendet Nachricht an alle aktiven WebSocket-Verbindungen"""
        daten = json.dumps(nachricht, ensure_ascii=False)
        for ws in list(self.alle_ws):
            try:
                await self._ws_send(ws, daten)
            except:
                pass

    def _mp_autosave(self, lobby: "Lobby"):
        """Aktualisiert den MP-Speicherstand parallel zum regulären Autosave.
        Fallback: legt den Slot neu an, falls er nicht mehr existiert."""
        if not (lobby.ersteller_google_id and lobby.game_key and lobby.game_state):
            return
        updated = MPSaveManager.update_by_game_key(
            lobby.ersteller_google_id, lobby.game_key, lobby.game_state)
        if not updated:
            # Kein passender Slot gefunden – als Fallback neu anlegen
            _mp_managers = [
                {"google_id": sp.get("google_id"), "name": sp.get("name"), "team": sp.get("team")}
                for sp in lobby.spieler.values() if sp.get("google_id") and sp.get("team")
            ]
            if len(_mp_managers) >= 2:
                log.info(f"MP-Slot für {lobby.game_key} nicht gefunden – lege neu an.")
                MPSaveManager.create_for_game(
                    lobby.ersteller_google_id, lobby.game_key, _mp_managers, lobby.game_state)

    def _mp_lobby_status(self, lobby: "Lobby") -> dict:
        """Gibt den aktuellen MP-Beitrittsstatus zurück: welche erwarteten Manager sind online."""
        joined_gids = {sp.get("google_id") for sp in lobby.spieler.values()}
        return {
            "erwartete": [
                {**m, "beigetreten": m.get("google_id") in joined_gids}
                for m in lobby.mp_erwartete_manager
            ]
        }

    def _profil_daten(self, google_id: str) -> dict | None:
        """Gibt kompakte Profildaten für eine Google-ID zurück."""
        if not google_id:
            return None
        profile = ProfileManager.get_profile(google_id)
        if not profile:
            return None
        stats = profile.get("statistics", {})
        erf = profile.get("erfolge", {})
        history = profile.get("game_history", [])
        positions = [g["final_position"] for g in history if g.get("final_position")]
        bs = stats.get("beste_saison")
        saisons = erf.get("saisons", 0)
        wins = stats.get("wins", 0)
        email = profile.get("email", "")
        return {
            "wins":     wins,
            "draws":    stats.get("draws", 0),
            "losses":   stats.get("losses", 0),
            "total_games": stats.get("total_games", 0),
            "match_siege":        stats.get("match_siege", 0),
            "match_unentschieden": stats.get("match_unentschieden", 0),
            "match_niederlagen":  stats.get("match_niederlagen", 0),
            "saisons":  saisons,
            "best_pos": min(positions) if positions else None,
            "bild":     profile.get("profile_image", ""),
            "nickname": profile.get("nickname", ""),
            "erfolge":  erf,
            "lieblingsverein": profile.get("lieblingsverein"),
            "tore":            stats.get("tore", 0),
            "gegentore":       stats.get("gegentore", 0),
            "bester_kontostand": stats.get("bester_kontostand", 0),
            "beste_saison":    bs,
            "is_admin": _ist_admin(google_id, email),
            "is_tester": _ist_tester(google_id),
            "is_dev": email in _OWNER_EMAILS,
            "email": email,
            "last_seen": profile.get("last_seen", ""),
            "radio_settings": profile.get("radio_settings", {}),
            "theme": profile.get("theme", ""),
            "google_id": google_id,
        }

    async def _broadcast_online_spieler(self):
        """Sendet aktualisierte Online-Spieler-Liste mit Profil-Daten an alle"""
        spieler_liste = []
        for u in self.online_users.values():
            entry = {"name": u["name"]}
            if u.get("afk"):
                entry["afk"] = True
            # Status bestimmen
            lc = u.get("lobby_code")
            if lc:
                lobby = self.lobbys.get(lc)
                entry["status"] = "IM SPIEL" if (lobby and lobby.game_state) else "IN LOBBY"
            else:
                entry["status"] = ""
            gid = u.get("google_id")
            if not gid:
                entry["gast"] = True
            else:
                entry["google_id"] = gid
                p = self._profil_daten(gid)
                email = (p.get("email") if p else None) or u.get("email", "")
                if email in _OWNER_EMAILS:
                    entry["dev"] = True
                elif _ist_admin(gid, email):
                    entry["admin"] = True
                elif _ist_tester(gid):
                    entry["tester"] = True
                if p:
                    p["status"] = entry.get("status", "")
                    entry["profil"] = p
            spieler_liste.append(entry)
        # Sortierung: Dev zuerst, dann Admins, dann Tester, dann Rest
        spieler_liste.sort(key=lambda x: 0 if x.get("dev") else (1 if x.get("admin") else (2 if x.get("tester") else 3)))
        # Lobby-Codes für Lobbys in der Wartephase (beitretbar für neue Spieler)
        joinbare_codes = [
            lb.code for lb in self.lobbys.values()
            if lb.phase == "warten" and len(lb.spieler) < lb.max_spieler
        ]
        await self._broadcast_alle({"typ": "online_spieler", "spieler": spieler_liste,
                                    "aktive_lobby_codes": joinbare_codes})

    async def handler(self, ws):
        """Haupt-Handler für WebSocket-Verbindungen"""
        manager_id = None
        google_id = None
        self.alle_ws.add(ws)
        # Neuen Client direkt mit aktueller Online-Liste versorgen
        spieler_liste = [{"name": u["name"]} for u in self.online_users.values()]
        try:
            _afk_min = _cfg_int("lobby", "afk_timeout_min")
            await self._ws_send(ws, json.dumps({"typ": "server_info", "version": _VERSION, "server_id": _SERVER_ID, "afk_timeout_min": _afk_min}, ensure_ascii=False))
            await self._ws_send(ws, json.dumps({"typ": "online_spieler", "spieler": spieler_liste}, ensure_ascii=False))
            if self.global_chat:
                aktive_codes = set(self.lobbys.keys())
                def _msg_behalten(m):
                    codes = _LOBBY_CODE_RE.findall(m.get("text", ""))
                    if not codes:
                        return True
                    return all(c in aktive_codes for c in codes)
                gefiltert = [m for m in self.global_chat if _msg_behalten(m)]
                nachrichten = [dict(m, profil=self._profil_daten(m.get("google_id"))) for m in gefiltert]
                await self._ws_send(ws, json.dumps({"typ": "chat_verlauf", "bereich": "global", "nachrichten": nachrichten}, ensure_ascii=False))
        except:
            pass

        try:
            async for nachricht in ws:
                _netstat.rx += len(nachricht) if isinstance(nachricht, (bytes, bytearray)) else len(nachricht.encode())
                data = json.loads(nachricht)
                aktion = data.get("aktion")

                # Authentication: Verify auth_token for new connections
                if aktion in ("lobby_erstellen", "lobby_beitreten", "identifizieren"):
                    auth_token = data.get("auth_token")
                    if auth_token:
                        verified_manager_id, verified_google_id = self._verify_auth_token(auth_token)
                        if verified_manager_id:
                            manager_id = verified_manager_id
                            google_id = verified_google_id

                if aktion == "identifizieren":
                    if not manager_id:
                        manager_id = data.get("manager_id", generiere_lobby_code(8))
                    name = data.get("name", "").strip() or f"{random.choice(_VORNAMEN)} {random.choice(_NACHNAMEN)}"
                    self.verbindungen[ws] = {"lobby_code": None, "manager_id": manager_id, "google_id": google_id}
                    # Cancel grace period if this user was in the 5-minute offline grace window
                    _gt = self._grace_tasks.pop(manager_id, None)
                    if _gt and not _gt.done():
                        _gt.cancel()
                    self.online_users[manager_id] = {"ws": ws, "name": name, "google_id": google_id, "lobby_code": None}
                    _email = None
                    if google_id:
                        _p = ProfileManager.get_profile(google_id)
                        _email = _p.get("email") if _p else None
                    log_connect(name, google_id=google_id, email=_email)
                    await self._broadcast_online_spieler()
                    if google_id:
                        _slots = MPSaveManager.list_slots(google_id)
                        _summary = {str(i): MPSaveManager.slot_summary(_slots[i]) for i in range(1, 6)}
                        await self._ws_send(ws, json.dumps({"typ": "mp_slots", "slots": _summary}, ensure_ascii=False))

                elif aktion == "lobby_erstellen":
                    code = generiere_lobby_code()
                    # Use auth_token's manager_id if available, fallback to random
                    if not manager_id:
                        manager_id = data.get("manager_id", generiere_lobby_code(8))
                    name = data.get("name", "").strip() or f"{random.choice(_VORNAMEN)} {random.choice(_NACHNAMEN)}"
                    lobby = Lobby(code=code, ersteller_id=manager_id)
                    lobby.ersteller_google_id = google_id
                    email = data.get("email")  # From auth
                    lobby.spieler_hinzufügen(manager_id, ws, name, google_id, email)
                    self.lobbys[code] = lobby
                    self.verbindungen[ws] = {"lobby_code": code, "manager_id": manager_id, "google_id": google_id}
                    self.online_users[manager_id] = {"ws": ws, "name": name, "google_id": google_id, "lobby_code": code}
                    await self._ws_send(ws, json.dumps({"typ": "lobby_erstellt", "code": code, "manager_id": manager_id}))
                    # Ersteller sich selbst in der Manager-Liste anzeigen
                    await self._ws_send(ws, json.dumps({
                        "typ": "manager_liste",
                        "manager": [{"id": manager_id, "name": name, "team": None}]
                    }))
                    await self._broadcast_online_spieler()

                elif aktion == "lobby_beitreten":
                    code = data.get("code", "").upper()
                    # Use auth_token's manager_id if available, fallback to random
                    if not manager_id:
                        manager_id = data.get("manager_id", generiere_lobby_code(8))
                    name = data.get("name", "").strip() or f"{random.choice(_VORNAMEN)} {random.choice(_NACHNAMEN)}"
                    lobby = self.lobbys.get(code)

                    if not lobby:
                        await self._ws_send(ws, json.dumps({"typ": "fehler", "nachricht": "Lobby nicht gefunden"}))
                        continue

                    # MP-Save-Lobby: Prüfe ob Spieler im Speicherstand registriert ist
                    if lobby.mp_ist_geladen:
                        _erwartet = next(
                            (m for m in lobby.mp_erwartete_manager if m.get("google_id") == google_id),
                            None
                        )
                        if not _erwartet:
                            await self._ws_send(ws, json.dumps({"typ": "fehler",
                                "nachricht": "Du bist in diesem Spielstand nicht registriert."}))
                            continue
                        # Team direkt aus Speicherstand zuweisen
                        _mp_team = _erwartet["team"]
                        email = data.get("email")
                        if not lobby.spieler_hinzufügen(manager_id, ws, name, google_id, email):
                            await self._ws_send(ws, json.dumps({"typ": "fehler", "nachricht": "Lobby voll"}))
                            continue
                        lobby.spieler[manager_id]["team"] = _mp_team
                    else:
                        email = data.get("email")  # From auth
                        if not lobby.spieler_hinzufügen(manager_id, ws, name, google_id, email):
                            await self._ws_send(ws, json.dumps({"typ": "fehler", "nachricht": "Lobby voll"}))
                            continue

                    self.verbindungen[ws] = {"lobby_code": code, "manager_id": manager_id, "google_id": google_id}
                    self.online_users[manager_id] = {"ws": ws, "name": name, "google_id": google_id, "lobby_code": code}
                    # Private Bestätigung mit manager_id an den Beitretenden
                    await self._ws_send(ws, json.dumps({"typ": "beigetreten", "manager_id": manager_id,
                                              "name": name, "mp_geladen": lobby.mp_ist_geladen}))
                    # Vollständige Manager-Liste + MP-Status an alle senden
                    manager_liste = [
                        {"id": mid, "name": sp["name"], "team": sp["team"]}
                        for mid, sp in lobby.spieler.items()
                    ]
                    mp_status = self._mp_lobby_status(lobby) if lobby.mp_ist_geladen else None
                    await lobby.broadcast({"typ": "manager_liste", "manager": manager_liste,
                                           "mp_status": mp_status})
                    await self._broadcast_online_spieler()

                elif aktion == "team_waehlen":
                    info = self.verbindungen.get(ws, {})
                    lobby = self.lobbys.get(info.get("lobby_code"))
                    if lobby:
                        mid = info["manager_id"]
                        team_name = data.get("team")
                        # Prüfen ob Verein bereits von anderem Manager gewählt
                        bereits_belegt = any(
                            sp["team"] == team_name and other_mid != mid
                            for other_mid, sp in lobby.spieler.items()
                        )
                        if bereits_belegt:
                            await self._ws_send(ws, json.dumps({"typ": "fehler", "nachricht": f"{team_name} bereits vergeben"}))
                        else:
                            lobby.spieler[mid]["team"] = team_name
                            await lobby.broadcast({"typ": "team_gewaehlt", "manager": mid, "team": team_name})
                            # Aktualisierte Manager-Liste senden
                            manager_liste = [
                                {"id": m, "name": sp["name"], "team": sp["team"]}
                                for m, sp in lobby.spieler.items()
                            ]
                            await lobby.broadcast({"typ": "manager_liste", "manager": manager_liste})

                elif aktion == "spiel_starten":
                    info = self.verbindungen.get(ws, {})
                    lobby = self.lobbys.get(info.get("lobby_code"))
                    if lobby and info.get("manager_id") == lobby.ersteller_id:
                        team_auswahl = {mid: sp["team"] for mid, sp in lobby.spieler.items()}
                        lobby.spiel_starten(team_auswahl)
                        # Ersten Kontostand-Verlaufswert nach dem Draft setzen
                        for _t in lobby.game_state.teams.values():
                            if _t.ist_menschlich:
                                _t.kontostand_verlauf = [_t.kontostand]
                        # Jedem Manager seine eigenen Daten schicken
                        alle_mgr_teams = [
                            {"team": sp["team"], "name": sp.get("name", "Manager")}
                            for sp in lobby.spieler.values() if sp.get("team")
                        ]
                        gs0 = lobby.game_state
                        _pokale0 = self._compute_pokal_uebersicht(gs0)
                        for mid, sp_info in lobby.spieler.items():
                            team_name = sp_info["team"]
                            team = gs0.teams.get(team_name)
                            if not team:
                                continue
                            _gl = _gelistet_namen(lobby)
                            kader_data = [_spieler_dict(s, s.name in _gl) for s in team.kader]
                            await sp_info["ws"].send(json.dumps({
                                "typ": "spiel_gestartet",
                                "team": team_name,
                                "saison": gs0.saison,
                                "spieltag": gs0.spieltag,
                                "kontostand": team.kontostand,
                                "kader": kader_data,
                                "startelf": team.startelf,
                                "alle_manager_teams": alle_mgr_teams,
                                "tabelle": _tab_data_gs(gs0, 1),
                                "tabelle_bl2": _tab_data_gs(gs0, 2),
                                "pokale": _pokale0,
                                "kontostand_verlauf": team.kontostand_verlauf,
                                "game_key": lobby.game_key,
                                "lobby_code": lobby.code,
                            }, ensure_ascii=False))
                        await self._broadcast_online_spieler()
                        # Lobby-Code aus globalem Chat-Buffer löschen (Spiel läuft, Code nicht mehr joinbar)
                        if _entferne_lobby_code_aus_chat(self.global_chat, lobby.code):
                            _save_global_chat(self.global_chat)
                            await self._broadcast_alle({"typ": "lobby_code_abgelaufen", "code": lobby.code})
                        # MP-Autosave anlegen falls mindestens 2 Google-angemeldete Manager
                        if lobby.ersteller_google_id and lobby.game_key:
                            _mp_managers = [
                                {"google_id": sp.get("google_id"), "name": sp.get("name"), "team": sp.get("team")}
                                for sp in lobby.spieler.values() if sp.get("google_id") and sp.get("team")
                            ]
                            if len(_mp_managers) >= 2:
                                MPSaveManager.create_for_game(
                                    lobby.ersteller_google_id, lobby.game_key, _mp_managers, gs0)

                elif aktion == "resume_game":
                    # Verify auth and register connection if not yet done
                    auth_token = data.get("auth_token")
                    if auth_token:
                        res_mid, res_gid = self._verify_auth_token(auth_token)
                        if res_mid:
                            manager_id = res_mid
                            google_id = res_gid
                            self.verbindungen[ws] = {"lobby_code": None, "manager_id": manager_id, "google_id": google_id}

                    info = self.verbindungen.get(ws, {})
                    if not info.get("manager_id"):
                        await self._ws_send(ws, json.dumps({"typ": "fehler", "nachricht": "Nicht authentifiziert"}))
                        continue

                    game_key = data.get("game_key")
                    if not game_key:
                        await self._ws_send(ws, json.dumps({"typ": "fehler", "nachricht": "Kein Spiel angegeben"}))
                        continue

                    manager_id = info.get("manager_id")
                    google_id = info.get("google_id")

                    # ── Aktive Session suchen (Reconnect) ────────────────────
                    active_lobby = next(
                        (l for l in self.lobbys.values()
                         if l.game_key == game_key and manager_id in l.spieler),
                        None
                    )
                    if active_lobby:
                        # Spieler in laufende Lobby reconnecten
                        spieler_info = active_lobby.spieler[manager_id]
                        spieler_info["ws"] = ws
                        self.verbindungen[ws] = {"lobby_code": active_lobby.code,
                                                 "manager_id": manager_id, "google_id": google_id}
                        _name = spieler_info.get("name", "Manager")
                        # Cancel grace period on reconnect
                        _gt = self._grace_tasks.pop(manager_id, None)
                        if _gt and not _gt.done():
                            _gt.cancel()
                        self.online_users[manager_id] = {"ws": ws, "name": _name,
                                                         "google_id": google_id,
                                                         "lobby_code": active_lobby.code}
                        # Ersteller zurück: Close-Task canceln und andere informieren
                        if manager_id == active_lobby.ersteller_id:
                            if active_lobby.close_task and not active_lobby.close_task.done():
                                active_lobby.close_task.cancel()
                                active_lobby.close_task = None
                            for other_mid, sp_info in active_lobby.spieler.items():
                                if other_mid != manager_id and sp_info.get("ws"):
                                    await self._ws_send(sp_info["ws"], json.dumps({
                                        "typ": "ersteller_online", "name": _name
                                    }, ensure_ascii=False))
                        await self._broadcast_online_spieler()
                        log.info(f"↗ {_name} wieder verbunden.")
                        log_reconnect(_name, google_id=google_id)
                        await active_lobby.broadcast({"typ": "spieler_online",
                                                      "manager_id": manager_id, "name": _name})
                        team_name = spieler_info.get("team")
                        team = active_lobby.game_state.teams.get(team_name) if active_lobby.game_state else None
                        if team:
                            alle_mgr_teams = [
                                {"team": sp.get("team"), "name": sp.get("name", "Manager")}
                                for sp in active_lobby.spieler.values() if sp.get("team")
                            ]
                            gs_r = active_lobby.game_state
                            _rc_cup = None
                            for _wb, _runde, _leg in EUROPA_KALENDER.get(gs_r.spieltag, []):
                                _bracket = gs_r.dfb_pokal_bracket if _wb == "dfb" else gs_r.europa_brackets.get(_wb)
                                if not _bracket:
                                    continue
                                _paarungen = _bracket.get("runden", {}).get(_runde, [])
                                if any(team_name in (p.get("heim"), p.get("gast")) for p in _paarungen):
                                    _rc_cup = {"wb": _wb, "runde": _runde}
                                    break
                            await self._ws_send(ws, json.dumps({
                                "typ": "spiel_gestartet",
                                "team": team_name,
                                "saison": gs_r.saison,
                                "spieltag": gs_r.spieltag,
                                "kontostand": team.kontostand,
                                "kader": [_spieler_dict(s, s.name in _gelistet_namen(active_lobby)) for s in team.kader],
                                "startelf": team.startelf,
                                "alle_manager_teams": alle_mgr_teams,
                                "tabelle": _tab_data_gs(gs_r, 1),
                                "tabelle_bl2": _tab_data_gs(gs_r, 2),
                                "pokale": self._compute_pokal_uebersicht(gs_r),
                                "naechstes_cup": _rc_cup,
                                "kontostand_verlauf": team.kontostand_verlauf[-34:],
                                "resumed": True,
                                "reconnected": True,
                                "game_key": active_lobby.game_key,
                                "lobby_code": active_lobby.code,
                                "session_chat": active_lobby.session_chat,
                            }, ensure_ascii=False))
                        continue

                    # ── Spielstand aus Datei laden ────────────────────────────
                    game_save, loaded_gs = GameSaver.load_game_save(game_key)
                    if not loaded_gs:
                        await self._ws_send(ws, json.dumps({"typ": "fehler", "nachricht": "Spiel konnte nicht geladen werden"}))
                        continue

                    # Create new lobby for resumed game
                    code = generiere_lobby_code()

                    # Restore game in new lobby
                    lobby = Lobby(code=code, ersteller_id=manager_id)
                    lobby.game_state = loaded_gs
                    lobby.game_key = game_key
                    lobby.phase = loaded_gs.phase
                    lobby.session_chat = game_save.get("session_chat", [])

                    # Falls mid-spiel gespeichert (Liga lief schon, Cup noch nicht):
                    # Pending Cup-Events wiederherstellen; Phase bleibt "spiel".
                    # Nächstes Weiter des Users führt sie aus, dann erst naechster_spieltag().
                    # _dfb/_europa_runde_ausfuehren prüfen aktive_runde – bereits erledigte
                    # Events werden automatisch übersprungen (idempotent).
                    if lobby.phase == "spiel":
                        lobby.pending_pokal_events = list(EUROPA_KALENDER.get(loaded_gs.spieltag, []))

                    # Restore transfer market
                    lobby.transfermarkt = Transfermarkt(loaded_gs)
                    lobby.transfermarkt.neue_woche()
                    # Gelistete Spieler aus Save wiederherstellen (müssen vor neue_woche_angebote sein)
                    for _ge in getattr(loaded_gs, '_gelistete_spieler_raw', []):
                        from engine.game_state import Spieler as _Sp
                        from server.game_saver import deserialize_spieler as _ds
                        _sp = _ds(_ge["spieler"])
                        lobby.transfermarkt.gelistete_spieler.append(
                            (_sp, _ge["preis"], _ge["verkäufer"], _ge["woche"])
                        )
                    lobby.transfermarkt.neue_woche_angebote()

                    # Add manager to restored lobby
                    manager_data = game_save.get("managers", {}).get(manager_id, {})
                    lobby.spieler_hinzufügen(manager_id, ws, manager_data.get("name", "Manager"),
                                           google_id, manager_data.get("email"))
                    lobby.spieler[manager_id]["team"] = manager_data.get("team")

                    self.lobbys[code] = lobby
                    self.verbindungen[ws] = {"lobby_code": code, "manager_id": manager_id, "google_id": google_id}
                    _name = manager_data.get("name", "Manager")
                    self.online_users[manager_id] = {"ws": ws, "name": _name, "google_id": google_id, "lobby_code": code}
                    await self._broadcast_online_spieler()

                    # Send game data to manager
                    team_name = manager_data.get("team")
                    team = loaded_gs.teams.get(team_name)
                    if team:
                        _gl2 = _gelistet_namen(lobby)
                        kader_data = [_spieler_dict(s, s.name in _gl2) for s in team.kader]
                        alle_mgr_teams = [
                            {"team": sp["team"], "name": sp.get("name", "Manager")}
                            for sp in lobby.spieler.values() if sp.get("team")
                        ]
                        # Cup-Hinweis für den Button (gleiche Logik wie _sende_management_phase)
                        _naechstes_cup = None
                        for _wb, _runde, _leg in EUROPA_KALENDER.get(loaded_gs.spieltag, []):
                            _bracket = loaded_gs.dfb_pokal_bracket if _wb == "dfb" else loaded_gs.europa_brackets.get(_wb)
                            if not _bracket:
                                continue
                            _paarungen = _bracket.get("runden", {}).get(_runde, [])
                            if any(team_name in (p.get("heim"), p.get("gast")) for p in _paarungen):
                                _naechstes_cup = {"wb": _wb, "runde": _runde}
                                break
                        _gl_eigene = lobby.transfermarkt.get_gelistete_fuer_team(team_name) if lobby.transfermarkt else []
                        _letzte_zv = lobby.transfermarkt.letzte_zwangsverkäufe.get(team_name, []) if lobby.transfermarkt else []
                        await self._ws_send(ws, json.dumps({
                            "typ": "spiel_gestartet",
                            "team": team_name,
                            "saison": loaded_gs.saison,
                            "spieltag": loaded_gs.spieltag,
                            "kontostand": team.kontostand,
                            "kader": kader_data,
                            "startelf": team.startelf,
                            "alle_manager_teams": alle_mgr_teams,
                            "tabelle": _tab_data_gs(loaded_gs, 1),
                            "tabelle_bl2": _tab_data_gs(loaded_gs, 2),
                            "pokale": self._compute_pokal_uebersicht(loaded_gs),
                            "naechstes_cup": _naechstes_cup,
                            "kontostand_verlauf": team.kontostand_verlauf[-34:],
                            "resumed": True,
                            "phase": lobby.phase,
                            "weiter_sek": max(0, int(60 - (time.time() - lobby.weiter_ts))) if lobby.phase == "spiel" and lobby.weiter_ts else None,
                            "game_key": lobby.game_key,
                            "lobby_code": code,
                            "session_chat": lobby.session_chat,
                            "gelistete_spieler_eigene": _gl_eigene,
                            "letzte_zv": _letzte_zv,
                        }, ensure_ascii=False))

                elif aktion == "weiter":
                    info = self.verbindungen.get(ws, {})
                    lobby = self.lobbys.get(info.get("lobby_code"))
                    if lobby:
                        lobby.bereit.add(info["manager_id"])
                        _online_mids = set(lobby.online_spieler().keys())
                        _afk_mids = {m for m in _online_mids if self.online_users.get(m, {}).get("afk")}
                        warten_auf = [sp["name"] for mid, sp in lobby.spieler.items()
                                      if mid not in lobby.bereit and mid not in _afk_mids]
                        await lobby.broadcast({"typ": "spieler_bereit", "anzahl": len(lobby.bereit), "gesamt": len(lobby.spieler), "warten_auf": warten_auf})
                        if lobby.alle_bereit():
                            lobby.bereit.clear()
                            lobby.phase_task = asyncio.create_task(self._naechste_phase(lobby))

                elif aktion == "set_afk":
                    info = self.verbindungen.get(ws, {})
                    mid = info.get("manager_id")
                    if mid and mid in self.online_users:
                        ist_afk = bool(data.get("afk"))
                        self.online_users[mid]["afk"] = ist_afk
                        await self._broadcast_online_spieler()
                        # Wenn in Lobby: prüfen ob jetzt alle (effektiv) bereit sind
                        lc = info.get("lobby_code")
                        if lc:
                            lobby = self.lobbys.get(lc)
                            if lobby and lobby.phase == "management" and lobby.alle_bereit():
                                lobby.bereit.clear()
                                lobby.phase_task = asyncio.create_task(self._naechste_phase(lobby))

                elif aktion == "simulieren":
                    info = self.verbindungen.get(ws, {})
                    lobby = self.lobbys.get(info.get("lobby_code"))
                    if lobby:
                        gid = info.get("google_id", "")
                        manager_id = info.get("manager_id", "")
                        email = (lobby.spieler.get(manager_id) or {}).get("email", "") or ""
                        if _ist_admin(gid, email) or _ist_tester(gid):
                            lobby.sim_skip[0] = True
                            await lobby.broadcast({"typ": "simulieren"})

                elif aktion == "debug_force_vl":
                    info = self.verbindungen.get(ws, {})
                    lobby = self.lobbys.get(info.get("lobby_code"))
                    manager_id = info.get("manager_id")
                    if lobby and manager_id:
                        _gid = self.verbindungen.get(ws, {}).get("google_id", "")
                        _profil = ProfileManager.get_profile(_gid) if _gid else None
                        _email = (_profil.get("email", "") if _profil else "").lower()
                        if _email and _email in _OWNER_EMAILS:
                            lobby.debug_force_vl[0] = True
                            lobby.sim_skip[0] = True
                            await lobby.broadcast({"typ": "simulieren"})

                elif aktion == "debug_force_elf":
                    info = self.verbindungen.get(ws, {})
                    lobby = self.lobbys.get(info.get("lobby_code"))
                    manager_id = info.get("manager_id")
                    if lobby and manager_id:
                        _gid = self.verbindungen.get(ws, {}).get("google_id", "")
                        _profil = ProfileManager.get_profile(_gid) if _gid else None
                        _email = (_profil.get("email", "") if _profil else "").lower()
                        if _email and _email in _OWNER_EMAILS:
                            lobby.debug_force_elf[0] = True
                            lobby.debug_force_vl[0] = True
                            lobby.sim_skip[0] = True
                            await lobby.broadcast({"typ": "simulieren"})

                elif aktion == "transfer_inland":
                    await self._handle_transfer_inland(ws, data)

                elif aktion == "transfer_ausland":
                    await self._handle_transfer_ausland(ws, data)

                elif aktion == "kaufen":
                    await self._handle_kaufen(ws, data)

                elif aktion == "startelf_speichern":
                    info = self.verbindungen.get(ws, {})
                    lobby = self.lobbys.get(info.get("lobby_code"))
                    if lobby and lobby.game_state:
                        mid = info["manager_id"]
                        team_name = lobby.spieler[mid]["team"]
                        team = lobby.game_state.teams.get(team_name)
                        if team:
                            neue_startelf = data.get("startelf", [])
                            # Validierung: max 11, alle im Kader, verfügbar (nicht verletzt/gesperrt), max 3 Ausländer
                            kader_map = {s.name: s for s in team.kader}
                            gefiltert = [
                                n for n in neue_startelf
                                if n in kader_map and kader_map[n].verfuegbar
                            ][:11]
                            auslaender = sum(
                                1 for n in gefiltert
                                if kader_map[n].ist_auslaender
                            )
                            if auslaender <= 3:
                                team.startelf = gefiltert
                                # Bereit-Status zurücksetzen wenn Aufstellung geändert
                                if mid in lobby.bereit:
                                    lobby.bereit.discard(mid)
                                    warten_auf = [sp["name"] for m2, sp in lobby.spieler.items() if m2 not in lobby.bereit]
                                    await lobby.broadcast({"typ": "spieler_bereit", "anzahl": len(lobby.bereit), "gesamt": len(lobby.spieler), "warten_auf": warten_auf})
                                await self._ws_send(ws, json.dumps({
                                    "typ": "startelf_ok",
                                    "startelf": team.startelf
                                }, ensure_ascii=False))
                            else:
                                await self._ws_send(ws, json.dumps({
                                    "typ": "fehler",
                                    "nachricht": "Max 3 Internationale in der Startelf"
                                }))

                elif aktion == "verkaufen":
                    await self._handle_verkaufen(ws, data)

                elif aktion == "delist":
                    await self._handle_delist(ws, data)

                # ── Multiplayer-Speicherstände ─────────────────────────────
                elif aktion == "mp_slots":
                    # Gibt die 5 Speicherslots des eingeloggten Users zurück
                    if google_id:
                        slots = MPSaveManager.list_slots(google_id)
                        summary = {str(i): MPSaveManager.slot_summary(slots[i]) for i in range(1, 6)}
                        await self._ws_send(ws, json.dumps({"typ": "mp_slots", "slots": summary}, ensure_ascii=False))

                elif aktion == "mp_laden":
                    # Erstellt eine neue Lobby aus einem MP-Speicherslot
                    _slot = int(data.get("slot", 0))
                    if not google_id:
                        await self._ws_send(ws, json.dumps({"typ": "fehler",
                            "nachricht": "Nicht eingeloggt."}, ensure_ascii=False))
                        continue
                    _slot_data = MPSaveManager.load_slot(google_id, _slot)
                    if not _slot_data:
                        await self._ws_send(ws, json.dumps({"typ": "fehler",
                            "nachricht": "Speicherstand nicht gefunden."}, ensure_ascii=False))
                        continue
                    # Neue Lobby erstellen
                    if not manager_id:
                        manager_id = generiere_lobby_code(8)
                    _name = data.get("name", "Manager")
                    _code = generiere_lobby_code()
                    _lobby = Lobby(code=_code, ersteller_id=manager_id)
                    _lobby.ersteller_google_id = google_id
                    _lobby.mp_ist_geladen = True
                    _lobby.mp_erwartete_manager = _slot_data["managers"]
                    _email = data.get("email")
                    _lobby.spieler_hinzufügen(manager_id, ws, _name, google_id, _email)
                    # Ersteller-Team direkt zuweisen
                    _ersteller_eintrag = next(
                        (m for m in _slot_data["managers"] if m.get("google_id") == google_id), None)
                    if _ersteller_eintrag:
                        _lobby.spieler[manager_id]["team"] = _ersteller_eintrag["team"]
                    self.lobbys[_code] = _lobby
                    self.verbindungen[ws] = {"lobby_code": _code, "manager_id": manager_id, "google_id": google_id}
                    self.online_users[manager_id] = {"ws": ws, "name": _name, "google_id": google_id, "lobby_code": _code}
                    _mp_status = self._mp_lobby_status(_lobby)
                    await self._ws_send(ws, json.dumps({
                        "typ": "mp_lobby_erstellt",
                        "code": _code,
                        "manager_id": manager_id,
                        "slot": _slot,
                        "saison": _slot_data["saison"],
                        "spieltag": _slot_data["spieltag"],
                        "mp_status": _mp_status,
                    }, ensure_ascii=False))
                    await self._ws_send(ws, json.dumps({
                        "typ": "manager_liste",
                        "manager": [{"id": manager_id, "name": _name,
                                     "team": (_ersteller_eintrag or {}).get("team")}],
                        "mp_status": _mp_status,
                    }, ensure_ascii=False))
                    await self._broadcast_online_spieler()

                elif aktion == "mp_laden_starten":
                    # Startet das Spiel aus dem MP-Speicherstand
                    # Fehlende Manager werden zu CPU-Teams
                    _info = self.verbindungen.get(ws, {})
                    _lobby = self.lobbys.get(_info.get("lobby_code"))
                    _mid = _info.get("manager_id")
                    if not _lobby or _mid != _lobby.ersteller_id or not _lobby.mp_ist_geladen:
                        await self._ws_send(ws, json.dumps({"typ": "fehler",
                            "nachricht": "Nicht berechtigt oder kein MP-Spielstand."}, ensure_ascii=False))
                        continue
                    # GameState aus dem Slot wiederherstellen
                    _slot_data = MPSaveManager.load_slot(
                        _lobby.ersteller_google_id, data.get("slot", 1))
                    if not _slot_data:
                        await self._ws_send(ws, json.dumps({"typ": "fehler",
                            "nachricht": "Spielstand nicht mehr vorhanden."}, ensure_ascii=False))
                        continue
                    from server.game_saver import deserialize_team
                    from engine.game_state import GameState
                    _gs_data = _slot_data["game_state"]
                    _gs = GameState(lobby_code=_lobby.code)
                    _gs.saison = _gs_data["saison"]
                    _gs.spieltag = _gs_data["spieltag"]
                    _gs.phase = _gs_data["phase"]
                    for _tn, _td in _gs_data["teams"].items():
                        _gs.teams[_tn] = deserialize_team(_td)
                    for _tn, _td in _gs_data.get("europa_teams", {}).items():
                        _gs.europa_teams[_tn] = deserialize_team(_td)
                    _gs.dfb_pokal_bracket = _gs_data.get("dfb_pokal_bracket", {})
                    _gs.europa_brackets = _gs_data.get("europa_brackets", {})
                    # Beigetretene Manager: Team als menschlich markieren
                    _joined_gids = {sp.get("google_id"): mid
                                    for mid, sp in _lobby.spieler.items()}
                    for _erw in _lobby.mp_erwartete_manager:
                        _egid = _erw.get("google_id")
                        _eteam = _erw.get("team")
                        _team_obj = _gs.teams.get(_eteam)
                        if not _team_obj:
                            continue
                        if _egid in _joined_gids:
                            _team_obj.ist_menschlich = True
                            _team_obj.manager_id = _joined_gids[_egid]
                        else:
                            # Fehlender Spieler → CPU
                            _team_obj.ist_menschlich = False
                            _team_obj.manager_id = None
                    _lobby.game_state = _gs
                    _lobby.phase = "management"
                    _lobby.transfermarkt = Transfermarkt(_gs)
                    _lobby.transfermarkt.neue_woche()
                    for _ge in getattr(_gs, '_gelistete_spieler_raw', []):
                        from server.game_saver import deserialize_spieler as _ds2
                        _sp2 = _ds2(_ge["spieler"])
                        _lobby.transfermarkt.gelistete_spieler.append(
                            (_sp2, _ge["preis"], _ge["verkäufer"], _ge["woche"])
                        )
                    _lobby.transfermarkt.neue_woche_angebote()
                    _lobby.game_key = GameSaver.create_game_save(
                        _lobby,
                        _gs,
                        {mid: {"google_id": sp.get("google_id"), "email": sp.get("email"),
                               "name": sp.get("name"), "team": sp.get("team")}
                         for mid, sp in _lobby.spieler.items()}
                    )
                    # MP-Slot verwalten: bei Einzelspieler löschen, sonst auf neuen game_key umschreiben
                    # Nur Google-angemeldete Manager zählen (Gäste können nicht zurückkehren)
                    _human_count = sum(
                        1 for sp in _lobby.spieler.values()
                        if sp.get("google_id") and
                           _gs.teams.get(sp.get("team"), None) and
                           _gs.teams[sp.get("team")].ist_menschlich
                    )
                    if _lobby.ersteller_google_id and _lobby.game_key:
                        _slot_num = data.get("slot", 1)
                        if _human_count <= 1:
                            # Alleine → MP-Slot löschen, läuft als normaler Spielstand weiter
                            MPSaveManager.delete_slot(_lobby.ersteller_google_id, _slot_num)
                        else:
                            # Mehrere → Slot direkt mit neuem game_key aktualisieren (kein delete+recreate)
                            _mp_mgrs = [
                                {"google_id": sp.get("google_id"), "name": sp.get("name"), "team": sp.get("team")}
                                for sp in _lobby.spieler.values() if sp.get("google_id") and sp.get("team")
                            ]
                            MPSaveManager.update_slot(
                                _lobby.ersteller_google_id, _slot_num, _lobby.game_key, _mp_mgrs, _gs)
                    # Jeden beigetretenen Manager informieren
                    _alle_mgr_teams = [
                        {"team": sp["team"], "name": sp.get("name", "Manager")}
                        for sp in _lobby.spieler.values() if sp.get("team")
                    ]
                    _pokale = self._compute_pokal_uebersicht(_gs)
                    for _jmid, _jsp in _lobby.spieler.items():
                        _jteam_name = _jsp.get("team")
                        _jteam = _gs.teams.get(_jteam_name)
                        if not _jteam or not _jsp.get("ws"):
                            continue
                        _gl3 = _gelistet_namen(_lobby)
                        _kader = [_spieler_dict(s, s.name in _gl3) for s in _jteam.kader]
                        await _jsp["ws"].send(json.dumps({
                            "typ": "spiel_gestartet",
                            "team": _jteam_name,
                            "saison": _gs.saison,
                            "spieltag": _gs.spieltag,
                            "kontostand": _jteam.kontostand,
                            "kader": _kader,
                            "startelf": _jteam.startelf,
                            "alle_manager_teams": _alle_mgr_teams,
                            "tabelle": _tab_data_gs(_gs, 1),
                            "tabelle_bl2": _tab_data_gs(_gs, 2),
                            "pokale": _pokale,
                            "game_key": _lobby.game_key,
                            "lobby_code": _lobby.code,
                        }, ensure_ascii=False))
                    await self._broadcast_online_spieler()

                elif aktion == "mp_slot_loeschen":
                    _slot = int(data.get("slot", 0))
                    if google_id and 1 <= _slot <= 5:
                        _ok = MPSaveManager.delete_slot(google_id, _slot)
                        await self._ws_send(ws, json.dumps({"typ": "mp_slot_geloescht",
                            "ok": _ok, "slot": _slot}, ensure_ascii=False))

                elif aktion == "spiel_verlassen":
                    info = self.verbindungen.get(ws, {})
                    lobby = self.lobbys.get(info.get("lobby_code"))
                    mid = info.get("manager_id")
                    if lobby and mid:
                        name = lobby.spieler.get(mid, {}).get("name", "Spieler")
                        is_creator = (mid == lobby.ersteller_id)
                        other_mids = [m for m in lobby.spieler if m != mid]

                        if is_creator and other_mids:
                            # Ersteller verlässt Lobby/Spiel → für alle schließen
                            if lobby.game_state:
                                if lobby.game_key:
                                    GameSaver.save_game_state(lobby.game_key, lobby.game_state,
                                                              session_chat=lobby.session_chat)
                                    self._mp_autosave(lobby)
                                if lobby.phase_task and not lobby.phase_task.done():
                                    lobby.phase_task.cancel()
                                meldung = f"{name} (Ersteller) hat die Session beendet. Spiel gespeichert."
                            else:
                                meldung = "Die Lobby wurde vom Ersteller geschlossen."
                            for other_mid in other_mids:
                                other_ws = lobby.spieler.get(other_mid, {}).get("ws")
                                if other_ws:
                                    await self._ws_send(other_ws, json.dumps({
                                        "typ": "lobby_aufgeloest",
                                        "nachricht": meldung
                                    }, ensure_ascii=False))
                                if other_mid in self.online_users:
                                    self.online_users[other_mid]["lobby_code"] = None
                                other_conn = next((c for c_ws, c in self.verbindungen.items()
                                                   if c.get("manager_id") == other_mid), None)
                                if other_conn:
                                    other_conn["lobby_code"] = None
                            if _entferne_lobby_code_aus_chat(self.global_chat, lobby.code):
                                _save_global_chat(self.global_chat)
                                await self._broadcast_alle({"typ": "lobby_code_abgelaufen", "code": lobby.code})
                            self.lobbys.pop(lobby.code, None)
                            # Ersteller selbst zurück
                            self.verbindungen[ws] = {"lobby_code": None, "manager_id": mid, "google_id": google_id}
                            if mid in self.online_users:
                                self.online_users[mid]["lobby_code"] = None
                            await self._ws_send(ws, json.dumps({"typ": "zurueck_zur_lobby"}, ensure_ascii=False))
                        else:
                            # Sofort speichern
                            if lobby.game_key:
                                GameSaver.save_game_state(lobby.game_key, lobby.game_state,
                                                          session_chat=lobby.session_chat)
                                self._mp_autosave(lobby)
                            lobby.spieler_entfernen(mid)
                            self.verbindungen[ws] = {"lobby_code": None, "manager_id": mid, "google_id": google_id}
                            if mid in self.online_users:
                                self.online_users[mid]["lobby_code"] = None
                            # Spieler zurück zur Lobby schicken
                            await self._ws_send(ws, json.dumps({"typ": "zurueck_zur_lobby"}, ensure_ascii=False))
                            # Verbleibende benachrichtigen
                            if lobby.spieler:
                                await lobby.broadcast({
                                    "typ": "spieler_verlassen",
                                    "name": name,
                                    "verbleibend": len(lobby.spieler)
                                })
                                # Falls jetzt alle bereit sind (Verlassender war letzter der noch fehlte)
                                if lobby.alle_bereit():
                                    lobby.bereit.clear()
                                    lobby.phase_task = asyncio.create_task(self._naechste_phase(lobby))
                            else:
                                if _entferne_lobby_code_aus_chat(self.global_chat, lobby.code):
                                    _save_global_chat(self.global_chat)
                                    await self._broadcast_alle({"typ": "lobby_code_abgelaufen", "code": lobby.code})
                                self.lobbys.pop(lobby.code, None)
                        await self._broadcast_online_spieler()

                elif aktion == "chat_nachricht":
                    conn_info = self.verbindungen.get(ws, {})
                    mid = conn_info.get("manager_id")
                    if mid and mid in self.online_users:
                        text = str(data.get("text", "")).strip()[:200]
                        bereich = data.get("bereich", "global")
                        # Mute-Check: stummgeschaltet? (Admins ausgenommen)
                        _mute_gid = self.online_users[mid].get("google_id") or ""
                        _mute_profil = ProfileManager.get_profile(_mute_gid) if _mute_gid else None
                        _mute_email = (_mute_profil.get("email", "") if _mute_profil else "").lower()
                        _is_muted_admin = _mute_email in _OWNER_EMAILS
                        _lobby_mute = self.lobbys.get(conn_info.get("lobby_code"))
                        _session_muted = bereich == "session" and _lobby_mute and mid in _lobby_mute.muted
                        _global_muted = bereich != "session" and mid in self.global_muted
                        if (_session_muted or _global_muted) and not _is_muted_admin:
                            await self._ws_send(ws, json.dumps({"typ": "system_msg",
                                "text": "Du bist stummgeschaltet."}, ensure_ascii=False))
                            continue
                        if text:
                            name = self.online_users[mid]["name"]
                            gid = self.online_users[mid].get("google_id") or ""
                            log_chat(name, text, bereich=bereich, google_id=gid)
                            ts = datetime.now().strftime("%d.%m.%Y %H:%M")
                            msg = {"typ": "chat_nachricht", "name": name, "text": text,
                                   "bereich": bereich, "google_id": gid, "ts": ts, "ts_epoch": int(time.time() * 1000),
                                   "profil": self._profil_daten(gid)}
                            if bereich == "session":
                                lobby = self.lobbys.get(conn_info.get("lobby_code"))
                                if lobby:
                                    lobby.session_chat.append({"name": name, "text": text})
                                    await lobby.broadcast(msg)
                            else:
                                self.global_chat.append({"name": name, "text": text,
                                                         "google_id": gid, "ts": ts})
                                if len(self.global_chat) > GLOBAL_CHAT_MAX:
                                    self.global_chat.pop(0)
                                _save_global_chat(self.global_chat)
                                await self._broadcast_alle(msg)
                            # @mention Benachrichtigungen
                            import re as _re
                            for _mention in _re.findall(r"@(\S+)", text):
                                _target_mid = next(
                                    (m for m, u in self.online_users.items()
                                     if u.get("name", "").lower() == _mention.lower() and m != mid),
                                    None
                                )
                                if _target_mid:
                                    _tws = self.online_users[_target_mid].get("ws")
                                    if _tws:
                                        try:
                                            await _tws.send(json.dumps({
                                                "typ": "mention", "von": name,
                                                "text": text, "bereich": bereich
                                            }, ensure_ascii=False))
                                        except Exception:
                                            pass

                elif aktion == "chat_befehl":
                    _raw_befehl = str(data.get("befehl", "")).strip()
                    _bereich = data.get("bereich", "global")
                    conn_info = self.verbindungen.get(ws, {})
                    mid = conn_info.get("manager_id")
                    gid = (self.online_users.get(mid) or {}).get("google_id") if mid else None
                    _is_admin = False
                    if gid:
                        profil = ProfileManager.get_profile(gid)
                        email = (profil.get("email", "") if profil else "").lower()
                        _is_admin = email in _OWNER_EMAILS
                    _lobby = self.lobbys.get(conn_info.get("lobby_code"))
                    _is_ersteller = _lobby and mid and _lobby.ersteller_id == mid
                    _ERSTELLER_CMDS = {"weiter", "kick", "mute", "unmute"}
                    _parts = _raw_befehl.split()
                    _cmd = _parts[0].lower().lstrip('/') if _parts else ""
                    _allowed = _is_admin or (_is_ersteller and _cmd in _ERSTELLER_CMDS)
                    if not _allowed:
                        pass
                    else:
                        _parts = _raw_befehl.split()
                        _cmd = _parts[0].lower() if _parts else ""
                        _args = _parts[1:]
                        _gs = _lobby.game_state if _lobby else None

                        async def _admin_reply(text: str):
                            await self._ws_send(ws, json.dumps({"typ": "admin_result", "text": text}, ensure_ascii=False))

                        def _fuzzy_team(name_parts: list) -> str | None:
                            """Findet einen Teamnamen case-insensitiv (vollständiger oder Teil-Match)."""
                            if not _gs or not name_parts:
                                return None
                            query = " ".join(name_parts).lower()
                            for tn in _gs.teams:
                                if tn.lower() == query:
                                    return tn
                            for tn in _gs.teams:
                                if query in tn.lower():
                                    return tn
                            return None

                        if _cmd == "clear":
                            self.global_chat.clear()
                            _save_global_chat(self.global_chat)
                            await self._broadcast_alle({"typ": "chat_geleert"})

                        elif _cmd == "weiter":
                            if not _lobby:
                                await _admin_reply("Kein aktives Spiel gefunden.")
                            elif _lobby.phase == "management":
                                # Alle als bereit markieren und Phase starten
                                for _m in list(_lobby.spieler.keys()):
                                    _lobby.bereit.add(_m)
                                if _lobby.alle_bereit():
                                    _lobby.bereit.clear()
                                    _lobby.phase_task = asyncio.create_task(self._naechste_phase(_lobby))
                                    await _admin_reply("Spieltag wird gestartet.")
                                else:
                                    await _admin_reply("Bereit gesetzt, aber nicht alle Manager online?")
                            else:
                                await _admin_reply(f"Nicht in Management-Phase (aktuell: {_lobby.phase}).")

                        elif _cmd == "phase":
                            if not _lobby:
                                await _admin_reply("Kein aktives Spiel gefunden.")
                            else:
                                gs_info = f"Spieltag {_gs.spieltag}" if _gs else "kein GameState"
                                bereit_count = len(_lobby.bereit)
                                total = len(_lobby.spieler)
                                await _admin_reply(
                                    f"Phase: {_lobby.phase} | {gs_info} | Bereit: {bereit_count}/{total}")

                        elif _cmd == "kick":
                            if _bereich != "session":
                                await _admin_reply("/kick nur im Session-Chat verfügbar.")
                            elif not _args:
                                await _admin_reply("Verwendung: /kick <name>")
                            elif not _lobby:
                                await _admin_reply("Kein aktives Spiel gefunden.")
                            else:
                                _target_name = " ".join(_args).lower()
                                _kicked_mid = None
                                for _km, _kinfo in _lobby.spieler.items():
                                    if _kinfo.get("name", "").lower() == _target_name:
                                        _kicked_mid = _km
                                        break
                                if not _kicked_mid:
                                    await _admin_reply(f"Spieler '{' '.join(_args)}' nicht gefunden.")
                                else:
                                    _kws = _lobby.spieler[_kicked_mid].get("ws")
                                    if _kws:
                                        await _kws.send(json.dumps({"typ": "kicked",
                                            "grund": "Vom Admin aus der Lobby entfernt."}, ensure_ascii=False))
                                    _kname = _lobby.spieler[_kicked_mid].get("name", _kicked_mid)
                                    _lobby.spieler.pop(_kicked_mid, None)
                                    _lobby.bereit.discard(_kicked_mid)
                                    _lobby.muted.discard(_kicked_mid)
                                    if _kicked_mid in self.online_users:
                                        self.online_users[_kicked_mid].pop("lobby_code", None)
                                    for _cws, _cinfo in self.verbindungen.items():
                                        if _cinfo.get("manager_id") == _kicked_mid:
                                            _cinfo["lobby_code"] = None
                                    await _lobby.broadcast({"typ": "system_msg",
                                        "text": f"{_kname} wurde vom Admin entfernt."})
                                    await _admin_reply(f"{_kname} wurde gekickt.")

                        elif _cmd == "announce":
                            if not _args:
                                await _admin_reply("Verwendung: /announce <text>")
                            else:
                                _text = " ".join(_args)
                                await self._broadcast_alle({"typ": "system_msg", "text": f"[ADMIN] {_text}"})
                                await _admin_reply("Ankündigung gesendet.")

                        elif _cmd == "mute":
                            if not _args:
                                await _admin_reply("Verwendung: /mute <name>")
                            else:
                                _target_name = " ".join(_args).lower()
                                # Suche in Lobby-Spielern oder global online
                                _target_mid = None
                                _target_display = None
                                if _bereich == "session" and _lobby:
                                    _target_mid = next((m for m, i in _lobby.spieler.items()
                                                        if i.get("name", "").lower() == _target_name), None)
                                    if _target_mid:
                                        _target_display = _lobby.spieler[_target_mid].get("name")
                                else:
                                    _target_mid = next((m for m, i in self.online_users.items()
                                                        if i.get("name", "").lower() == _target_name), None)
                                    if _target_mid:
                                        _target_display = self.online_users[_target_mid].get("name")
                                if not _target_mid:
                                    await _admin_reply(f"Spieler '{' '.join(_args)}' nicht gefunden.")
                                elif _bereich == "session":
                                    if not _lobby:
                                        await _admin_reply("Kein aktives Spiel gefunden.")
                                    else:
                                        _lobby.muted.add(_target_mid)
                                        await _admin_reply(f"{_target_display} im Session-Chat stummgeschaltet.")
                                        _tws = self.online_users.get(_target_mid, {}).get("ws")
                                        if _tws:
                                            try:
                                                await _tws.send(json.dumps({"typ": "system_msg",
                                                    "text": "Du wurdest im Session-Chat stummgeschaltet."}, ensure_ascii=False))
                                            except Exception:
                                                pass
                                else:
                                    self.global_muted.add(_target_mid)
                                    await _admin_reply(f"{_target_display} im globalen Chat stummgeschaltet.")
                                    _tws = self.online_users.get(_target_mid, {}).get("ws")
                                    if _tws:
                                        try:
                                            await _tws.send(json.dumps({"typ": "system_msg",
                                                "text": "Du wurdest im globalen Chat stummgeschaltet."}, ensure_ascii=False))
                                        except Exception:
                                            pass

                        elif _cmd == "unmute":
                            if not _args:
                                await _admin_reply("Verwendung: /unmute <name>")
                            else:
                                _target_name = " ".join(_args).lower()
                                _target_mid = None
                                _target_display = None
                                if _bereich == "session" and _lobby:
                                    _target_mid = next((m for m, i in _lobby.spieler.items()
                                                        if i.get("name", "").lower() == _target_name), None)
                                    if _target_mid:
                                        _target_display = _lobby.spieler[_target_mid].get("name")
                                else:
                                    _target_mid = next((m for m, i in self.online_users.items()
                                                        if i.get("name", "").lower() == _target_name), None)
                                    if _target_mid:
                                        _target_display = self.online_users[_target_mid].get("name")
                                if not _target_mid:
                                    await _admin_reply(f"Spieler '{' '.join(_args)}' nicht gefunden.")
                                elif _bereich == "session":
                                    if not _lobby:
                                        await _admin_reply("Kein aktives Spiel gefunden.")
                                    else:
                                        _lobby.muted.discard(_target_mid)
                                        await _admin_reply(f"{_target_display} im Session-Chat entstummt.")
                                        _tws = self.online_users.get(_target_mid, {}).get("ws")
                                        if _tws:
                                            try:
                                                await _tws.send(json.dumps({"typ": "system_msg",
                                                    "text": "Du wurdest im Session-Chat entstummt."}, ensure_ascii=False))
                                            except Exception:
                                                pass
                                else:
                                    self.global_muted.discard(_target_mid)
                                    await _admin_reply(f"{_target_display} im globalen Chat entstummt.")
                                    _tws = self.online_users.get(_target_mid, {}).get("ws")
                                    if _tws:
                                        try:
                                            await _tws.send(json.dumps({"typ": "system_msg",
                                                "text": "Du wurdest im globalen Chat entstummt."}, ensure_ascii=False))
                                        except Exception:
                                            pass

                        elif _cmd == "status":
                            lines = []
                            for _lc, _lb in self.lobbys.items():
                                _lgs = _lb.game_state
                                _online = [i.get("name") for i in _lb.spieler.values() if i.get("ws")]
                                _offline = [i.get("name") for i in _lb.spieler.values() if not i.get("ws")]
                                st_info = f"ST{_lgs.spieltag}" if _lgs else "—"
                                lines.append(f"[{_lc}] {_lb.phase} {st_info} | Online: {', '.join(_online) or '—'}"
                                             + (f" | Offline: {', '.join(_offline)}" if _offline else ""))
                            lines.append(f"Globale User online: {len(self.online_users)}")
                            await _admin_reply("\n".join(lines) if lines else "Keine aktiven Lobbys.")

                        elif _cmd == "budget":
                            # /budget <team> <betrag>  — letztes Token ist Betrag
                            if len(_args) < 2:
                                await _admin_reply("Verwendung: /budget <team> <betrag>")
                            elif not _gs:
                                await _admin_reply("Kein aktives Spiel in dieser Lobby.")
                            else:
                                try:
                                    _betrag = int(_args[-1])
                                except ValueError:
                                    await _admin_reply("Betrag muss eine ganze Zahl sein.")
                                else:
                                    _tname = _fuzzy_team(_args[:-1])
                                    if not _tname:
                                        await _admin_reply(f"Team '{' '.join(_args[:-1])}' nicht gefunden.")
                                    else:
                                        _gs.teams[_tname].kontostand = _betrag
                                        await _admin_reply(f"{_tname}: Kontostand auf {_betrag:,} DM gesetzt.")

                        elif _cmd == "heal":
                            if not _gs:
                                await _admin_reply("Kein aktives Spiel in dieser Lobby.")
                            else:
                                _count = 0
                                for _t in _gs.teams.values():
                                    for _sp in _t.spieler:
                                        if _sp.verletzt_wochen > 0:
                                            _sp.verletzt_wochen = 0
                                            _count += 1
                                await _admin_reply(f"{_count} verletzte Spieler geheilt.")

                        elif _cmd == "karten":
                            if not _args:
                                await _admin_reply("Verwendung: /karten <team>")
                            elif not _gs:
                                await _admin_reply("Kein aktives Spiel in dieser Lobby.")
                            else:
                                _tname = _fuzzy_team(_args)
                                if not _tname:
                                    await _admin_reply(f"Team '{' '.join(_args)}' nicht gefunden.")
                                else:
                                    for _sp in _gs.teams[_tname].spieler:
                                        _sp.gelbe_karten = 0
                                        _sp.gelbe_karten_zyklus = 0
                                        _sp.gesperrt_wochen = 0
                                        _sp.verletzt_wochen = 0
                                    await _admin_reply(f"{_tname}: Alle Karten/Sperren/Verletzungen zurückgesetzt.")

                        elif _cmd == "stats":
                            # /stats edit <nickname> <feld> <wert>
                            if _args and _args[0].lower() == "edit":
                                # /stats edit <name> <feld> <wert>
                                _edit_args = _args[1:]
                                if len(_edit_args) < 3:
                                    await _admin_reply("Syntax: /stats edit <nickname> <feld> <wert>\nFelder: tore gegentore bester_kontostand wins draws losses total_games total_points beste_saison(reset)")
                                else:
                                    _edit_name = _edit_args[0]
                                    _edit_feld = _edit_args[1].lower()
                                    _edit_wert = " ".join(_edit_args[2:])
                                    # Spieler anhand Nickname suchen
                                    _target_gid = None
                                    for _u in self.online_users.values():
                                        if _u.get("name", "").lower() == _edit_name.lower() and _u.get("google_id"):
                                            _target_gid = _u["google_id"]
                                            break
                                    if not _target_gid:
                                        # Auch offline Profile durchsuchen
                                        for _pf in ProfileManager.list_profiles():
                                            _nn = (_pf.get("nickname") or _pf.get("name") or "").lower()
                                            if _nn == _edit_name.lower():
                                                _target_gid = _pf.get("google_id")
                                                break
                                    if not _target_gid:
                                        await _admin_reply(f"Spieler '{_edit_name}' nicht gefunden.")
                                    else:
                                        _pf = ProfileManager.get_profile(_target_gid)
                                        if not _pf:
                                            await _admin_reply("Profil nicht gefunden.")
                                        else:
                                            _stats = _pf.setdefault("statistics", {})
                                            _erfolge = _pf.setdefault("erfolge", {})
                                            _INT_FELDER = {"tore", "gegentore", "bester_kontostand", "wins", "draws", "losses", "total_games", "total_points", "avg_points_per_season"}
                                            _ERFOLGE_FELDER = {"saisons", "meisterschaften", "dfb_pokale", "ecl_titel", "pokalsieger_titel", "uefacup_titel", "bester_kaderwert"}
                                            async def _stats_refresh_target():
                                                _fresh = ProfileManager.get_profile(_target_gid)
                                                if not _fresh:
                                                    return
                                                _msg = json.dumps({"typ": "profil_refresh",
                                                    "statistics": _fresh.get("statistics", {}),
                                                    "game_history": _fresh.get("game_history", []),
                                                    "erfolge": _fresh.get("erfolge", {}),
                                                }, ensure_ascii=False)
                                                for _u in self.online_users.values():
                                                    if _u.get("google_id") == _target_gid and _u.get("ws"):
                                                        try: await self._ws_send(_u["ws"], _msg)
                                                        except Exception: pass
                                                        break
                                                await self._broadcast_online_spieler()

                                            if _edit_feld in _INT_FELDER:
                                                try:
                                                    _stats[_edit_feld] = int(_edit_wert)
                                                    ProfileManager.force_update(_target_gid, {"statistics": _stats})
                                                    await _admin_reply(f"✓ {_edit_name}.statistics.{_edit_feld} = {int(_edit_wert)}")
                                                    await _stats_refresh_target()
                                                except ValueError:
                                                    await _admin_reply(f"Wert muss eine Zahl sein.")
                                            elif _edit_feld in _ERFOLGE_FELDER:
                                                try:
                                                    _erfolge[_edit_feld] = int(_edit_wert)
                                                    ProfileManager.force_update(_target_gid, {"erfolge": _erfolge})
                                                    await _admin_reply(f"✓ {_edit_name}.erfolge.{_edit_feld} = {int(_edit_wert)}")
                                                    await _stats_refresh_target()
                                                except ValueError:
                                                    await _admin_reply(f"Wert muss eine Zahl sein.")
                                            elif _edit_feld == "beste_saison" and _edit_wert.lower() == "reset":
                                                _stats["beste_saison"] = None
                                                ProfileManager.force_update(_target_gid, {"statistics": _stats})
                                                await _admin_reply(f"✓ {_edit_name}.statistics.beste_saison zurückgesetzt.")
                                                await _stats_refresh_target()
                                            elif _edit_feld == "game_history" and _edit_wert.lower() == "reset":
                                                ProfileManager.force_update(_target_gid, {
                                                    "game_history": [],
                                                    "statistics": {
                                                        "total_games": 0, "wins": 0, "draws": 0, "losses": 0,
                                                        "total_points": 0, "avg_points_per_season": 0,
                                                        "tore": 0, "gegentore": 0, "bester_kontostand": 0, "beste_saison": None,
                                                    },
                                                    "erfolge": {
                                                        "saisons": 0, "meisterschaften": 0,
                                                        "dfb_pokale": 0, "ecl_titel": 0,
                                                        "pokalsieger_titel": 0, "uefacup_titel": 0,
                                                        "bester_kaderwert": 0,
                                                    },
                                                })
                                                await _admin_reply(f"✓ {_edit_name}: Profil komplett zurückgesetzt.")
                                                await _stats_refresh_target()
                                            elif _edit_feld == "full_reset" and _edit_wert.lower() == "reset":
                                                ProfileManager.force_update(_target_gid, {
                                                    "game_history": [],
                                                    "ongoing_games": [],
                                                    "statistics": {
                                                        "total_games": 0, "wins": 0, "draws": 0, "losses": 0,
                                                        "total_points": 0, "avg_points_per_season": 0,
                                                        "tore": 0, "gegentore": 0, "bester_kontostand": 0, "beste_saison": None,
                                                    },
                                                    "erfolge": {
                                                        "saisons": 0, "meisterschaften": 0,
                                                        "dfb_pokale": 0, "ecl_titel": 0,
                                                        "pokalsieger_titel": 0, "uefacup_titel": 0,
                                                        "bester_kaderwert": 0,
                                                    },
                                                })
                                                await _admin_reply(f"✓ {_edit_name}: Profil auf Neuzustand zurückgesetzt (Nickname/Bild/Lieblingsverein bleiben erhalten).")
                                                await _stats_refresh_target()
                                            else:
                                                await _admin_reply(f"Unbekanntes Feld '{_edit_feld}'.\nStatistik: tore gegentore bester_kontostand wins draws losses total_games total_points avg_points_per_season beste_saison(reset)\nErfolge: saisons meisterschaften dfb_pokale ecl_titel pokalsieger_titel uefacup_titel bester_kaderwert\nAlles: game_history(reset) | Neuzustand: full_reset(reset)")
                            elif not _gs:
                                await _admin_reply("Kein aktives Spiel in dieser Lobby.")
                            else:
                                if _args:
                                    _tname = _fuzzy_team(_args)
                                    if not _tname:
                                        await _admin_reply(f"Team '{' '.join(_args)}' nicht gefunden.")
                                    else:
                                        _t = _gs.teams[_tname]
                                        _sp_count = len(_t.spieler)
                                        _verletzt = sum(1 for s in _t.spieler if s.verletzt_wochen > 0)
                                        _gesperrt = sum(1 for s in _t.spieler if s.gesperrt_wochen > 0)
                                        _gelb = sum(1 for s in _t.spieler if s.gelbe_karten_zyklus >= 4)
                                        await _admin_reply(
                                            f"{_tname}\n"
                                            f"Konto: {_t.kontostand:,} DM\n"
                                            f"Spieler: {_sp_count} | Verletzt: {_verletzt} | Gesperrt: {_gesperrt} | Gelbwarnung: {_gelb}"
                                        )
                                else:
                                    # Alle Manager-Teams
                                    lines = [f"Saison {_gs.saison} | Spieltag {_gs.spieltag}"]
                                    for _m, _minfo in (_lobby.spieler.items() if _lobby else {}.items()):
                                        _tn = _minfo.get("team")
                                        _t = _gs.teams.get(_tn)
                                        if _t:
                                            lines.append(f"{_minfo.get('name')}: {_tn} — {_t.kontostand:,} DM")
                                    await _admin_reply("\n".join(lines))

                        else:
                            await _admin_reply(f"Unbekannter Befehl: /{_cmd}")

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.alle_ws.discard(ws)
            if ws in self.verbindungen:
                info = self.verbindungen.pop(ws)
                lobby = self.lobbys.get(info.get("lobby_code"))
                mid = info.get("manager_id")
                if lobby and mid:
                    if lobby.game_key and lobby.game_state:
                        name = lobby.spieler.get(mid, {}).get("name", "Spieler")
                        log_disconnect(name, google_id=info.get("google_id"))
                        is_creator = (mid == lobby.ersteller_id)
                        if is_creator:
                            # Ersteller-Disconnect: speichern, Timer starten – Reconnect-Fenster
                            GameSaver.save_game_state(lobby.game_key, lobby.game_state,
                                                      session_chat=lobby.session_chat)
                            self._mp_autosave(lobby)
                            lobby.spieler_disconnected(mid)
                            timeout = _cfg_int("lobby", "ersteller_reconnect_timeout")
                            log.info(f"↩ {name} (Ersteller) hat Verbindung verloren – warte {timeout}s auf Reconnect.")
                            other_mids = [m for m in lobby.spieler if m != mid]
                            for other_mid in other_mids:
                                other_ws = lobby.spieler.get(other_mid, {}).get("ws")
                                if other_ws:
                                    await self._ws_send(other_ws, json.dumps({
                                        "typ": "ersteller_offline",
                                        "name": name,
                                        "timeout": timeout,
                                    }, ensure_ascii=False))
                            if lobby.close_task and not lobby.close_task.done():
                                lobby.close_task.cancel()
                            lobby.close_task = asyncio.create_task(
                                self._ersteller_reconnect_timeout(lobby, mid, name, timeout)
                            )
                        else:
                            # Nicht-Ersteller: als offline markieren, Lobby bleibt für Reconnect
                            lobby.spieler_disconnected(mid)
                            GameSaver.save_game_state(lobby.game_key, lobby.game_state,
                                                      session_chat=lobby.session_chat)
                            self._mp_autosave(lobby)
                            log.info(f"↩ {name} hat Verbindung verloren.")
                            await lobby.broadcast({"typ": "spieler_offline",
                                                   "manager_id": mid, "name": name})
                            if lobby.alle_bereit():
                                lobby.bereit.clear()
                                lobby.phase_task = asyncio.create_task(self._naechste_phase(lobby))
                    else:
                        # Pre-game: Ersteller-Disconnect löst Lobby für alle auf
                        is_creator = (mid == lobby.ersteller_id)
                        other_mids = [m for m in lobby.spieler if m != mid]
                        if is_creator and other_mids:
                            for other_mid in other_mids:
                                other_ws = lobby.spieler.get(other_mid, {}).get("ws")
                                if other_ws:
                                    await self._ws_send(other_ws, json.dumps({
                                        "typ": "lobby_aufgeloest",
                                        "nachricht": "Die Lobby wurde vom Ersteller geschlossen."
                                    }, ensure_ascii=False))
                                if other_mid in self.online_users:
                                    self.online_users[other_mid]["lobby_code"] = None
                                other_conn = next((c for _, c in self.verbindungen.items()
                                                   if c.get("manager_id") == other_mid), None)
                                if other_conn:
                                    other_conn["lobby_code"] = None
                            if _entferne_lobby_code_aus_chat(self.global_chat, lobby.code):
                                _save_global_chat(self.global_chat)
                                await self._broadcast_alle({"typ": "lobby_code_abgelaufen", "code": lobby.code})
                            self.lobbys.pop(lobby.code, None)
                        else:
                            lobby.spieler_entfernen(mid)
                            if not lobby.spieler:
                                if _entferne_lobby_code_aus_chat(self.global_chat, lobby.code):
                                    _save_global_chat(self.global_chat)
                                    await self._broadcast_alle({"typ": "lobby_code_abgelaufen", "code": lobby.code})
                                self.lobbys.pop(lobby.code, None)
            if manager_id and manager_id in self.online_users:
                # Save last_seen timestamp to profile
                _gid_disc = self.online_users[manager_id].get("google_id")
                if _gid_disc:
                    from datetime import datetime as _dt
                    ProfileManager.update_profile(_gid_disc, {"last_seen": _dt.now().isoformat()})
                # Cancel any existing grace task for this manager
                _existing_grace = self._grace_tasks.pop(manager_id, None)
                if _existing_grace and not _existing_grace.done():
                    _existing_grace.cancel()
                _grace_name = self.online_users[manager_id].get("name", "")
                _grace_lc = self.online_users[manager_id].get("lobby_code")
                # Mark as disconnected (keep in online_users during grace period)
                self.online_users[manager_id]["disconnected"] = True
                self.online_users[manager_id]["ws"] = None
                # Start 5-minute grace period before announcing offline
                self._grace_tasks[manager_id] = asyncio.create_task(
                    self._grace_period_offline(manager_id, _gid_disc, _grace_name, _grace_lc)
                )

    async def _grace_period_offline(self, manager_id: str, google_id, name: str, lobby_code):
        """Wartet 5 Minuten; wenn kein Reconnect, User als offline markieren."""
        await asyncio.sleep(300)
        if manager_id not in self.online_users:
            return
        user = self.online_users.get(manager_id, {})
        if not user.get("disconnected"):
            return  # User hat sich reconnectet
        del self.online_users[manager_id]
        self._grace_tasks.pop(manager_id, None)
        await self._broadcast_online_spieler()
        # Session-Chat-Benachrichtigung falls in einer aktiven Lobby
        if lobby_code:
            lobby = self.lobbys.get(lobby_code)
            if lobby and lobby.game_state:
                await lobby.broadcast({"typ": "chat_nachricht", "name": "Server",
                                       "text": f"{name} ist offline gegangen.",
                                       "bereich": "session", "system": True})

    async def _ersteller_reconnect_timeout(self, lobby: Lobby, creator_mid: str, name: str, timeout: int):
        """Schließt die Lobby wenn der Ersteller sich nicht innerhalb des Timeouts reconnectet."""
        await asyncio.sleep(timeout)
        spieler_info = lobby.spieler.get(creator_mid, {})
        if spieler_info.get("ws") is not None:
            return  # Bereits reconnectet
        log.info(f"Ersteller {name} nicht zurückgekehrt – Lobby {lobby.code} wird geschlossen.")
        if lobby.phase_task and not lobby.phase_task.done():
            lobby.phase_task.cancel()
        other_mids = [m for m in lobby.spieler if m != creator_mid]
        for other_mid in other_mids:
            other_ws = lobby.spieler.get(other_mid, {}).get("ws")
            if other_ws:
                await self._ws_send(other_ws, json.dumps({
                    "typ": "lobby_aufgeloest",
                    "nachricht": f"{name} (Ersteller) ist nicht zurückgekehrt. Spiel gespeichert."
                }, ensure_ascii=False))
            if other_mid in self.online_users:
                self.online_users[other_mid]["lobby_code"] = None
            other_conn = next((c for _, c in self.verbindungen.items()
                               if c.get("manager_id") == other_mid), None)
            if other_conn:
                other_conn["lobby_code"] = None
        if _entferne_lobby_code_aus_chat(self.global_chat, lobby.code):
            _save_global_chat(self.global_chat)
            await self._broadcast_alle({"typ": "lobby_code_abgelaufen", "code": lobby.code})
        self.lobbys.pop(lobby.code, None)

    async def _naechste_phase(self, lobby: Lobby):
        """Wechselt zur nächsten Spielphase"""
        if lobby.phase == "management":
            lobby.phase = "spiel"
            lobby.game_state.phase = "spiel"
            await self._broadcast_online_spieler()
            await lobby.broadcast({"typ": "phase", "phase": "spiel"})
            await self._spieltag_ausfuehren(lobby)
        elif lobby.phase == "spiel":
            # Ausstehende Cup-Events abarbeiten; Cup ohne Manager-Beteiligung direkt durchlaufen
            while lobby.pending_pokal_events:
                wettbewerb, runde, leg = lobby.pending_pokal_events.pop(0)
                if wettbewerb == "dfb":
                    hat_manager = await self._dfb_runde_ausfuehren(lobby, runde)
                else:
                    hat_manager = await self._europa_runde_ausfuehren(lobby, wettbewerb, runde, leg)
                if hat_manager:
                    # pokal_runde_ende wurde gesendet – auf Weiter des Clients warten
                    return
                # Kein Manager beteiligt → nächsten Event sofort verarbeiten
            # Keine Events mehr → Management-Phase
            gs = lobby.game_state
            gs.naechster_spieltag()
            if gs.spieltag > 34:
                await self._saison_abschluss(lobby)
                return
            lobby.phase = "management"
            gs.phase = "management"
            await self._broadcast_online_spieler()
            lobby.transfermarkt.neue_woche()
            from engine.cpu_ai import cpu_woche as _cpu_woche
            _cpu_woche(gs, lobby.transfermarkt, news_items=lobby.news_items)
            lobby.transfermarkt.neue_woche_angebote()
            if lobby.game_key:
                GameSaver.save_game_state(lobby.game_key, gs, session_chat=lobby.session_chat, transfermarkt=lobby.transfermarkt)
                self._mp_autosave(lobby)
            await self._sende_management_phase(lobby)
        elif lobby.phase == "saison_zusammenfassung":
            lobby.phase = "management"
            await self._broadcast_online_spieler()
            lobby.transfermarkt.neue_woche()
            from engine.cpu_ai import cpu_woche as _cpu_woche
            _cpu_woche(lobby.game_state, lobby.transfermarkt, news_items=lobby.news_items)
            lobby.transfermarkt.neue_woche_angebote()
            if lobby.game_key:
                GameSaver.save_game_state(lobby.game_key, lobby.game_state, session_chat=lobby.session_chat, transfermarkt=lobby.transfermarkt)
                self._mp_autosave(lobby)
            await self._sende_management_phase(lobby)

    def _compute_pokal_uebersicht(self, gs) -> dict:
        """Berechnet den Pokal-Status aller Manager-Teams für die Übersicht."""
        WB_NAMEN = {
            "dfb":         "DFB-Pokal",
            "ecl":         "Landesmeister-Pokal",
            "pokalsieger": "Pokalsieger-Cup",
            "uefacup":     "UEFA-Pokal",
        }
        manager_teams = {n for n, t in gs.teams.items() if t.ist_menschlich}
        competitions = []
        if gs.dfb_pokal_bracket:
            competitions.append(("dfb", gs.dfb_pokal_bracket))
        for wb in ["ecl", "pokalsieger", "uefacup"]:
            if wb in gs.europa_brackets:
                competitions.append((wb, gs.europa_brackets[wb]))

        # Hilfsfunktion: Spieltag-Nummer für (wb, runde) im Kalender
        def _cup_spieltag(wb_key: str, runde: str):
            for st, events in EUROPA_KALENDER.items():
                for wb, r, _ in events:
                    if wb == wb_key and r == runde:
                        return st
            return None

        result = {}
        for wb_key, bracket in competitions:
            runden_folge = RUNDEN_FOLGE[wb_key]
            team_status = {}
            for team in manager_teams:
                in_comp = any(
                    team in (p["heim"], p["gast"])
                    for paarungen in bracket["runden"].values()
                    for p in paarungen
                )
                if not in_comp:
                    team_status[team] = {"s": "nicht_qualifiziert"}
                    continue
                st = None
                for runde_name in runden_folge:
                    for p in bracket["runden"].get(runde_name, []):
                        if team not in (p["heim"], p["gast"]):
                            continue
                        if p.get("sieger") is None:
                            entry = {"s": "aktiv", "runde": runde_name,
                                     "naechster_spieltag": _cup_spieltag(wb_key, runde_name)}
                            if p.get("typ") == "hinrueck" and p.get("hin_heim") is not None:
                                entry["hin"] = {
                                    "heim": p["heim"], "gast": p["gast"],
                                    "ht": p["hin_heim"], "gt": p["hin_gast"],
                                }
                            st = entry
                        elif p["sieger"] != team:
                            st = {"s": "ausgeschieden", "in_runde": runde_name}
                        break  # nur eine Paarung pro Team pro Runde
                    if st:
                        break
                team_status[team] = st or {"s": "sieger"}
            # Aktuelle Runde + offene Paarungen (erste Runde ohne Sieger)
            aktuelle_runde = None
            aktuelle_paarungen = []
            for runde_name in runden_folge:
                runde_paare = bracket["runden"].get(runde_name, [])
                offene = [p for p in runde_paare if p.get("sieger") is None]
                if offene:
                    aktuelle_runde = runde_name
                    for p in offene:
                        eintrag = {"heim": p["heim"], "gast": p["gast"], "typ": p.get("typ", "einzel")}
                        if p.get("typ") == "hinrueck" and p.get("hin_heim") is not None:
                            # Rückspiel: hin_* enthält Hinspiel-Ergebnis (aus Sicht des orig. Heimteams)
                            eintrag["hin_heim"] = p["hin_heim"]
                            eintrag["hin_gast"] = p["hin_gast"]
                        aktuelle_paarungen.append(eintrag)
                    break
            result[wb_key] = {"name": WB_NAMEN.get(wb_key, wb_key.upper()), "teams": team_status,
                              "aktuelle_runde": aktuelle_runde, "aktuelle_paarungen": aktuelle_paarungen}
        return result

    def _pruefe_tabellen_meilensteine(self, lobby: "Lobby"):
        """
        Prüft in den letzten 4 Spieltagen, ob Vereine rechnerisch Meister,
        UEFA-Cup-Qualifikant oder Absteiger sind.
        Neu bestätigte Ereignisse werden als Ticker-Meldungen in lobby.news_items eingefügt.
        """
        gs = lobby.game_state
        if gs.spieltag <= 28:
            return

        tabelle = gs.get_tabelle(1)
        if len(tabelle) < 6:
            return

        GESAMT_SPIELE = 34  # 18 Teams, doppelter Rundenturnier

        def verbleibend(team):
            return max(0, GESAMT_SPIELE - team.spiele)

        # ── Meister ───────────────────────────────────────────────────────────
        key = f"meister:{tabelle[0].name}"
        if key not in lobby.gemeldet_tabellen_ereignisse:
            max_andere = max(
                (t.punkte + verbleibend(t) * 3 for t in tabelle[1:]),
                default=0
            )
            if tabelle[0].punkte > max_andere:
                lobby.gemeldet_tabellen_ereignisse.add(key)
                lobby.news_items.append(
                    random.choice(_MEILENSTEIN_MEISTER).format(
                        team=tabelle[0].name, punkte=tabelle[0].punkte
                    )
                )

        # ── UEFA-Cup-Qualifikation (Plätze 2–5) ───────────────────────────────
        max_ausserhalb = max(
            (t.punkte + verbleibend(t) * 3 for t in tabelle[5:]),
            default=0
        ) if len(tabelle) > 5 else 0
        for team in tabelle[1:5]:
            key = f"uefacup:{team.name}"
            if key not in lobby.gemeldet_tabellen_ereignisse:
                if team.punkte > max_ausserhalb:
                    lobby.gemeldet_tabellen_ereignisse.add(key)
                    lobby.news_items.append(
                        random.choice(_MEILENSTEIN_UEFA).format(team=team.name)
                    )

        # ── Abstieg (Plätze 16–18, direkte Absteiger) ─────────────────────────
        if len(tabelle) >= 16:
            punkte_15 = tabelle[14].punkte  # 15. Platz = erster sicherer Platz
            for team in tabelle[15:]:
                key = f"abstieg:{team.name}"
                if key not in lobby.gemeldet_tabellen_ereignisse:
                    if team.punkte + verbleibend(team) * 3 < punkte_15:
                        lobby.gemeldet_tabellen_ereignisse.add(key)
                        lobby.news_items.append(
                            random.choice(_MEILENSTEIN_ABSTIEG).format(team=team.name)
                        )

    def _generiere_spieltag_news(self, lobby):
        """Generiert Pressestimmen und Schlagzeilen aus dem letzten Spieltag."""
        gs = lobby.game_state
        ergebnisse = lobby.letzte_ergebnisse
        if not ergebnisse:
            return

        spieltag = gs.spieltag
        bl1 = [e for e in ergebnisse if e["liga"] == 1]
        if not bl1:
            return

        menschliche_teams = {n for n, t in gs.teams.items() if t.ist_menschlich}

        # ── Pressestimme: dramatischstes Nicht-Manager-Spiel bevorzugen ──────────
        nicht_mgr = [e for e in bl1
                     if e["heim"] not in menschliche_teams and e["gast"] not in menschliche_teams]
        pool = nicht_mgr if nicht_mgr else bl1
        spiel = max(pool, key=lambda e: abs(e["heim_tore"] - e["gast_tore"]))
        ht, gt = spiel["heim_tore"], spiel["gast_tore"]
        diff = ht - gt
        if diff >= 3:
            tmpl = random.choice(_PRESSE_SIEG_HOCH)
        elif diff >= 1:
            tmpl = random.choice(_PRESSE_SIEG_KNAPP)
        elif diff == 0:
            tmpl = random.choice(_PRESSE_UNENTSCHIEDEN)
        elif diff >= -2:
            tmpl = random.choice(_PRESSE_NIEDERLAGE_KNAPP)
        else:
            tmpl = random.choice(_PRESSE_NIEDERLAGE_HOCH)
        lobby.news_items.append(tmpl.format(heim=spiel["heim"], gast=spiel["gast"], ht=ht, gt=gt))

        # ── Schlagzeile: Tabellenspitze ─────────────────────────────────────────
        tabelle = gs.get_tabelle(1)
        if len(tabelle) >= 2 and spieltag >= 3:
            leader, zweiter = tabelle[0], tabelle[1]
            abstand = leader.punkte - zweiter.punkte
            tmpl = random.choice(_HEADLINE_SPITZE)
            lobby.news_items.append(tmpl.format(
                leader=leader.name, zweiter=zweiter.name,
                abstand=abstand, punkte=leader.punkte, spiele=leader.spiele
            ))

        # ── Schlagzeile: Abstiegskampf (ab 2. Saisonhälfte, 60% Chance) ──────────
        if len(tabelle) >= 16 and spieltag >= 18 and random.random() < 0.60:
            kellerkind = tabelle[15]
            tmpl = random.choice(_HEADLINE_ABSTIEG)
            lobby.news_items.append(tmpl.format(
                kellerkind=kellerkind.name, punkte=kellerkind.punkte,
                spiele=kellerkind.spiele, platz=16
            ))

        # ── Spieltag-Highlight: Torekonto + größter Sieg (40% Chance) ───────────
        if random.random() < 0.40:
            tore_gesamt = sum(e["heim_tore"] + e["gast_tore"] for e in bl1)
            top = max(bl1, key=lambda e: abs(e["heim_tore"] - e["gast_tore"]))
            if top["heim_tore"] != top["gast_tore"]:
                sieger = top["heim"] if top["heim_tore"] > top["gast_tore"] else top["gast"]
                tmpl = random.choice(_HEADLINE_SPIELTAG)
                lobby.news_items.append(tmpl.format(
                    spieltag=spieltag, tore_gesamt=tore_gesamt, sieger=sieger
                ))

    def _news_pokal_runde(self, lobby, wettbewerb: str, runde: str, paarungen: list, menschliche_teams: set):
        """Fügt Pokal-News für Manager-Teams zum Ticker hinzu."""
        WB_LABEL = {"dfb": "DFB-Pokal", "ecl": "Landesmeister-Pokal",
                    "pokalsieger": "Pokalsieger-Cup", "uefacup": "UEFA-Pokal"}
        label = WB_LABEL.get(wettbewerb, wettbewerb)
        for p in paarungen:
            sieger = p.get("sieger")
            if not sieger:
                continue
            for team_name in (p.get("heim"), p.get("gast")):
                if team_name not in menschliche_teams:
                    continue
                if team_name == sieger:
                    if runde == "Finale":
                        tmpl = random.choice(_POKAL_SIEG_TEXTE)
                    else:
                        tmpl = random.choice(_POKAL_WEITER_TEXTE)
                else:
                    tmpl = random.choice(_POKAL_AUS_TEXTE)
                lobby.news_items.append(tmpl.format(team=team_name, pokal=label))

    async def _sende_management_phase(self, lobby: Lobby):
        """Sendet die Management-Phase-Nachrichten an alle Manager."""
        gs = lobby.game_state
        # Nächste Liga-Paarungen berechnen
        naechste_paarungen = []
        if gs.spieltag <= 34:
            spieltag_idx = gs.spieltag - 1
            bl1_teams = [n for n, t in gs.teams.items() if t.liga == 1]
            bl2_teams = [n for n, t in gs.teams.items() if t.liga == 2]
            if not hasattr(gs, '_spielplan') or not gs._spielplan:
                from engine.spielplan import erstelle_liga_spielplan
                gs._spielplan = erstelle_liga_spielplan(bl1_teams, "1bl")
            if not hasattr(gs, '_spielplan_bl2') or not gs._spielplan_bl2:
                from engine.spielplan import erstelle_liga_spielplan
                gs._spielplan_bl2 = erstelle_liga_spielplan(bl2_teams, "2bl")
            if spieltag_idx < len(gs._spielplan):
                naechste_paarungen += [{"heim": p.heim, "gast": p.gast, "liga": 1} for p in gs._spielplan[spieltag_idx]]
            if spieltag_idx < len(gs._spielplan_bl2):
                naechste_paarungen += [{"heim": p.heim, "gast": p.gast, "liga": 2} for p in gs._spielplan_bl2[spieltag_idx]]
        if lobby.news_items:
            mgr_teams = {n for n, t in gs.teams.items() if t.ist_menschlich}
            markiert = []
            for item in lobby.news_items:
                for t in mgr_teams:
                    item = item.replace(t, f"«{t}»")
                markiert.append(item)
            await lobby.broadcast({"typ": "news_ticker", "items": markiert})
            lobby.news_items = []
        pokale = self._compute_pokal_uebersicht(gs)
        # Torschützenliste (alle BL1-Teams)
        _torjaeger = []
        for _tn, _t in gs.teams.items():
            if _t.liga == 1:
                for _sp in _t.kader:
                    if _sp.tore_liga > 0:
                        _torjaeger.append({"name": _sp.name, "team": _tn, "tore": _sp.tore_liga})
        _torjaeger.sort(key=lambda x: -x["tore"])
        _torjaeger = _torjaeger[:10]
        for sp_info in lobby.spieler.values():
            team_name = sp_info["team"]
            team = gs.teams.get(team_name)
            if not team:
                continue
            # Verletzte/gesperrte Spieler automatisch aus Startelf entfernen
            verfuegbar = {s.name for s in team.kader if s.verfuegbar}
            team.startelf = [n for n in team.startelf if n in verfuegbar]
            _gl4 = _gelistet_namen(lobby)
            kader_data = [_spieler_dict(s, s.name in _gl4) for s in team.kader]
            # Cup-Hinweis: gibt es diesen Spieltag ein Pokalspiel für dieses Team?
            naechstes_cup = None
            for _wb, _runde, _leg in EUROPA_KALENDER.get(gs.spieltag, []):
                _bracket = gs.dfb_pokal_bracket if _wb == "dfb" else gs.europa_brackets.get(_wb)
                if not _bracket:
                    continue
                _paarungen = _bracket.get("runden", {}).get(_runde, [])
                if any(team_name in (p.get("heim"), p.get("gast")) for p in _paarungen):
                    naechstes_cup = {"wb": _wb, "runde": _runde}
                    break
            gelistete_eigene = lobby.transfermarkt.get_gelistete_fuer_team(team_name)
            letzter_zv = lobby.transfermarkt.letzte_zwangsverkäufe.get(team_name, [])
            try:
                await sp_info["ws"].send(json.dumps({
                    "typ": "phase",
                    "phase": "management",
                    "kader": kader_data,
                    "startelf": team.startelf,
                    "kontostand": team.kontostand,
                    "saisons_negativ": team.saisons_negativ,
                    "spieltag": gs.spieltag,
                    "saison": gs.saison,
                    "pokale": pokale,
                    "naechstes_cup": naechstes_cup,
                    "kontozins_faktor": _cfg_float("finanzen", "kontozins_faktor"),
                    "kontostand_verlauf": team.kontostand_verlauf[-34:],
                    "torjaeger": _torjaeger,
                    "naechste_paarungen": naechste_paarungen,
                    "tabelle": _tab_data_gs(gs, 1),
                    "tabelle_bl2": _tab_data_gs(gs, 2),
                    "gelistete_spieler_eigene": gelistete_eigene,
                    "letzte_zv": letzter_zv,
                    "finanzen_verlauf": gs.finanzen_verlauf.get(team_name, []),
                }, ensure_ascii=False))
            except Exception:
                pass

    async def _saison_abschluss(self, lobby: Lobby):
        """Zeigt Saisonzusammenfassung und bereitet nächste Saison vor."""
        gs = lobby.game_state

        # Finale Tabelle VOR dem Reset sichern
        tabelle = gs.get_tabelle(1)
        tab_data = [
            {"name": t.name, "spiele": t.spiele, "siege": t.siege,
             "unentschieden": t.unentschieden, "niederlagen": t.niederlagen,
             "tore": t.tore, "gegentore": t.gegentore, "punkte": t.punkte}
            for t in tabelle
        ]
        meister = tabelle[0].name if tabelle else "–"

        # Manager-Team-Stats + Positionen VOR dem Reset sichern (für Profil-Tracking)
        tabelle_bl2_pre = gs.get_tabelle(2)
        _bl2_pos = {t.name: (i + 1) for i, t in enumerate(tabelle_bl2_pre)}
        _bl1_pos = {t.name: (i + 1) for i, t in enumerate(tabelle)}
        _pre_reset_stats = {}
        for _mid, _info in lobby.spieler.items():
            _tn = _info.get("team")
            _t = gs.teams.get(_tn)
            if _t:
                _pos_pre = _bl1_pos.get(_tn) or ((_bl2_pos.get(_tn, 99) + 18) if _bl2_pos.get(_tn) else 99)
                _pre_reset_stats[_tn] = {
                    "punkte": _t.punkte, "tore": _t.tore,
                    "gegentore": _t.gegentore, "kontostand": _t.kontostand,
                    "liga": _t.liga, "final_position": _pos_pre,
                    "siege": _t.siege, "unentschieden": _t.unentschieden,
                    "niederlagen": _t.niederlagen,
                }

        # Finanzen-Verlauf für menschliche Teams aktualisieren (max. 2 Einträge)
        for _tn, _stats in _pre_reset_stats.items():
            eintrag = {
                "saison": gs.saison,
                "position": _stats["final_position"],
                "end_kontostand": _stats["kontostand"],
                "liga": _stats["liga"],
            }
            verlauf = gs.finanzen_verlauf.setdefault(_tn, [])
            verlauf.append(eintrag)
            gs.finanzen_verlauf[_tn] = verlauf[-5:]  # max. 5 Saisons behalten

        # DFB-Pokal Ergebnis
        dfb_sieger = None
        dfb_finalist = None
        if gs.dfb_pokal_bracket:
            finale = gs.dfb_pokal_bracket.get("runden", {}).get("Finale", [])
            if finale and finale[0].get("sieger"):
                dfb_sieger = finale[0]["sieger"]
                p = finale[0]
                dfb_finalist = p["gast"] if dfb_sieger == p["heim"] else p["heim"]

        # Europapokale nächste Saison
        ecl = meister
        if dfb_sieger and dfb_sieger != meister:
            ps_cup = dfb_sieger
        elif dfb_finalist:
            ps_cup = dfb_finalist
        else:
            ps_cup = tabelle[1].name if len(tabelle) > 1 else "–"

        # UEFA-Cup: ab Platz 2, aber bereits für ECL/Pokalsieger qualifizierte
        # Vereine dürfen nicht gleichzeitig im UEFA-Cup stehen (hist. korrekt)
        bereits_europa = {ecl, ps_cup}
        uefacup = []
        for t in tabelle[1:]:
            if t.name not in bereits_europa:
                uefacup.append(t.name)
            if len(uefacup) >= 4:
                break
        # DFB-Finalist erhält UEFA-Cup-Platz, sofern nicht anderweitig qualifiziert
        if (dfb_finalist and dfb_finalist not in bereits_europa
                and dfb_finalist not in uefacup):
            if len(uefacup) >= 4:
                uefacup = uefacup[:3] + [dfb_finalist]
            else:
                uefacup.append(dfb_finalist)

        # BL2-Tabelle holen (wurde simuliert)
        tabelle_bl2 = gs.get_tabelle(2)
        tab_data_bl2 = [
            {"name": t.name, "spiele": t.spiele, "siege": t.siege,
             "unentschieden": t.unentschieden, "niederlagen": t.niederlagen,
             "tore": t.tore, "gegentore": t.gegentore, "punkte": t.punkte}
            for t in tabelle_bl2
        ]

        # ── Auf-/Abstieg berechnen ───────────────────────────────────────────
        # BL1: Platz 16+17+18 direkt abgestiegen (kein Relegationsspiel BL1↔BL2)
        absteiger_bl1 = [t.name for t in tabelle[15:18]] if len(tabelle) >= 18 else []
        # BL2: Platz 1+2+3 direkt aufgestiegen
        aufsteiger_bl2 = [t.name for t in tabelle_bl2[:3]] if len(tabelle_bl2) >= 3 else []

        # BL2: Plätze 17–20 steigen direkt ab; Platz 16 = Relegationsspiel BL2↔Liga3 (noch nicht live)
        absteiger_bl2 = [t.name for t in tabelle_bl2[16:20]] if len(tabelle_bl2) >= 17 else []

        # BL2: 4 direkte Aufsteiger aus Liga-3-Pool (ersetzen die 4 Absteiger)
        liga3_kandidaten = [n for n, t in gs.teams.items() if t.liga == 3]
        if len(liga3_kandidaten) >= 4:
            aufsteiger_bl3 = random.sample(liga3_kandidaten, 4)
        elif liga3_kandidaten:
            aufsteiger_bl3 = liga3_kandidaten[:]
        else:
            aufsteiger_bl3 = []
        liga3_pool = getattr(gs, 'liga3_pool', [])
        eligible_pool = [
            entry["name"] if isinstance(entry, dict) else entry
            for entry in liga3_pool
        ]
        random.shuffle(eligible_pool)
        for kandidat in eligible_pool:
            if len(aufsteiger_bl3) >= 4:
                break
            if kandidat not in aufsteiger_bl3 and kandidat not in gs.teams:
                aufsteiger_bl3.append(kandidat)

        # ── Relegationsspiel BL2 Platz 16 vs Liga-3-Team ────────────────────
        relegation_ergebnis = None
        relegation_sieger = None
        relegation_verlierer = None
        relegation_bl2_team = tabelle_bl2[15].name if len(tabelle_bl2) >= 16 else None
        relegation_liga3_team = liga3_kandidaten[0] if liga3_kandidaten else None

        if relegation_bl2_team and relegation_liga3_team:
            menschliche_rel = {n for n, t in gs.teams.items() if t.ist_menschlich}
            hat_manager_rel = (relegation_bl2_team in menschliche_rel or relegation_liga3_team in menschliche_rel)
            liga3_t = gs.teams.get(relegation_liga3_team)
            bl2_rel_t = gs.teams.get(relegation_bl2_team)
            if liga3_t and bl2_rel_t and hat_manager_rel:
                # Mindestens ein Manager beteiligt → live für alle
                bl2_bleibt = await self._relegation_doppel(
                    lobby, relegation_bl2_team, relegation_liga3_team,
                    label1="2. BUNDESLIGA PLATZ 16",
                    label2="LIGA 3",
                )
            elif liga3_t and bl2_rel_t:
                # Kein Manager beteiligt → instant im Hintergrund
                bl2_bleibt = await self._relegation_instant(
                    bl2_rel_t, liga3_t
                )
            else:
                # Kein Team-Objekt → Zufallswert
                bl2_bleibt = random.random() < 0.65

            if bl2_bleibt:
                relegation_ergebnis = "bleibt"
                relegation_sieger = relegation_bl2_team
                relegation_verlierer = relegation_liga3_team
                # Liga-3-Team das Playoff verloren → bleibt in Liga 3
                aufsteiger_bl3 = [t for t in aufsteiger_bl3 if t != relegation_liga3_team]
            else:
                relegation_ergebnis = "abgestiegen"
                relegation_sieger = relegation_liga3_team
                relegation_verlierer = relegation_bl2_team
                absteiger_bl2.append(relegation_bl2_team)
                # Liga-3-Sieger steigt auf (falls nicht bereits drin)
                if relegation_liga3_team not in aufsteiger_bl3:
                    aufsteiger_bl3.append(relegation_liga3_team)

        alte_saison = gs.saison

        # ── Liga-Wechsel durchführen ────────────────────────────────────────
        for name in absteiger_bl1:
            if name in gs.teams:
                gs.teams[name].liga = 2
        for name in aufsteiger_bl2:
            if name in gs.teams:
                gs.teams[name].liga = 1
        for name in absteiger_bl2:
            if name in gs.teams:
                gs.teams[name].liga = 3
        for name in aufsteiger_bl3:
            if name in gs.teams:
                gs.teams[name].liga = 2
            else:
                # Neues Team aus Liga-3-Pool anlegen
                from engine.game_state import lade_vereine_csv
                from engine.draft import erstelle_cpu_team
                alle_vereine = lade_vereine_csv()
                v_data = next((v for v in alle_vereine if v["name"] == name), None)
                if v_data:
                    gs.teams[name] = erstelle_cpu_team(
                        name, liga=2,
                        staerke_min=v_data["staerke_min"],
                        staerke_max=v_data["staerke_max"],
                    )

        # ── Ausländer-Saisonvariation ────────────────────────────────────────
        from engine.game_state import staerke_label as _slabel
        for team in gs.teams.values():
            for s in team.kader:
                if s.nationalitaet != "A":
                    continue
                if s.staerke_wert_basis > 0:
                    # Temporärer Einbruch war letzte Saison → wiederherstellen
                    s.staerke_wert = s.staerke_wert_basis
                    s.staerke_wert_basis = 0
                    s.staerke_label = _slabel(s.staerke_wert)
                elif s.staerke_wert >= 70 and random.random() < _cfg_float("entwicklung", "auslaender_einbruch_chance"):
                    # Konfigurierbare Chance auf einen schwachen Saisoneinbruch → "Stark"
                    s.staerke_wert_basis = s.staerke_wert
                    s.staerke_wert = random.randint(
                        _cfg_int("entwicklung", "auslaender_einbruch_min"),
                        _cfg_int("entwicklung", "auslaender_einbruch_max"),
                    )
                    s.staerke_label = "Stark"

        # ── Inländer-Saisonentwicklung: konfigurierbare Range, max Sehr stark (84) ──
        _entw_min = _cfg_int("entwicklung", "entwicklung_min")
        _entw_max = _cfg_int("entwicklung", "entwicklung_max")
        for team in gs.teams.values():
            for s in team.kader:
                if s.nationalitaet == "A":
                    continue
                delta = random.randint(_entw_min, _entw_max)
                s.staerke_wert = max(1, min(84, s.staerke_wert + delta))
                s.staerke_label = _slabel(s.staerke_wert)

        # ── Saisonstatistiken und Spielpläne zurücksetzen ──────────────────
        gs.saison += 1
        gs.spieltag = 1
        for team in gs.teams.values():
            team.spiele = team.siege = team.unentschieden = team.niederlagen = 0
            team.tore = team.gegentore = team.punkte = 0
            for s in team.kader:
                s.gelbe_karten = 0
                s.gelbe_karten_zyklus = 0
                s.gesperrt_wochen = 0
                s.tore_liga = 0
                s.tore_pokal = 0
        gs._spielplan = None
        gs._spielplan_bl2 = None

        # ── DFB-Pokal und Europapokale für die neue Saison aufbauen ─────────
        from engine.game_state import erstelle_international_team as _eit
        bl1_neu = [n for n, t in gs.teams.items() if t.liga == 1]
        bl2_neu = [n for n, t in gs.teams.items() if t.liga == 2]
        liga3_in_gs = [n for n, t in gs.teams.items() if t.liga == 3]
        liga3_pool_cfg = getattr(gs, 'liga3_pool', [])
        oberliga_neu = list(liga3_in_gs)
        for entry in liga3_pool_cfg:
            name = entry["name"] if isinstance(entry, dict) else entry
            if name not in gs.teams and name not in oberliga_neu:
                smin = entry.get("staerke_min", 20) if isinstance(entry, dict) else 20
                smax = entry.get("staerke_max", 50) if isinstance(entry, dict) else 50
                t = _eit(name, smin, smax, auslaender=False)
                t.liga = 3
                gs.europa_teams[name] = t
                oberliga_neu.append(name)
        gs.dfb_pokal_bracket = erstelle_dfb_pokal_bracket(bl1_neu, bl2_neu, oberliga_neu)

        # ── Europapokale: Sieger der abgelaufenen Saison ermitteln ──────────
        def _bracket_sieger(wettbewerb):
            b = gs.europa_brackets.get(wettbewerb, {})
            finale = b.get("runden", {}).get("Finale", [])
            return finale[0].get("sieger") if finale else None

        ecl_sieger = _bracket_sieger("ecl")
        pokalsieger_sieger = _bracket_sieger("pokalsieger")
        uefacup_sieger = _bracket_sieger("uefacup")

        _fallback = tabelle[1].name if len(tabelle) > 1 else meister
        gs.europa_brackets = {}
        erstelle_europa_saison(gs, {
            "meister_bl1":            meister,
            "dfb_pokalsieger":        dfb_sieger or _fallback,
            "dfb_pokalfinalist":      dfb_finalist or _fallback,
            "ist_pokalsieger_meister": bool(dfb_sieger and dfb_sieger == meister),
            "uefacup_qualifikanten":  uefacup,
        })
        lobby.pending_pokal_events = []
        lobby.gemeldet_tabellen_ereignisse = set()  # Neue Saison – Meilensteine zurücksetzen

        # Nachwuchs-Spieler für die neue Saison generieren
        from engine.game_state import generiere_nachwuchs
        generiere_nachwuchs(gs)

        # ── Profil-Erfolge aktualisieren ─────────────────────────────────────
        from server.profile_manager import ProfileManager
        for mid, info in lobby.spieler.items():
            google_id = info.get("google_id")
            team_name = info.get("team")
            if not google_id or not team_name:
                continue
            team = gs.teams.get(team_name)
            kaderwert = sum(s.marktwert for s in team.kader) if team else 0
            delta = {
                "meisterschaft": team_name == meister,
                "dfb_pokal":     team_name == dfb_sieger,
                "ecl":           team_name == ecl_sieger,
                "pokalsieger":   team_name == pokalsieger_sieger,
                "uefacup":       team_name == uefacup_sieger,
            }
            ProfileManager.update_erfolge(google_id, delta, kaderwert)
            # Saisonabschluss in Spielhistorie speichern (gesicherte Pre-Reset-Stats)
            _saved = _pre_reset_stats.get(team_name, {})
            from datetime import date as _date
            ProfileManager.add_to_game_history(google_id, {
                "game_key": lobby.game_key or "",
                "date": str(_date.today()),
                "team": team_name,
                "saison": alte_saison,
                "liga": _saved.get("liga", 1),
                "status": "completed",
                "final_position": _saved.get("final_position", 99),
                "punkte": _saved.get("punkte", 0),
                "tore": _saved.get("tore", 0),
                "gegentore": _saved.get("gegentore", 0),
                "kontostand": _saved.get("kontostand", 0),
                "siege": _saved.get("siege", 0),
                "unentschieden": _saved.get("unentschieden", 0),
                "niederlagen": _saved.get("niederlagen", 0),
            })

        # ── Ausstehende Transfermarkt-Verkäufe vor Insolvenzprüfung abwickeln ──
        # Spieler die in Woche 33 gelistet wurden haben woche=1 → Zwangsverkauf jetzt
        import random as _random
        from engine.settings import getfloat as _cfg_float_zv
        _zv_min = _cfg_float_zv("transfer", "zwangsverkauf_min")
        _zv_max = _cfg_float_zv("transfer", "zwangsverkauf_max")
        _zv_peak = _cfg_float_zv("transfer", "zwangsverkauf_peak")
        _noch_gelistet = list(lobby.transfermarkt.gelistete_spieler)
        lobby.transfermarkt.gelistete_spieler = []
        for _sp, _preis, _vk, _w in _noch_gelistet:
            if _w >= 1:  # Woche abgelaufen → Zwangsverkauf
                _erloes = int(_sp.marktwert * _random.triangular(_zv_min, _zv_max, _zv_peak))
                _t = gs.teams.get(_vk)
                if _t:
                    _t.kontostand += _erloes
            # woche=0 Spieler (in Woche 34 gelistet): gelten als zurückgegeben
            else:
                _t = gs.teams.get(_vk)
                if _t:
                    _t.kader.append(_sp)

        # ── Insolvenz-Prüfung ────────────────────────────────────────────────
        from engine.finanzen import saison_abschluss as _finanz_check
        gekickte_manager = []
        for mid, info in list(lobby.spieler.items()):
            team_name = info.get("team")
            team = gs.teams.get(team_name)
            if not team or not team.ist_menschlich:
                continue
            ok, _ = _finanz_check(team)
            stufe = team.saisons_negativ
            if not ok:  # 3. negative Saison → Rauswurf
                _saved = _pre_reset_stats.get(team_name, {})
                # Vergleichsdaten aller anderen menschlichen Manager
                _andere = []
                for _omid, _oinfo in lobby.spieler.items():
                    if _omid == mid:
                        continue
                    _otn = _oinfo.get("team")
                    if not _otn:
                        continue
                    _os = _pre_reset_stats.get(_otn, {})
                    _andere.append({
                        "team": _otn,
                        "name": _oinfo.get("name", _otn),
                        "saison": alte_saison,
                        "position": _os.get("final_position", 99),
                        "end_kontostand": _os.get("kontostand", 0),
                        "liga": _os.get("liga", 1),
                    })
                await lobby.sende_an(mid, {
                    "typ": "insolvenz", "stufe": 3, "team": team_name,
                    "verlauf": gs.finanzen_verlauf.get(team_name, []),
                    "letzte_saison": {
                        "saison": alte_saison,
                        "position": _saved.get("final_position", 99),
                        "end_kontostand": _saved.get("kontostand", 0),
                        "liga": _saved.get("liga", 1),
                    },
                    "andere_manager": _andere,
                })
                gekickte_manager.append(mid)
            elif stufe == 2:
                await lobby.sende_an(mid, {"typ": "insolvenz", "stufe": 2})
            elif stufe == 1:
                await lobby.sende_an(mid, {"typ": "insolvenz", "stufe": 1})

        # ── Entlassung bei BL2-Abstieg ───────────────────────────────────────
        for mid, info in list(lobby.spieler.items()):
            if mid in gekickte_manager:
                continue
            team_name = info.get("team")
            team = gs.teams.get(team_name)
            if not team or not team.ist_menschlich:
                continue
            if team_name in absteiger_bl2:
                team.ist_menschlich = False  # Team wird CPU-geführt
                _saved = _pre_reset_stats.get(team_name, {})
                _andere = []
                for _omid, _oinfo in lobby.spieler.items():
                    if _omid == mid:
                        continue
                    _otn = _oinfo.get("team")
                    if not _otn:
                        continue
                    _os = _pre_reset_stats.get(_otn, {})
                    _andere.append({
                        "team": _otn,
                        "name": _oinfo.get("name", _otn),
                        "saison": alte_saison,
                        "position": _os.get("final_position", 99),
                        "end_kontostand": _os.get("kontostand", 0),
                        "liga": _os.get("liga", 1),
                    })
                await lobby.sende_an(mid, {
                    "typ": "gefeuert", "team": team_name,
                    "verlauf": gs.finanzen_verlauf.get(team_name, []),
                    "letzte_saison": {
                        "saison": alte_saison,
                        "position": _saved.get("final_position", 99),
                        "end_kontostand": _saved.get("kontostand", 0),
                        "liga": _saved.get("liga", 1),
                    },
                    "andere_manager": _andere,
                })
                gekickte_manager.append(mid)

        for mid in gekickte_manager:
            lobby.spieler_entfernen(mid)

        lobby.phase = "saison_zusammenfassung"
        lobby.bereit.clear()
        lobby.news_items = []

        await lobby.broadcast({
            "typ": "saison_abschluss",
            "saison_alt": alte_saison,
            "meister": meister,
            "meister_bl2": tabelle_bl2[0].name if tabelle_bl2 else "–",
            "ecl": ecl,
            "pokalsieger_cup": ps_cup,
            "uefacup": uefacup,
            "dfb_sieger": dfb_sieger or "–",
            "abstieg": absteiger_bl1,
            "aufstieg": aufsteiger_bl2,
            "abstieg_bl2": absteiger_bl2,
            "aufstieg_bl3": aufsteiger_bl3,
            "relegation_bl2_team": relegation_bl2_team,
            "relegation_liga3_team": relegation_liga3_team,
            "relegation_ergebnis": relegation_ergebnis,
            "relegation_sieger": relegation_sieger,
            "relegation_verlierer": relegation_verlierer,
            "tabelle": tab_data,
            "tabelle_bl2": tab_data_bl2,
            "pokale": self._compute_pokal_uebersicht(gs),
        })

        if lobby.game_key:
            GameSaver.save_game_state(lobby.game_key, gs, session_chat=lobby.session_chat, transfermarkt=lobby.transfermarkt)
            self._mp_autosave(lobby)

    async def _relegation_instant(self, bl2_t, liga3_t) -> bool:
        """Berechnet das Relegationsergebnis ohne Live-Anzeige (keine Manager beteiligt)."""
        from engine.match import simulate_match
        erg_hin = await simulate_match(bl2_t, liga3_t, instant=True)
        erg_rueck = await simulate_match(liga3_t, bl2_t, instant=True)
        bl2_gesamt = erg_hin.heim_tore + erg_rueck.gast_tore
        liga3_gesamt = erg_hin.gast_tore + erg_rueck.heim_tore
        if bl2_gesamt != liga3_gesamt:
            return bl2_gesamt > liga3_gesamt
        return random.random() < 0.5

    async def _relegation_doppel(self, lobby, bl1_name: str, bl2_name: str,
                                  label1: str = "2. BUNDESLIGA PLATZ 16",
                                  label2: str = "LIGA 3") -> bool:
        """
        Spielt das Relegations-Doppelspiel live (Hinspiel bl2 Heimrecht, Rückspiel bl1 Heimrecht).
        Gibt True zurück wenn bl1-Team die Klasse hält, False wenn bl2-Team aufsteigt.
        Alle Lobby-Mitglieder schauen zu (broadcast).
        label1/label2: Beschriftung für die Ankündigungs-Einblendung.
        """
        from engine.match import simulate_match
        gs = lobby.game_state
        bl1_t = gs.teams.get(bl1_name)
        bl2_t = gs.teams.get(bl2_name)
        if not bl1_t or not bl2_t:
            return random.random() < 0.60

        menschliche_teams = {n for n, t in gs.teams.items() if t.ist_menschlich}
        lobby.sim_skip[0] = False

        # ── Ankündigung ─────────────────────────────────────────────────────
        await lobby.broadcast({
            "typ": "relegation_ankuendigung",
            "bl1": bl1_name,
            "bl2": bl2_name,
            "label1": label1,
            "label2": label2,
        })
        await asyncio.sleep(4)

        # ── Hinspiel: BL2 spielt zu Hause ───────────────────────────────────
        await lobby.broadcast({
            "typ": "spieltag_start",
            "spieltag": 0,
            "label": "RELEGATION · HINSPIEL",
            "paarungen": [{"heim": bl2_name, "gast": bl1_name, "liga": 2}],
        })

        async def _cb(heim, gast):
            async def cb(minute, ereignis, ergebnis):
                if ereignis.spieler == "ABPFIFF":
                    return
                await lobby.broadcast({
                    "typ": "ticker",
                    "heim": heim, "gast": gast,
                    "minute": minute,
                    "stand": f"{ergebnis.heim_tore}:{ergebnis.gast_tore}",
                    "ereignis": ereignis.typ,
                    "spieler": ereignis.spieler,
                    "team": ereignis.team,
                    "detail": ereignis.detail,
                })
            return cb

        cb_hin = await _cb(bl2_name, bl1_name)
        erg_hin = await simulate_match(
            bl2_t, bl1_t, callback=cb_hin,
            ist_menschlich_heim=(bl2_name in menschliche_teams),
            ist_menschlich_gast=(bl1_name in menschliche_teams),
            skip_ref=lobby.sim_skip,
        )
        await lobby.broadcast({
            "typ": "abpfiff",
            "heim": bl2_name, "gast": bl1_name,
            "heim_tore": erg_hin.heim_tore,
            "gast_tore": erg_hin.gast_tore,
            "einnahmen": 0,
        })

        # ── Zwischenstand nach Hinspiel ──────────────────────────────────────
        await asyncio.sleep(3)
        await lobby.broadcast({
            "typ": "relegation_zwischen",
            "bl1": bl1_name,
            "bl2": bl2_name,
            "hinspiel": f"{erg_hin.heim_tore}:{erg_hin.gast_tore}",  # BL2 Heimrecht
            "bl2_tore": erg_hin.heim_tore,
            "bl1_tore": erg_hin.gast_tore,
        })
        await asyncio.sleep(6)

        # ── Rückspiel: BL1 spielt zu Hause ──────────────────────────────────
        lobby.sim_skip[0] = False
        await lobby.broadcast({
            "typ": "spieltag_start",
            "spieltag": 0,
            "label": "RELEGATION · RÜCKSPIEL",
            "paarungen": [{"heim": bl1_name, "gast": bl2_name, "liga": 1}],
        })

        cb_rueck = await _cb(bl1_name, bl2_name)
        erg_rueck = await simulate_match(
            bl1_t, bl2_t, callback=cb_rueck,
            ist_menschlich_heim=(bl1_name in menschliche_teams),
            ist_menschlich_gast=(bl2_name in menschliche_teams),
            skip_ref=lobby.sim_skip,
        )
        await lobby.broadcast({
            "typ": "abpfiff",
            "heim": bl1_name, "gast": bl2_name,
            "heim_tore": erg_rueck.heim_tore,
            "gast_tore": erg_rueck.gast_tore,
            "einnahmen": 0,
        })

        await asyncio.sleep(3)

        # ── Aggregat ─────────────────────────────────────────────────────────
        # BL2: Hinspiel-Heimtore + Rückspiel-Auswärtstore
        bl2_gesamt = erg_hin.heim_tore + erg_rueck.gast_tore
        # BL1: Hinspiel-Auswärtstore + Rückspiel-Heimtore
        bl1_gesamt = erg_hin.gast_tore + erg_rueck.heim_tore

        muenzwurf = False
        if bl1_gesamt > bl2_gesamt:
            bl1_bleibt = True
        elif bl2_gesamt > bl1_gesamt:
            bl1_bleibt = False
        else:
            # Gleichstand → Münzwurf (historisch: Wiederholungsspiel, hier vereinfacht)
            muenzwurf = True
            bl1_bleibt = random.random() < 0.5

        await lobby.broadcast({
            "typ": "relegation_ergebnis",
            "bl1": bl1_name,
            "bl2": bl2_name,
            "hinspiel": f"{erg_hin.heim_tore}:{erg_hin.gast_tore}",
            "rueckspiel": f"{erg_rueck.heim_tore}:{erg_rueck.gast_tore}",
            "bl1_gesamt": bl1_gesamt,
            "bl2_gesamt": bl2_gesamt,
            "bl1_bleibt": bl1_bleibt,
            "muenzwurf": muenzwurf,
        })
        await asyncio.sleep(10)
        return bl1_bleibt

    async def _spieltag_ausfuehren(self, lobby: Lobby):
        """Führt einen Spieltag durch"""
        from engine.match import simulate_match, MatchErgebnis as _MR
        from engine.finanzen import heimspiel_einnahmen

        async def _forfeit(heim: str, gast: str, abbruch_team: str) -> _MR:
            """Sofortige Aufgabe: Startelf < 7 Spieler"""
            erg = _MR(heim_team=heim, gast_team=gast)
            erg.abbruch = True
            erg.abbruch_team = abbruch_team
            return erg

        lobby.sim_skip[0] = False  # Vorspul-Flag zurücksetzen
        gs = lobby.game_state

        # Paarungen für diesen Spieltag ermitteln
        spieltag_idx = gs.spieltag - 1
        bl1_teams = [n for n, t in gs.teams.items() if t.liga == 1]
        bl2_teams = [n for n, t in gs.teams.items() if t.liga == 2]
        # Spielpläne aus dem GameState oder neu generieren
        if not hasattr(gs, '_spielplan') or not gs._spielplan:
            from engine.spielplan import erstelle_liga_spielplan
            gs._spielplan = erstelle_liga_spielplan(bl1_teams, "1bl")
        if not hasattr(gs, '_spielplan_bl2') or not gs._spielplan_bl2:
            from engine.spielplan import erstelle_liga_spielplan
            gs._spielplan_bl2 = erstelle_liga_spielplan(bl2_teams, "2bl")

        paarungen_bl1 = gs._spielplan[spieltag_idx] if spieltag_idx < len(gs._spielplan) else []
        paarungen_bl2 = gs._spielplan_bl2[spieltag_idx] if spieltag_idx < len(gs._spielplan_bl2) else []
        menschliche_teams = {n for n, t in gs.teams.items() if t.ist_menschlich}

        # Paarungen beider Ligen an Clients senden (mit liga-Feld)
        await lobby.broadcast({"typ": "spieltag_start", "spieltag": gs.spieltag,
            "paarungen": [{"heim": p.heim, "gast": p.gast, "liga": 1} for p in paarungen_bl1] +
                         [{"heim": p.heim, "gast": p.gast, "liga": 2} for p in paarungen_bl2]})

        async def mache_callback(heim_name, gast_name, ist_manager_spiel):
            async def callback(minute, ereignis, ergebnis):
                # Vorspulen: keine Events senden, Simulation läuft still bis zum Ende
                if lobby.sim_skip[0]:
                    return
                # ABPFIFF wird separat als {"typ":"abpfiff"} gesendet
                if ereignis.spieler == "ABPFIFF":
                    return
                stand = f"{ergebnis.heim_tore}:{ergebnis.gast_tore}"
                msg = {
                    "typ": "ticker" if ist_manager_spiel else "ticker_kurz",
                    "heim": heim_name, "gast": gast_name,
                    "minute": minute, "stand": stand,
                    "ereignis": ereignis.typ,
                    "spieler": ereignis.spieler,
                    "team": ereignis.team,
                    "detail": ereignis.detail,
                }
                if ist_manager_spiel:
                    await lobby.broadcast(msg)
                elif ereignis.typ not in ("tick",):
                    await lobby.broadcast(msg)
            return callback

        # ── Alle Spiele beider Ligen gemeinsam parallel simulieren ──────────
        import asyncio
        # Aufgaben als Liste von (paarung, liga, coroutine)
        aufgaben = []
        for paarung in paarungen_bl1:
            heim_t = gs.teams.get(paarung.heim)
            gast_t = gs.teams.get(paarung.gast)
            if not heim_t or not gast_t:
                continue
            ist_manager = paarung.heim in menschliche_teams or paarung.gast in menschliche_teams
            cb = await mache_callback(paarung.heim, paarung.gast, ist_manager)
            if len(heim_t.startelf) < 7:
                aufgaben.append((paarung, 1, _forfeit(paarung.heim, paarung.gast, paarung.heim)))
            elif len(gast_t.startelf) < 7:
                aufgaben.append((paarung, 1, _forfeit(paarung.heim, paarung.gast, paarung.gast)))
            else:
                aufgaben.append((paarung, 1, simulate_match(
                    heim_t, gast_t, callback=cb,
                    ist_menschlich_heim=(paarung.heim in menschliche_teams),
                    ist_menschlich_gast=(paarung.gast in menschliche_teams),
                    skip_ref=lobby.sim_skip)))
        for paarung in paarungen_bl2:
            heim_t = gs.teams.get(paarung.heim)
            gast_t = gs.teams.get(paarung.gast)
            if not heim_t or not gast_t:
                continue
            ist_manager = paarung.heim in menschliche_teams or paarung.gast in menschliche_teams
            cb = await mache_callback(paarung.heim, paarung.gast, ist_manager)
            if len(heim_t.startelf) < 7:
                aufgaben.append((paarung, 2, _forfeit(paarung.heim, paarung.gast, paarung.heim)))
            elif len(gast_t.startelf) < 7:
                aufgaben.append((paarung, 2, _forfeit(paarung.heim, paarung.gast, paarung.gast)))
            else:
                aufgaben.append((paarung, 2, simulate_match(
                    heim_t, gast_t, callback=cb,
                    ist_menschlich_heim=(paarung.heim in menschliche_teams),
                    ist_menschlich_gast=(paarung.gast in menschliche_teams),
                    skip_ref=lobby.sim_skip)))

        ergebnisse = await asyncio.gather(*[a[2] for a in aufgaben])

        # ── Ergebnisse eintragen und Einnahmen berechnen ────────────────────
        for i, (paarung, liga, _) in enumerate(aufgaben):
            if i >= len(ergebnisse):
                break
            erg = ergebnisse[i]
            heim_t = gs.teams.get(paarung.heim)
            gast_t = gs.teams.get(paarung.gast)
            if not heim_t or not gast_t:
                continue
            # Abbruch-Wertung (Liga: 2:0)
            if erg.abbruch:
                if erg.abbruch_team == paarung.heim:
                    # Heim verursacht Abbruch → Gast gewinnt
                    if not (erg.gast_tore - erg.heim_tore >= 2):
                        erg.heim_tore, erg.gast_tore = 0, 2
                else:
                    # Gast verursacht Abbruch → Heim gewinnt
                    if not (erg.heim_tore - erg.gast_tore >= 2):
                        erg.heim_tore, erg.gast_tore = 2, 0
            heim_t.tore += erg.heim_tore; heim_t.gegentore += erg.gast_tore
            gast_t.tore += erg.gast_tore; gast_t.gegentore += erg.heim_tore
            heim_t.spiele += 1; gast_t.spiele += 1
            if erg.heim_tore > erg.gast_tore:
                heim_t.siege += 1; heim_t.punkte += 2; gast_t.niederlagen += 1
            elif erg.heim_tore < erg.gast_tore:
                gast_t.siege += 1; gast_t.punkte += 2; heim_t.niederlagen += 1
            else:
                heim_t.unentschieden += 1; heim_t.punkte += 1
                gast_t.unentschieden += 1; gast_t.punkte += 1
            # Heimspiel-Einnahmen (Tabellenplatz aus der jeweiligen Liga)
            liga_tabelle = gs.get_tabelle(liga)
            tab_heim = next((j+1 for j,t in enumerate(liga_tabelle) if t.name == paarung.heim), 9)
            tab_gast = next((j+1 for j,t in enumerate(liga_tabelle) if t.name == paarung.gast), 9)
            einnahmen = heimspiel_einnahmen(heim_t, gast_t, tab_heim, tab_gast, liga)
            heim_t.kontostand += einnahmen
            if paarung.heim in menschliche_teams or paarung.gast in menschliche_teams:
                await lobby.broadcast({"typ": "abpfiff",
                    "heim": paarung.heim, "gast": paarung.gast,
                    "heim_tore": erg.heim_tore, "gast_tore": erg.gast_tore,
                    "liga": liga,
                    "einnahmen": einnahmen if paarung.heim in menschliche_teams else 0,
                    "ereignisse": [{"minute": e.minute, "typ": e.typ, "spieler": e.spieler,
                                    "team": e.team, "detail": e.detail}
                                   for e in erg.ereignisse if e.typ not in ("tick",)]})

        # ── Ergebnisse für Pressestimmen/Headlines merken ────────────────────
        lobby.letzte_ergebnisse = [
            {"heim": aufgaben[i][0].heim, "gast": aufgaben[i][0].gast,
             "heim_tore": ergebnisse[i].heim_tore, "gast_tore": ergebnisse[i].gast_tore,
             "liga": aufgaben[i][1]}
            for i in range(min(len(aufgaben), len(ergebnisse)))
        ]

        # ── Cup-Events für diesen Spieltag merken (werden nach Weiter ausgeführt) ──
        lobby.pending_pokal_events = list(EUROPA_KALENDER.get(gs.spieltag, []))

        # Tabellen serialisieren und senden
        def _tab_data(liga):
            return [{"name": t.name, "spiele": t.spiele, "siege": t.siege,
                "unentschieden": t.unentschieden, "niederlagen": t.niederlagen,
                "tore": t.tore, "gegentore": t.gegentore, "punkte": t.punkte}
                for t in gs.get_tabelle(liga)]

        # Save game state after matchday
        if lobby.game_key:
            GameSaver.save_game_state(lobby.game_key, lobby.game_state, transfermarkt=lobby.transfermarkt)
            self._mp_autosave(lobby)

        # Nächste Runde ermitteln für Button-Beschriftung
        # Nur anzeigen wenn mindestens ein Manager-Team dabei ist
        _WB_NAMEN = {"dfb": "DFB-POKAL", "ecl": "LANDESMEISTERPOKAL",
                     "pokalsieger": "POKALSIEGER CUP", "uefacup": "UEFA-POKAL"}
        naechste_runde = None
        if lobby.pending_pokal_events:
            _mgr_teams = {n for n, t in gs.teams.items() if t.ist_menschlich}
            wb, runde_next, _ = lobby.pending_pokal_events[0]
            if wb == "dfb" and gs.dfb_pokal_bracket:
                _paarungen = gs.dfb_pokal_bracket.get("runden", {}).get(runde_next, [])
                _hat_mgr = any(
                    p.get("heim") in _mgr_teams or p.get("gast") in _mgr_teams
                    for p in _paarungen
                )
            elif wb in gs.europa_brackets:
                _paarungen = gs.europa_brackets[wb].get("runden", {}).get(runde_next, [])
                _hat_mgr = any(
                    p.get("heim") in _mgr_teams or p.get("gast") in _mgr_teams
                    for p in _paarungen
                )
            else:
                _hat_mgr = False
            if _hat_mgr:
                naechste_runde = _WB_NAMEN.get(wb, wb.upper())

        lobby.weiter_ts = time.time()
        await lobby.broadcast({"typ": "spieltag_ende",
            "spieltag": gs.spieltag,
            "tabelle": _tab_data(1),
            "tabelle_bl2": _tab_data(2),
            "naechste_runde": naechste_runde})

        self._pruefe_tabellen_meilensteine(lobby)
        self._generiere_spieltag_news(lobby)

    async def _elfmeter_schuss(self, lobby, heim_name: str, gast_name: str,
                               schussmannschaft: str, schutze, tw_name: str,
                               tw_staerke: int, ist_manager_spiel: bool,
                               instant: bool,
                               heim_elf: int = 0, gast_elf: int = 0) -> bool:
        """
        Simuliert einen einzelnen Elfmeter. Gibt True zurück wenn Tor.
        Sendet Anlauf- und Ergebnis-Ticker-Meldungen mit Pausen.
        """
        s_name = schutze.name if schutze else "Spieler"
        s_staerke = schutze.staerke_wert if schutze else 60

        # Wahrscheinlichkeiten: Torwart-Stärke beeinflusst Halte-Chance (15-35%)
        miss_chance = max(0.04, 0.10 - s_staerke / 1000)
        save_chance = 0.15 + tw_staerke / 100 * 0.20
        roll = random.random()
        ist_miss = roll < miss_chance
        ist_gehalten = not ist_miss and roll < (miss_chance + save_chance)
        ist_tor = not ist_miss and not ist_gehalten

        if ist_manager_spiel and not instant:
            anlauf_text = random.choice(_ELF_ANLAUF).format(s=s_name, tw=tw_name)
            await lobby.broadcast({
                "typ": "ticker",
                "heim": heim_name, "gast": gast_name,
                "wettbewerb": "", "runde": "",
                "minute": 120,
                "ereignis": "elfmeter_anlauf",
                "spieler": anlauf_text, "team": schussmannschaft, "detail": "",
            })
            await asyncio.sleep(random.uniform(4.0, 7.0))

            if ist_tor:
                ergebnis_text = random.choice(_ELF_TOR).format(s=s_name, tw=tw_name)
                neuer_heim = heim_elf + (1 if schussmannschaft == heim_name else 0)
                neuer_gast = gast_elf + (1 if schussmannschaft == gast_name else 0)
                ergebnis_text += f" [{neuer_heim}:{neuer_gast} n.E.]"
            else:
                ergebnis_text = random.choice(_ELF_GEHALTEN).format(s=s_name, tw=tw_name)

            await lobby.broadcast({
                "typ": "ticker_append",
                "heim": heim_name, "gast": gast_name,
                "text": f" → {ergebnis_text}",
                "tor": ist_tor,
                "team": schussmannschaft,
            })
        return ist_tor

    async def _simuliere_elfmeterschiessen(self, lobby, heim_name: str, gast_name: str,
                                           heim_t, gast_t,
                                           ist_manager_spiel: bool, instant: bool) -> str:
        """
        Führt ein vollständiges Elfmeterschießen durch (5 Schüsse, dann sudden death).
        Gibt den Namen des Gewinners zurück.
        """
        def _tw_info(team):
            tw = next((s for s in team.kader if s.position == 'T' and s.verfuegbar), None)
            return (tw.name if tw else "Torhüter", tw.staerke_wert if tw else 50)

        def _schutzen(team):
            feldspieler = [s for s in team.kader if s.position != 'T' and s.verfuegbar]
            feldspieler.sort(key=lambda s: -s.staerke_wert)
            if not feldspieler:
                tw = next((s for s in team.kader if s.position == 'T'), None)
                return [tw] if tw else []
            return feldspieler

        heim_tw_name, heim_tw_staerke = _tw_info(heim_t)
        gast_tw_name, gast_tw_staerke = _tw_info(gast_t)
        heim_schutzen = _schutzen(heim_t)
        gast_schutzen = _schutzen(gast_t)

        heim_tore = 0
        gast_tore = 0
        MAX_KICKS = 5
        kick = 0

        while True:
            kick += 1
            h_idx = (kick - 1) % max(1, len(heim_schutzen))
            g_idx = (kick - 1) % max(1, len(gast_schutzen))

            # Heim schießt
            h_schutze = heim_schutzen[h_idx] if heim_schutzen else None
            tor = await self._elfmeter_schuss(
                lobby, heim_name, gast_name, heim_name,
                h_schutze, gast_tw_name, gast_tw_staerke,
                ist_manager_spiel, instant,
                heim_elf=heim_tore, gast_elf=gast_tore,
            )
            if tor:
                heim_tore += 1

            # Frühzeitiger Sieg (Heim kann nicht mehr eingeholt werden)?
            if kick >= MAX_KICKS:
                gast_max = gast_tore + (MAX_KICKS - (kick - 1))
                if heim_tore > gast_max:
                    return heim_name, heim_tore, gast_tore
            elif kick < MAX_KICKS:
                gast_max = gast_tore + (MAX_KICKS - kick + 1)
                if heim_tore > gast_max:
                    return heim_name, heim_tore, gast_tore

            # Gast schießt
            g_schutze = gast_schutzen[g_idx] if gast_schutzen else None
            tor = await self._elfmeter_schuss(
                lobby, heim_name, gast_name, gast_name,
                g_schutze, heim_tw_name, heim_tw_staerke,
                ist_manager_spiel, instant,
                heim_elf=heim_tore, gast_elf=gast_tore,
            )
            if tor:
                gast_tore += 1

            # Frühzeitiger Sieg (Gast kann nicht mehr eingeholt werden)?
            if kick < MAX_KICKS:
                heim_max = heim_tore + (MAX_KICKS - kick)
                if gast_tore > heim_max:
                    return gast_name, heim_tore, gast_tore

            # Nach 5 Runden: Sieger oder Sudden Death?
            if kick >= MAX_KICKS:
                if heim_tore != gast_tore:
                    break
                MAX_KICKS += 1  # eine weitere Runde (sudden death)

            if kick > 20:  # Sicherheits-Limit
                break

        return heim_name if heim_tore >= gast_tore else gast_name, heim_tore, gast_tore

    async def _cup_match_ausfuehren(self, lobby, heim_name: str, gast_name: str,
                                     wettbewerb: str, runde: str,
                                     split_einnahmen: bool = False,
                                     hinspiel_heim: int = None,
                                     hinspiel_gast: int = None,
                                     ist_hinspiel: bool = False,
                                     instant: bool = False) -> tuple:
        """
        Führt ein einzelnes Pokalspiel aus inkl. Verlängerung + Elfmeter bei Unentschieden.
        Gibt (heim_tore, gast_tore, elfmeter_sieger) zurück.
        hinspiel_heim/gast: falls gesetzt, wird nach Aggregatgleichstand + Auswärtstore VL geprüft.
        """
        from engine.match import simulate_match
        from engine.finanzen import internationale_einnahmen, heimspiel_einnahmen

        gs = lobby.game_state
        heim_t = gs.get_team(heim_name)
        gast_t = gs.get_team(gast_name)
        if not heim_t or not gast_t:
            return 0, 0, None

        menschliche_teams = {n for n, t in gs.teams.items() if t.ist_menschlich}
        ist_heim_m = heim_name in menschliche_teams
        ist_gast_m = gast_name in menschliche_teams
        ist_manager_spiel = ist_heim_m or ist_gast_m

        # Offset für kumulative Anzeige während Verlängerung: [heim, gast]
        _score_offset = [0, 0]
        # Flag ob wir in der VL sind (ABPFIFF bei 90' unterdrücken, bei 120' zeigen)
        _in_vl = [False]
        # Elfmeter-Ergebnis (wird gesetzt wenn Elfmeterschießen stattfindet)
        elf_heim = 0
        elf_gast = 0

        async def cb(minute, ereignis, ergebnis):
            # Vorspulen: keine Events senden, Simulation läuft still bis zum Ende
            if lobby.sim_skip[0]:
                return
            # Debug-Flags: stumm schalten
            if lobby.debug_force_vl[0] or lobby.debug_force_elf[0]:
                return
            # ABPFIFF immer unterdrücken – das WebSocket-"abpfiff"-Event übernimmt
            # die finale Anzeige (inkl. n.V./n.E.-Suffix)
            if ereignis.spieler == "ABPFIFF":
                return
            if ereignis.typ == "tick" and not ist_manager_spiel:
                if minute % 15 != 0:
                    return
            ht_anz = _score_offset[0] + ergebnis.heim_tore
            gt_anz = _score_offset[1] + ergebnis.gast_tore
            stand = f"{ht_anz}:{gt_anz}"
            await lobby.broadcast({
                "typ": "ticker" if ist_manager_spiel else "ticker_kurz",
                "heim": heim_name, "gast": gast_name,
                "wettbewerb": wettbewerb, "runde": runde,
                "minute": minute, "stand": stand,
                "ereignis": ereignis.typ, "spieler": ereignis.spieler,
                "team": ereignis.team, "detail": ereignis.detail if ereignis.detail else stand,
            })

        from engine.match import MatchErgebnis as _MR
        if len(heim_t.startelf) < 7:
            erg = _MR(heim_team=heim_name, gast_team=gast_name)
            erg.abbruch = True; erg.abbruch_team = heim_name
        elif len(gast_t.startelf) < 7:
            erg = _MR(heim_team=heim_name, gast_team=gast_name)
            erg.abbruch = True; erg.abbruch_team = gast_name
        else:
            erg = await simulate_match(
                heim_t, gast_t, callback=cb,
                ist_menschlich_heim=ist_heim_m,
                ist_menschlich_gast=ist_gast_m,
                instant=instant,
                skip_ref=lobby.sim_skip,
                ist_pokal=True,
            )

        # Abbruch-Wertung (International/Pokal: 3:0)
        if erg.abbruch:
            if erg.abbruch_team == heim_name:
                # Heim verursacht Abbruch → Gast gewinnt
                if not (erg.gast_tore - erg.heim_tore >= 3):
                    erg.heim_tore, erg.gast_tore = 0, 3
            else:
                # Gast verursacht Abbruch → Heim gewinnt
                if not (erg.heim_tore - erg.gast_tore >= 3):
                    erg.heim_tore, erg.gast_tore = 3, 0

        ht = erg.heim_tore
        gt = erg.gast_tore
        elfmeter_sieger = None
        _alle_ereignisse = list(erg.ereignisse)

        # Debug: Verlängerung erzwingen (Ergebnis auf Unentschieden setzen)
        if lobby.debug_force_vl[0]:
            lobby.debug_force_vl[0] = False
            gt = ht  # Gleichstand erzwingen
            if not lobby.debug_force_elf[0]:
                lobby.sim_skip[0] = False  # VL normal abspielen

        def _braucht_verlaengerung(ht_aktuell, gt_aktuell):
            """Prüft ob Verlängerung nötig ist."""
            if ist_hinspiel:
                return False  # Hinspiel: kein VL, kein Elfmeter – Unentschieden ist gültig
            if hinspiel_heim is None:
                # Einzelspiel (DFB-Pokal, Finale): Unentschieden → VL+Elfmeter
                return ht_aktuell == gt_aktuell
            else:
                # Rückspiel: Aggregatgleichstand UND Auswärtstore ausgeglichen
                # ht = rueck_heim (original gast's home goals), gt = rueck_gast (original heim's away goals)
                heim_ges = hinspiel_heim + gt_aktuell
                gast_ges = hinspiel_gast + ht_aktuell
                return heim_ges == gast_ges and gt_aktuell == hinspiel_gast

        if _braucht_verlaengerung(ht, gt):
            # Verlängerung ankündigen (einzige Minute-90-Meldung)
            if ist_manager_spiel:
                await lobby.broadcast({
                    "typ": "ticker",
                    "heim": heim_name, "gast": gast_name,
                    "wettbewerb": wettbewerb, "runde": runde,
                    "minute": 90, "stand": f"{ht}:{gt}",
                    "ereignis": "info", "spieler": "VERLÄNGERUNG",
                    "team": "", "detail": "",
                })

            # Score-Offset + VL-Flag setzen damit cb kumulative Tore und korrekten ABPFIFF zeigt
            _score_offset[0] = ht
            _score_offset[1] = gt
            _in_vl[0] = True

            erg_vl = await simulate_match(
                heim_t, gast_t, callback=cb,
                ist_menschlich_heim=ist_heim_m,
                ist_menschlich_gast=ist_gast_m,
                instant=instant,
                skip_ref=lobby.sim_skip,
                ist_pokal=True,
                start_minute=91,
                end_minute=120,
            )
            ht += erg_vl.heim_tore
            gt += erg_vl.gast_tore
            _alle_ereignisse.extend(erg_vl.ereignisse)

            # Abbruch in Verlängerung (International/Pokal: 3:0 auf kumulative Tore)
            if erg_vl.abbruch:
                if erg_vl.abbruch_team == heim_name:
                    if not (gt - ht >= 3):
                        ht, gt = 0, 3
                else:
                    if not (ht - gt >= 3):
                        ht, gt = 3, 0

            # Debug: Elfmeter erzwingen (nach VL auf Unentschieden setzen)
            if lobby.debug_force_elf[0]:
                lobby.debug_force_elf[0] = False
                gt = ht  # Gleichstand nach VL erzwingen
                lobby.sim_skip[0] = False  # Elfmeter normal abspielen

            if _braucht_verlaengerung(ht, gt):
                # Elfmeterschießen ankündigen
                # (sim_skip NICHT zurücksetzen – _elfmeter_schuss nutzt `instant`, nicht skip_ref)
                if ist_manager_spiel:
                    await lobby.broadcast({
                        "typ": "ticker",
                        "heim": heim_name, "gast": gast_name,
                        "wettbewerb": wettbewerb, "runde": runde,
                        "minute": 120, "stand": f"{ht}:{gt}",
                        "ereignis": "info", "spieler": "ELFMETER",
                        "team": "", "detail": "",
                    })
                elfmeter_sieger, elf_heim, elf_gast = await self._simuliere_elfmeterschiessen(  # noqa: F841
                    lobby, heim_name, gast_name, heim_t, gast_t,
                    ist_manager_spiel, instant=instant
                )
                # Endergebnis Elfmeter
                if ist_manager_spiel:
                    await lobby.broadcast({
                        "typ": "ticker",
                        "heim": heim_name, "gast": gast_name,
                        "wettbewerb": wettbewerb, "runde": runde,
                        "minute": 120, "stand": f"{ht}:{gt}",
                        "ereignis": "info", "spieler": "── ELFMETER-SIEGER ──",
                        "team": elfmeter_sieger, "detail": elfmeter_sieger,
                    })

        # Einnahmen
        einnahmen_heim = 0
        einnahmen_gast = 0
        if wettbewerb == "dfb":
            # DFB-Pokal: ein Spiel, beide Teams teilen je die Hälfte
            from engine.finanzen import _POKAL_MULTIPLIKATOR
            liga = heim_t.liga if heim_t.liga in (1, 2) else 1
            tab = gs.get_tabelle(liga)
            pos_h = next((i + 1 for i, t in enumerate(tab) if t.name == heim_name), 9)
            pos_g = next((i + 1 for i, t in enumerate(tab) if t.name == gast_name), 9)
            gesamt = int(heimspiel_einnahmen(heim_t, gast_t, pos_h, pos_g, liga) * _POKAL_MULTIPLIKATOR["dfb"])
            anteil = gesamt // 2
            if ist_heim_m:
                heim_t.kontostand += anteil
                einnahmen_heim = anteil
            if ist_gast_m:
                gast_t.kontostand += anteil
                einnahmen_gast = anteil
        else:
            runde_clean = runde.split(" – ")[0].strip()
            gesamt, anteil = internationale_einnahmen(heim_t, gast_t, wettbewerb, runde_clean)
            if split_einnahmen:
                # Finale/neutrales Stadion: beide Teams teilen je die Hälfte
                if ist_heim_m:
                    heim_t.kontostand += anteil
                    einnahmen_heim = anteil
                if ist_gast_m:
                    gast_t.kontostand += anteil
                    einnahmen_gast = anteil
            else:
                # Hin-/Rückspiel: nur das Heimteam bekommt die vollen Einnahmen
                if ist_heim_m:
                    heim_t.kontostand += gesamt
                    einnahmen_heim = gesamt

        if ist_manager_spiel:
            await lobby.broadcast({
                "typ": "abpfiff",
                "heim": heim_name, "gast": gast_name,
                "wettbewerb": wettbewerb, "runde": runde,
                "heim_tore": ht, "gast_tore": gt,
                "elfmeter_sieger": elfmeter_sieger,
                "elf_heim": elf_heim, "elf_gast": elf_gast,
                "verlängerung": _in_vl[0],
                "einnahmen_heim": einnahmen_heim,
                "einnahmen_gast": einnahmen_gast,
                "einnahmen_geteilt": wettbewerb == "dfb" or split_einnahmen,
                "ereignisse": [{"minute": e.minute, "typ": e.typ, "spieler": e.spieler,
                                "team": e.team, "detail": e.detail}
                               for e in _alle_ereignisse if e.typ not in ("tick",)],
            })

        return ht, gt, elfmeter_sieger

    async def _dfb_runde_ausfuehren(self, lobby, runde: str):
        """Führt eine DFB-Pokal-Runde durch."""
        bracket = lobby.game_state.dfb_pokal_bracket
        if not bracket or bracket.get("aktive_runde") != runde:
            return

        paarungen = bracket["runden"].get(runde, [])
        if not paarungen:
            return

        menschliche_teams = {n for n, t in lobby.game_state.teams.items() if t.ist_menschlich}
        hat_manager = any(
            p["heim"] in menschliche_teams or p["gast"] in menschliche_teams
            for p in paarungen
        )

        lobby.sim_skip[0] = False  # Liga-Vorspul-Flag vor Pokalrunde zurücksetzen

        if hat_manager:
            await lobby.broadcast({"typ": "pokal_runde_start",
                                    "wettbewerb": "dfb", "runde": runde,
                                    "paarungen": [{"heim": p["heim"], "gast": p["gast"]}
                                                  for p in paarungen]})

        aufgaben = []
        for p in paarungen:
            aufgaben.append(self._cup_match_ausfuehren(
                lobby, p["heim"], p["gast"], "dfb", runde, instant=not hat_manager))

        ergebnisse = await asyncio.gather(*aufgaben)

        for p, (ht, gt, elf) in zip(paarungen, ergebnisse):
            p["heim_tore"] = ht
            p["gast_tore"] = gt
            if elf:
                p["elfmeter_sieger"] = elf
            p["sieger"] = bestimme_sieger_einzel(p)

        self._news_pokal_runde(lobby, "dfb", runde, paarungen, menschliche_teams)

        # Nächste Runde auslosen
        naechste_runde_befuellen(bracket, "dfb")

        if hat_manager:
            lobby.weiter_ts = time.time()
            await lobby.broadcast({"typ": "pokal_runde_ende",
                                    "wettbewerb": "dfb", "runde": runde,
                                    "pokale": self._compute_pokal_uebersicht(lobby.game_state),
                                    "ergebnisse": [{"heim": p["heim"], "gast": p["gast"],
                                                    "heim_tore": p["heim_tore"],
                                                    "gast_tore": p["gast_tore"],
                                                    "sieger": p["sieger"]} for p in paarungen]})
        return hat_manager

    async def _europa_runde_ausfuehren(self, lobby, wettbewerb: str,
                                        runde: str, leg: str):
        """Führt ein Hin- oder Rückspiel einer Europacup-Runde durch."""
        brackets = lobby.game_state.europa_brackets
        bracket = brackets.get(wettbewerb)
        if not bracket or bracket.get("aktive_runde") != runde:
            return

        paarungen = bracket["runden"].get(runde, [])
        if not paarungen:
            return

        menschliche_teams = {n for n, t in lobby.game_state.teams.items() if t.ist_menschlich}
        hat_manager = any(
            p.get("heim") in menschliche_teams or p.get("gast") in menschliche_teams
            for p in paarungen
        )

        lobby.sim_skip[0] = False  # Liga-Vorspul-Flag vor Europacup-Runde zurücksetzen

        if hat_manager:
            # Für Rückspiele sind Heim/Gast vertauscht – Schlüssel muss zur ticker-Nachricht passen
            if leg == "rueck":
                paare_liste = [{"heim": p["gast"], "gast": p["heim"],
                                "hin_heim": p.get("hin_heim"), "hin_gast": p.get("hin_gast")} for p in paarungen]
            else:
                paare_liste = [{"heim": p["heim"], "gast": p["gast"]} for p in paarungen]
            await lobby.broadcast({"typ": "pokal_runde_start",
                                    "wettbewerb": wettbewerb, "runde": runde, "leg": leg,
                                    "paarungen": paare_liste})

        if leg == "hin":
            aufgaben = [self._cup_match_ausfuehren(
                lobby, p["heim"], p["gast"], wettbewerb, f"{runde} – Hinspiel",
                ist_hinspiel=True, instant=not hat_manager)
                for p in paarungen]
            ergebnisse = await asyncio.gather(*aufgaben)
            for p, (ht, gt, _) in zip(paarungen, ergebnisse):
                p["hin_heim"] = ht
                p["hin_gast"] = gt

        elif leg == "rueck":
            # Rückspiel: Heim/Gast sind vertauscht; VL+Elfmeter wenn Aggregat+Auswärtstore gleich
            aufgaben = [self._cup_match_ausfuehren(
                lobby, p["gast"], p["heim"], wettbewerb, f"{runde} – Rückspiel",
                hinspiel_heim=p["hin_heim"], hinspiel_gast=p["hin_gast"], instant=not hat_manager)
                for p in paarungen]
            ergebnisse = await asyncio.gather(*aufgaben)
            for p, (ht, gt, elf) in zip(paarungen, ergebnisse):
                p["rueck_heim"] = ht   # gast spielt jetzt heim
                p["rueck_gast"] = gt   # heim spielt jetzt gast
                if elf:
                    p["elfmeter_sieger"] = elf
                p["sieger"] = bestimme_sieger_hinrueck(p)

            self._news_pokal_runde(lobby, wettbewerb, runde, paarungen, menschliche_teams)
            naechste_runde_befuellen(bracket, wettbewerb)

        elif leg == "einzel":  # Finale ECL / Pokalsieger – neutraler Platz, VL+Elfmeter bei Unentschieden
            aufgaben = [self._cup_match_ausfuehren(
                lobby, p["heim"], p["gast"], wettbewerb, f"{runde}", split_einnahmen=True,
                instant=not hat_manager)
                for p in paarungen]
            ergebnisse = await asyncio.gather(*aufgaben)
            for p, (ht, gt, elf) in zip(paarungen, ergebnisse):
                p["heim_tore"] = ht
                p["gast_tore"] = gt
                if elf:
                    p["elfmeter_sieger"] = elf
                p["sieger"] = bestimme_sieger_einzel(p)

            self._news_pokal_runde(lobby, wettbewerb, runde, paarungen, menschliche_teams)

        if hat_manager:
            lobby.weiter_ts = time.time()
            await lobby.broadcast({"typ": "pokal_runde_ende",
                                    "wettbewerb": wettbewerb, "runde": runde, "leg": leg,
                                    "pokale": self._compute_pokal_uebersicht(lobby.game_state),
                                    "ergebnisse": [
                                        {"heim": p["heim"], "gast": p["gast"],
                                         "sieger": p.get("sieger")} for p in paarungen
                                    ]})
        return hat_manager

    async def _handle_transfer_inland(self, ws, _data: dict):
        info = self.verbindungen.get(ws, {})
        lobby = self.lobbys.get(info.get("lobby_code"))
        if not lobby or not lobby.transfermarkt:
            return
        mid = info["manager_id"]
        team_name = lobby.spieler[mid]["team"]
        angebote = lobby.transfermarkt.inland_besuchen(team_name)
        if angebote is None:
            await self._ws_send(ws, json.dumps({"typ": "fehler", "nachricht": "Keine Besuche mehr übrig"}))
        else:
            # Spieler-Objekte in der Session speichern (fuer spaeteres Kaufen)
            if mid not in lobby.transfer_session:
                lobby.transfer_session[mid] = {}
            for s, p in angebote:
                lobby.transfer_session[mid][s.name] = (s, p)
            await self._ws_send(ws, json.dumps({
                "typ": "inland_angebote",
                "angebote": [{"name": s.name, "position": s.position, "staerke": s.staerke_label, "preis": p} for s, p in angebote]
            }))

    async def _handle_transfer_ausland(self, ws, _data: dict):
        info = self.verbindungen.get(ws, {})
        lobby = self.lobbys.get(info.get("lobby_code"))
        if not lobby or not lobby.transfermarkt:
            return
        mid = info["manager_id"]
        team_name = lobby.spieler[mid]["team"]
        angebot, fehler = lobby.transfermarkt.ausland_besuchen(team_name)
        if fehler:
            await self._ws_send(ws, json.dumps({"typ": "fehler", "nachricht": fehler}))
        else:
            s, p = angebot
            if mid not in lobby.transfer_session:
                lobby.transfer_session[mid] = {}
            lobby.transfer_session[mid][s.name] = (s, p)
            await self._ws_send(ws, json.dumps({
                "typ": "ausland_angebot",
                "spieler": {"name": s.name, "position": s.position, "staerke": s.staerke_label, "preis": p}
            }))

    async def _handle_kaufen(self, ws, data: dict):
        info = self.verbindungen.get(ws, {})
        lobby = self.lobbys.get(info.get("lobby_code"))
        if not lobby:
            return
        mid = info["manager_id"]
        team_name = lobby.spieler[mid]["team"]
        spieler_name = data.get("spieler")

        # Spieler-Objekt aus der Session holen (Preis kommt aus der Session, nicht vom Client)
        session = lobby.transfer_session.get(mid, {})
        eintrag = session.get(spieler_name)
        if not eintrag:
            await self._ws_send(ws, json.dumps({"typ": "fehler", "nachricht": "Angebot nicht mehr gültig"}))
            return

        spieler_obj, orig_preis = eintrag

        # Prüfen ob Spieler bereits in irgendeinem Kader (namensbasiert – fängt auch Ausland/Inland-Überschneidungen)
        for t in lobby.game_state.teams.values():
            if any(s.name == spieler_name for s in t.kader):
                nachricht = "Spieler bereits im Kader" if t.name == team_name else "Spieler bereits verkauft"
                await self._ws_send(ws, json.dumps({"typ": "fehler", "nachricht": nachricht}))
                return

        erfolg, nachricht = lobby.transfermarkt.kaufen(team_name, spieler_obj, orig_preis)
        if not erfolg:
            await self._ws_send(ws, json.dumps({"typ": "fehler", "nachricht": nachricht}))
            return

        # Aus allen anderen Sessions entfernen (Shared-Logik)
        for other_mid, other_session in lobby.transfer_session.items():
            if other_mid != mid and spieler_name in other_session:
                del other_session[spieler_name]
                # Anderen Manager informieren dass Angebot weg ist
                other_ws = lobby.spieler.get(other_mid, {}).get("ws")
                if other_ws:
                    try:
                        await other_ws.send(json.dumps({
                            "typ": "angebot_vergriffen",
                            "spieler": spieler_name
                        }))
                    except:
                        pass

        # Aus eigener Session entfernen
        del session[spieler_name]

        preis_str = f"{orig_preis/1_000_000:.2f} Mio. DM" if orig_preis >= 1_000_000 else f"{orig_preis:,} DM"
        ist_ausland = spieler_obj.nationalitaet == "A"
        if ist_ausland or spieler_obj.staerke_wert >= 82 or orig_preis >= 1_000_000:
            msg = random.choice(_KAUF_TEXTE).format(
                team=f"«{team_name}»", spieler=spieler_obj.name,
                pos=spieler_obj.position, preis=preis_str)
            await lobby.broadcast({"typ": "news_ticker", "items": [msg]})

        team = lobby.game_state.teams[team_name]
        await self._ws_send(ws, json.dumps({
            "typ": "kauf_bestaetigt",
            "nachricht": nachricht,
            "kontostand": team.kontostand,
            "spieler": {
                "name": spieler_obj.name,
                "position": spieler_obj.position,
                "staerke": spieler_obj.staerke_label,
                "nationalitaet": spieler_obj.nationalitaet,
                "verletzt_wochen": spieler_obj.verletzt_wochen,
                "gesperrt_wochen": spieler_obj.gesperrt_wochen,
                "gelbe_karten": spieler_obj.gelbe_karten,
                "gelbe_karten_zyklus": spieler_obj.gelbe_karten_zyklus,
                "gehalt": spieler_obj.gehalt,
                "marktwert": spieler_obj.marktwert,
            }
        }))

    async def _handle_verkaufen(self, ws, data: dict):
        info = self.verbindungen.get(ws, {})
        lobby = self.lobbys.get(info.get("lobby_code"))
        if not lobby:
            return
        team_name = lobby.spieler[info["manager_id"]]["team"]
        spieler_name = data.get("spieler")
        modus = data.get("modus", "notverkauf")

        if modus == "notverkauf":
            erfolg, nachricht = lobby.transfermarkt.notverkauf(team_name, spieler_name)
            extra = {}
        else:
            erfolg, nachricht = lobby.transfermarkt.transfermarkt_listen(team_name, spieler_name)
            if erfolg:
                lobby.news_items.append(random.choice(_LIST_TEXTE).format(
                    team=team_name, spieler=spieler_name))
                listed_preis = next((p for s, p, vk, w in lobby.transfermarkt.gelistete_spieler
                                     if s.name == spieler_name and vk == team_name), None)
                extra = {"modus": "listen", "spieler": spieler_name, "preis": listed_preis}
            else:
                extra = {}

        await self._ws_send(ws, json.dumps({"typ": "verkauf_bestaetigt" if erfolg else "fehler",
                                            "nachricht": nachricht, **extra}))

    async def _handle_delist(self, ws, data: dict):
        info = self.verbindungen.get(ws, {})
        lobby = self.lobbys.get(info.get("lobby_code"))
        if not lobby:
            return
        team_name = lobby.spieler[info["manager_id"]]["team"]
        spieler_name = data.get("spieler")
        erfolg, nachricht = lobby.transfermarkt.transfermarkt_delist(team_name, spieler_name)
        if erfolg:
            _gl = _gelistet_namen(lobby)
            team = lobby.game_state.teams.get(team_name)
            await self._ws_send(ws, json.dumps({
                "typ": "delist_ok",
                "spieler": spieler_name,
                "nachricht": nachricht,
                "kader": [_spieler_dict(s, s.name in _gl) for s in team.kader],
                "gelistete_spieler_eigene": lobby.transfermarkt.get_gelistete_fuer_team(team_name),
            }, ensure_ascii=False))
        else:
            await self._ws_send(ws, json.dumps({"typ": "fehler", "nachricht": nachricht}, ensure_ascii=False))
