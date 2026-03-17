"""
Transfermarkt - Inland und Ausland
"""

import random
from engine.game_state import Spieler, GameState, lade_spieler_csv, berechne_marktwert
from engine.settings import getint, getfloat

_KADER_MAX     = getint("transfer", "kader_max")
_KAUF_MIN      = getfloat("transfer", "kauf_faktor_min")
_KAUF_MAX      = getfloat("transfer", "kauf_faktor_max")
_NV_MIN        = getfloat("transfer", "notverkauf_min")
_NV_MAX        = getfloat("transfer", "notverkauf_max")
_NV_PEAK       = getfloat("transfer", "notverkauf_peak")
_ZV_MIN        = getfloat("transfer", "zwangsverkauf_min")
_ZV_MAX        = getfloat("transfer", "zwangsverkauf_max")
_ZV_PEAK       = getfloat("transfer", "zwangsverkauf_peak")
_AUSLAND_WK_CHANCE = getfloat("transfer", "ausland_wk_chance")


class Transfermarkt:
    def __init__(self, game_state: GameState):
        self.gs = game_state
        self.inland_angebote: dict = {}    # team_name -> [Spieler, Spieler, Spieler]
        self.ausland_angebote: dict = {}   # team_name -> Spieler
        self.inland_besuche: dict = {}     # team_name -> anzahl besuche diese woche
        self.ausland_besucht: set = set()  # team_names die diese woche besucht haben
        self.gelistete_spieler: list = []  # [(Spieler, Preis, Verkäufer-Team, Woche)]
        self._spieler_cache: list = []     # spieler.csv einmal pro Woche gecacht
        self.letzte_zwangsverkäufe: dict = {}  # team_name -> [{name, erloes}]

    def neue_woche(self):
        """Generiert neue Angebote für die Woche"""
        self._spieler_cache = lade_spieler_csv() + self.gs.zusatz_spieler  # inkl. Nachwuchs
        self.inland_besuche = {}
        self.ausland_besucht = set()
        self._aktualisiere_marktwerte()
        self._verarbeite_gelistete_spieler()

    def _aktualisiere_marktwerte(self):
        """Marktwert aller Spieler aus aktuellem staerke_wert neu berechnen (±8% Variation)."""
        alle = (
            [sp for team in self.gs.teams.values() for sp in team.kader]
            + self.gs.zusatz_spieler
            + [sp for sp, _, _, _ in self.gelistete_spieler]
        )
        for sp in alle:
            sp.marktwert = int(berechne_marktwert(sp.staerke_wert) * random.uniform(0.92, 1.08))
        # Angebote werden erst nach cpu_woche() generiert (siehe neue_woche_angebote)

    def neue_woche_angebote(self):
        """Angebote generieren – muss NACH cpu_woche() aufgerufen werden,
        damit CPU-Käufe dieser Woche aus dem Pool ausgeschlossen sind."""
        self._generiere_inland_angebote()
        self._generiere_ausland_angebote()

    def _generiere_inland_angebote(self):
        """3 Angebote pro Team, 1-2 davon shared. Gelistete Spieler erscheinen als Shared-Slot."""
        menschliche_teams = [n for n, t in self.gs.teams.items() if t.ist_menschlich]

        # Generiere Spieler-Pool für Inlandsmarkt (max Sehr stark, kein Weltklasse)
        pool = self._generiere_spieler_pool(auslaender=False, max_staerke=84)

        for team_name in menschliche_teams:
            angebote = random.sample(pool, min(3, len(pool)))
            angebote_mit_preis = [(s, int(s.marktwert * random.uniform(_KAUF_MIN, _KAUF_MAX))) for s in angebote]
            self.inland_angebote[team_name] = angebote_mit_preis

        # Gelistete Spieler (ab nächster Woche verfügbar) als Shared-Slot einbauen
        # Nur Spieler die diese Woche neu gelistet wurden (woche == 0, noch nicht verarbeitet)
        # Zeige sie allen anderen Managern außer dem Verkäufer
        gelistete_verfuegbar = [
            (s, p, vk) for s, p, vk, w in self.gelistete_spieler if w == 0
        ]
        if gelistete_verfuegbar and len(menschliche_teams) > 1:
            for s, p, verkäufer in gelistete_verfuegbar:
                empfänger = [t for t in menschliche_teams if t != verkäufer]
                for team_name in empfänger:
                    if team_name in self.inland_angebote and len(self.inland_angebote[team_name]) > 0:
                        # Ersetze letzten Slot mit gelistetem Spieler (gleicher Preis wie gelistet)
                        angebote = self.inland_angebote[team_name]
                        angebote[-1] = (s, p)

        # Shared: 1-2 Angebote zufällig mit anderen Managern teilen
        if len(menschliche_teams) > 1:
            for _ in range(min(2, len(menschliche_teams))):
                if random.random() < 0.5:
                    # Wähle zufällig zwei Manager und teile ein Angebot
                    t1, t2 = random.sample(menschliche_teams, 2)
                    if t1 in self.inland_angebote and t2 in self.inland_angebote:
                        shared = self.inland_angebote[t1][0]
                        self.inland_angebote[t2][0] = shared  # Gleiches Objekt = shared

    def _generiere_ausland_angebote(self):
        """1 Angebot pro Manager, nur Sehr stark und Weltklasse (Weltklasse mit ausland_wk_chance-Wahrscheinlichkeit)"""
        menschliche_teams = [n for n, t in self.gs.teams.items() if t.ist_menschlich]
        if random.random() < _AUSLAND_WK_CHANCE:
            pool = self._generiere_spieler_pool(auslaender=True, min_staerke=85)
            if not pool:
                pool = self._generiere_spieler_pool(auslaender=True, min_staerke=76)
        else:
            pool = self._generiere_spieler_pool(auslaender=True, min_staerke=76, max_staerke=84)
            if not pool:
                pool = self._generiere_spieler_pool(auslaender=True, min_staerke=76)

        shared_chance = random.random() < 0.3  # 30% Chance dass mehrere denselben sehen

        if shared_chance and len(menschliche_teams) > 1:
            shared_spieler = random.choice(pool)
            preis = int(shared_spieler.marktwert * random.uniform(_KAUF_MIN, _KAUF_MAX))
            for team_name in menschliche_teams:
                self.ausland_angebote[team_name] = (shared_spieler, preis)
        else:
            for team_name in menschliche_teams:
                spieler = random.choice(pool)
                preis = int(spieler.marktwert * random.uniform(_KAUF_MIN, _KAUF_MAX))
                self.ausland_angebote[team_name] = (spieler, preis)

    def _generiere_spieler_pool(self, auslaender: bool, min_staerke: int = 1, max_staerke: int = 100) -> list:
        """Generiert einen Pool von verfügbaren Spielern (ohne bereits vergebene)"""
        bereits_vergeben = {s.name for t in self.gs.teams.values() for s in t.kader}
        alle = self._spieler_cache
        gefiltert = [
            s for s in alle
            if (s.nationalitaet == "A") == auslaender
            and min_staerke <= s.staerke_wert <= max_staerke
            and s.name not in bereits_vergeben
        ]
        return gefiltert if gefiltert else [
            s for s in alle
            if (s.nationalitaet == "A") == auslaender
            and s.name not in bereits_vergeben
        ]

    def _verarbeite_gelistete_spieler(self):
        """Ladenhüter-Regel: Zwangsverkauf zum Marktwert (deutlich besser als Notverkauf)"""
        self.letzte_zwangsverkäufe = {}
        neue_liste = []
        for spieler, preis, verkäufer, woche in self.gelistete_spieler:
            if woche >= 1:
                erlös = int(spieler.marktwert * random.triangular(_ZV_MIN, _ZV_MAX, _ZV_PEAK))
                team = self.gs.teams.get(verkäufer)
                if team:
                    team.kontostand += erlös
                self.letzte_zwangsverkäufe.setdefault(verkäufer, []).append(
                    {"name": spieler.name, "erloes": erlös})
            else:
                neue_liste.append((spieler, preis, verkäufer, woche + 1))
        self.gelistete_spieler = neue_liste

    def get_gelistete_fuer_team(self, team_name: str) -> list:
        """Gibt gelistete Spieler dieses Teams zurück: [{name, preis, woche}]"""
        return [
            {"name": s.name, "preis": p, "woche": w}
            for s, p, vk, w in self.gelistete_spieler
            if vk == team_name
        ]

    def inland_besuchen(self, team_name: str) -> list:
        """Gibt Inland-Angebote zurück – filtert live bereits vergebene Spieler heraus."""
        bereits_vergeben = {s.name for t in self.gs.teams.values() for s in t.kader}
        return [(s, p) for s, p in self.inland_angebote.get(team_name, [])
                if s.name not in bereits_vergeben]

    def ausland_besuchen(self, team_name: str):
        """Gibt Ausland-Angebot zurück, max 1 Besuch pro Woche"""
        team = self.gs.teams.get(team_name)
        if not team:
            return None, "Team nicht gefunden"

        if team_name in self.ausland_besucht:
            return None, "Bereits besucht diese Woche"

        if team.kontostand <= 0:
            return None, "Kontostand negativ"

        auslaender_im_kader = sum(1 for s in team.kader if s.ist_auslaender)
        if auslaender_im_kader >= 3:
            return None, "Maximal 3 Internationale im Kader"

        if len(team.kader) >= _KADER_MAX:
            return None, "Kader ist voll"

        self.ausland_besucht.add(team_name)
        return self.ausland_angebote.get(team_name), None

    def kaufen(self, team_name: str, spieler: Spieler, preis: int) -> tuple:
        """Kauft einen Spieler. Gibt (erfolg, nachricht) zurück"""
        team = self.gs.teams.get(team_name)
        if not team:
            return False, "Team nicht gefunden"

        # Inlandsmarkt: kaufen nur wenn Kontostand noch >= -1 Mio (danach gesperrt)
        # Auslandsmarkt: kein Kontostandslimit (Aufdecken selbst ist das Limit)
        if spieler.nationalitaet == "D" and team.kontostand < -1_000_000:
            return False, "Kontostand unter -1 Mio. – kein Kauf möglich"

        if len(team.kader) >= _KADER_MAX:
            return False, "Kader ist voll"

        team.kontostand -= preis
        spieler.tore_liga = 0
        spieler.tore_pokal = 0
        team.kader.append(spieler)
        return True, f"{spieler.name} für {preis:,} DM gekauft"

    def notverkauf(self, team_name: str, spieler_name: str) -> tuple:
        """Sofortiger Verkauf für 50-90% des Marktwertes (Glockenkurve um 65%)"""
        team = self.gs.teams.get(team_name)
        if not team:
            return False, "Team nicht gefunden"

        spieler = next((s for s in team.kader if s.name == spieler_name), None)
        if not spieler:
            return False, "Spieler nicht im Kader"

        if spieler.verletzt_wochen > 0:
            return False, f"{spieler.name} ist verletzt und kann nicht verkauft werden"
        if spieler.gesperrt_wochen > 0:
            return False, f"{spieler.name} ist gesperrt und kann nicht verkauft werden"

        erlös = int(spieler.marktwert * random.triangular(_NV_MIN, _NV_MAX, _NV_PEAK))
        team.kader.remove(spieler)
        team.kontostand += erlös
        return True, f"{spieler.name} für {erlös:,} DM verkauft"

    def transfermarkt_delist(self, team_name: str, spieler_name: str) -> tuple:
        """Nimmt einen gelisteten Spieler zurück — nur möglich wenn noch nicht im Verkauf (woche == 0)."""
        team = self.gs.teams.get(team_name)
        if not team:
            return False, "Team nicht gefunden"

        eintrag = next(
            ((s, p, vk, w) for s, p, vk, w in self.gelistete_spieler
             if s.name == spieler_name and vk == team_name and w == 0),
            None
        )
        if not eintrag:
            return False, "Spieler nicht zurücknehmbar (bereits im Verkauf oder nicht gelistet)"

        spieler, preis, _, _ = eintrag
        self.gelistete_spieler.remove(eintrag)
        team.kader.append(spieler)
        return True, f"{spieler.name} zurückgeholt"

    def transfermarkt_listen(self, team_name: str, spieler_name: str) -> tuple:
        """Listet Spieler auf dem Transfermarkt (nächste Woche verfügbar)"""
        team = self.gs.teams.get(team_name)
        if not team:
            return False, "Team nicht gefunden"

        spieler = next((s for s in team.kader if s.name == spieler_name), None)
        if not spieler:
            return False, "Spieler nicht im Kader"

        if spieler.verletzt_wochen > 0:
            return False, f"{spieler.name} ist verletzt und kann nicht gelistet werden"
        if spieler.gesperrt_wochen > 0:
            return False, f"{spieler.name} ist gesperrt und kann nicht gelistet werden"

        if len(team.kader) <= 11:
            return False, "Kader zu klein – mindestens 11 Spieler müssen im Kader bleiben"

        preis = int(spieler.marktwert * random.uniform(0.8, 1.2))
        team.kader.remove(spieler)
        self.gelistete_spieler.append((spieler, preis, team_name, 0))
        return True, f"{spieler.name} für {preis:,} DM gelistet"
