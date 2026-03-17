"""
Game State Persistence
Handles saving and loading game states as JSON
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
import uuid

log = logging.getLogger(__name__)

GAME_SAVE_DIR = Path(__file__).parent.parent / "data" / "game_saves"
MAX_SAVES_PER_PLAYER = 5


def ensure_game_save_dir():
    """Create game saves directory if it doesn't exist"""
    GAME_SAVE_DIR.mkdir(parents=True, exist_ok=True)


def serialize_team(team):
    """Convert Team object to JSON-serializable dict"""
    return {
        "name": team.name,
        "liga": team.liga,
        "kontostand": team.kontostand,
        "ist_menschlich": team.ist_menschlich,
        "manager_id": team.manager_id,
        "kader": [serialize_spieler(s) for s in team.kader],
        "startelf": team.startelf,
        "spiele": team.spiele,
        "punkte": team.punkte,
        "tore": team.tore,
        "gegentore": team.gegentore,
        "siege": team.siege,
        "niederlagen": team.niederlagen,
        "unentschieden": team.unentschieden,
        "kontostand_verlauf": team.kontostand_verlauf,
        "saisons_negativ": team.saisons_negativ,
    }


def serialize_spieler(spieler):
    """Convert Spieler object to JSON-serializable dict"""
    return {
        "name": spieler.name,
        "position": spieler.position,
        "staerke_label": spieler.staerke_label,
        "staerke_wert": spieler.staerke_wert,
        "nationalitaet": spieler.nationalitaet,
        "verletzt_wochen": spieler.verletzt_wochen,
        "gesperrt_wochen": spieler.gesperrt_wochen,
        "gelbe_karten": spieler.gelbe_karten,
        "gelbe_karten_zyklus": spieler.gelbe_karten_zyklus,
        "gehalt": spieler.gehalt,
        "marktwert": spieler.marktwert,
        "tore_liga": spieler.tore_liga,
        "tore_pokal": spieler.tore_pokal,
        "rote_karten": spieler.rote_karten,
        "diagnose": spieler.diagnose,
    }


def deserialize_team(data):
    """Reconstruct Team from serialized dict"""
    from engine.game_state import Team

    team = Team(
        name=data["name"],
        liga=data["liga"],
        kontostand=data["kontostand"],
        ist_menschlich=data["ist_menschlich"],
        manager_id=data["manager_id"]
    )
    team.kader = [deserialize_spieler(s) for s in data["kader"]]
    team.startelf = data["startelf"]
    team.spiele = data["spiele"]
    team.punkte = data["punkte"]
    team.tore = data["tore"]
    team.gegentore = data["gegentore"]
    team.siege = data["siege"]
    team.niederlagen = data["niederlagen"]
    team.unentschieden = data["unentschieden"]
    team.kontostand_verlauf = data.get("kontostand_verlauf", [])
    team.saisons_negativ = data.get("saisons_negativ", 0)
    return team


def deserialize_spieler(data):
    """Reconstruct Spieler from serialized dict"""
    from engine.game_state import Spieler

    spieler = Spieler(
        name=data["name"],
        position=data["position"],
        staerke_label=data["staerke_label"],
        staerke_wert=data["staerke_wert"],
        nationalitaet=data["nationalitaet"]
    )
    spieler.verletzt_wochen = data["verletzt_wochen"]
    spieler.gesperrt_wochen = data["gesperrt_wochen"]
    spieler.gelbe_karten = data["gelbe_karten"]
    spieler.gelbe_karten_zyklus = data.get("gelbe_karten_zyklus", 0)
    spieler.gehalt = data["gehalt"]
    spieler.marktwert = data["marktwert"]
    spieler.tore_liga = data.get("tore_liga", 0)
    spieler.tore_pokal = data.get("tore_pokal", 0)
    spieler.rote_karten = data.get("rote_karten", 0)
    spieler.diagnose = data.get("diagnose", "")
    # verfuegbar wird nicht gesetzt – es ist eine computed @property
    return spieler


class GameSaver:
    @staticmethod
    def generate_game_key(google_id):
        """Generate unique game key"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_id = str(uuid.uuid4())[:8].upper()
        return f"{google_id}_{timestamp}_{random_id}"

    @staticmethod
    def get_game_save_path(game_key):
        """Get file path for a game save"""
        return GAME_SAVE_DIR / f"{game_key}.json"

    @staticmethod
    def list_saves_for_google_id(google_id):
        """
        Return all save dicts for a given google_id, sorted oldest first.
        Includes all statuses (active, paused) – not completed.
        """
        ensure_game_save_dir()
        saves = []
        for f in GAME_SAVE_DIR.glob("*.json"):
            try:
                with open(f, 'r', encoding='utf-8') as fh:
                    gs = json.load(fh)
                if gs.get("status") in ("active", "paused"):
                    if any(m.get("google_id") == google_id for m in gs.get("managers", {}).values()):
                        saves.append(gs)
            except Exception:
                pass
        saves.sort(key=lambda s: s.get("created_at", ""))
        return saves

    @staticmethod
    def enforce_save_limit(google_id):
        """
        Enforce max MAX_SAVES_PER_PLAYER saves.
        Deletes oldest non-pinned saves until under the limit.
        """
        saves = GameSaver.list_saves_for_google_id(google_id)
        while len(saves) >= MAX_SAVES_PER_PLAYER:
            # Find oldest non-pinned save
            to_delete = next((s for s in saves if not s.get("pinned", False)), None)
            if not to_delete:
                break  # All remaining are pinned – can't delete
            path = GameSaver.get_game_save_path(to_delete["game_key"])
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
            saves.remove(to_delete)

    @staticmethod
    def create_game_save(lobby, game_state, managers_info):
        """
        Create initial game save.
        Args:
            lobby: Lobby object
            game_state: GameState object
            managers_info: {manager_id: {google_id, email, name, team}}
        Returns: game_key
        """
        ensure_game_save_dir()

        # Enforce limit for all human managers
        for minfo in managers_info.values():
            gid = minfo.get("google_id")
            if gid:
                GameSaver.enforce_save_limit(gid)

        game_key = GameSaver.generate_game_key(
            managers_info[list(managers_info.keys())[0]].get("google_id", "unknown")
        )

        game_save = {
            "game_key": game_key,
            "lobby_code": lobby.code,
            "created_at": datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
            "last_saved": datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
            "status": "active",
            "pinned": False,
            "season": game_state.saison,
            "matchday": game_state.spieltag,
            "managers": managers_info,
            "session_chat": [],
            "game_state": {
                "saison": game_state.saison,
                "spieltag": game_state.spieltag,
                "phase": game_state.phase,
                "teams": {name: serialize_team(team) for name, team in game_state.teams.items()},
                "europa_teams": {name: serialize_team(team) for name, team in game_state.europa_teams.items()},
                "dfb_pokal_bracket": game_state.dfb_pokal_bracket,
                "europa_brackets": game_state.europa_brackets,
            }
        }

        try:
            game_save_path = GameSaver.get_game_save_path(game_key)
            with open(game_save_path, 'w', encoding='utf-8') as f:
                json.dump(game_save, f, indent=2, ensure_ascii=False)
            return game_key
        except Exception as e:
            log.error(f"Error creating game save {game_key}: {e}")
            return None

    @staticmethod
    def save_game_state(game_key, game_state, session_chat=None, transfermarkt=None):
        """
        Save current game state (called after each matchday).
        """
        ensure_game_save_dir()
        game_save_path = GameSaver.get_game_save_path(game_key)

        if not game_save_path.exists():
            log.warning(f"Game save {game_key} does not exist")
            return False

        try:
            with open(game_save_path, 'r', encoding='utf-8') as f:
                game_save = json.load(f)

            game_save["last_saved"] = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
            game_save["season"] = game_state.saison
            game_save["matchday"] = game_state.spieltag
            game_save["game_state"]["saison"] = game_state.saison
            game_save["game_state"]["spieltag"] = game_state.spieltag
            game_save["game_state"]["phase"] = game_state.phase
            game_save["game_state"]["teams"] = {
                name: serialize_team(team) for name, team in game_state.teams.items()
            }
            game_save["game_state"]["europa_teams"] = {
                name: serialize_team(team) for name, team in game_state.europa_teams.items()
            }
            game_save["game_state"]["dfb_pokal_bracket"] = game_state.dfb_pokal_bracket
            game_save["game_state"]["europa_brackets"] = game_state.europa_brackets
            game_save["game_state"]["zusatz_spieler"] = [serialize_spieler(s) for s in game_state.zusatz_spieler]
            game_save["game_state"]["finanzen_verlauf"] = game_state.finanzen_verlauf
            if transfermarkt is not None:
                game_save["game_state"]["gelistete_spieler"] = [
                    {"spieler": serialize_spieler(s), "preis": p, "verkäufer": vk, "woche": w}
                    for s, p, vk, w in transfermarkt.gelistete_spieler
                ]
            if session_chat is not None:
                game_save["session_chat"] = session_chat

            with open(game_save_path, 'w', encoding='utf-8') as f:
                json.dump(game_save, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            log.error(f"Error saving game state {game_key}: {e}")
            return False

    @staticmethod
    def load_game_save(game_key):
        """
        Load game from save file.
        Returns: (game_save_dict, GameState) or (None, None) if not found
        """
        ensure_game_save_dir()
        game_save_path = GameSaver.get_game_save_path(game_key)

        if not game_save_path.exists():
            return None, None

        try:
            with open(game_save_path, 'r', encoding='utf-8') as f:
                game_save = json.load(f)

            from engine.game_state import GameState

            game_state = GameState(lobby_code=game_save["lobby_code"])
            game_state.saison = game_save["game_state"]["saison"]
            game_state.spieltag = game_save["game_state"]["spieltag"]
            game_state.phase = game_save["game_state"]["phase"]

            for team_name, team_data in game_save["game_state"]["teams"].items():
                game_state.teams[team_name] = deserialize_team(team_data)

            for team_name, team_data in game_save["game_state"].get("europa_teams", {}).items():
                game_state.europa_teams[team_name] = deserialize_team(team_data)

            game_state.dfb_pokal_bracket = game_save["game_state"].get("dfb_pokal_bracket", {})
            game_state.europa_brackets   = game_save["game_state"].get("europa_brackets", {})
            game_state.zusatz_spieler = [
                deserialize_spieler(s) for s in game_save["game_state"].get("zusatz_spieler", [])
            ]
            # gelistete_spieler werden als rohe Liste gespeichert und nach Transfermarkt-Init übergeben
            game_state._gelistete_spieler_raw = game_save["game_state"].get("gelistete_spieler", [])
            game_state.finanzen_verlauf = game_save["game_state"].get("finanzen_verlauf", {})

            return game_save, game_state
        except Exception as e:
            log.error(f"Error loading game save {game_key}: {e}")
            return None, None

    @staticmethod
    def delete_game_save(game_key, google_id):
        """
        Delete a game save. Only allowed if google_id is a manager of that game.
        Returns: True on success, False otherwise.
        """
        ensure_game_save_dir()
        game_save_path = GameSaver.get_game_save_path(game_key)

        if not game_save_path.exists():
            return False

        try:
            with open(game_save_path, 'r', encoding='utf-8') as f:
                game_save = json.load(f)

            # Authorization check
            if not any(m.get("google_id") == google_id for m in game_save.get("managers", {}).values()):
                return False

            game_save_path.unlink()
            return True
        except Exception as e:
            log.error(f"Error deleting game save {game_key}: {e}")
            return False

    @staticmethod
    def pin_game_save(game_key, google_id, pinned: bool):
        """
        Pin or unpin a game save.
        Returns: True on success, False otherwise.
        """
        ensure_game_save_dir()
        game_save_path = GameSaver.get_game_save_path(game_key)

        if not game_save_path.exists():
            return False

        try:
            with open(game_save_path, 'r', encoding='utf-8') as f:
                game_save = json.load(f)

            if not any(m.get("google_id") == google_id for m in game_save.get("managers", {}).values()):
                return False

            game_save["pinned"] = pinned

            with open(game_save_path, 'w', encoding='utf-8') as f:
                json.dump(game_save, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            log.error(f"Error pinning game save {game_key}: {e}")
            return False

    @staticmethod
    def list_ongoing_games(google_id):
        """Get all ongoing game keys for a manager."""
        return [s["game_key"] for s in GameSaver.list_saves_for_google_id(google_id)]

    @staticmethod
    def mark_game_completed(game_key, final_standings):
        """Mark game as completed and store final standings."""
        ensure_game_save_dir()
        game_save_path = GameSaver.get_game_save_path(game_key)

        if not game_save_path.exists():
            return False

        try:
            with open(game_save_path, 'r', encoding='utf-8') as f:
                game_save = json.load(f)

            game_save["status"] = "completed"
            game_save["final_standings"] = final_standings

            with open(game_save_path, 'w', encoding='utf-8') as f:
                json.dump(game_save, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            log.error(f"Error marking game completed {game_key}: {e}")
            return False

    @staticmethod
    def get_game_save(game_key):
        """Load game save metadata"""
        ensure_game_save_dir()
        game_save_path = GameSaver.get_game_save_path(game_key)

        if not game_save_path.exists():
            return None

        try:
            with open(game_save_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Error loading game save metadata {game_key}: {e}")
            return None


# ── Multiplayer Save Manager ───────────────────────────────────────────────────

MP_SAVE_DIR = Path(__file__).parent.parent / "data" / "mp_saves"
MP_SAVE_SLOTS = 5


def _mp_save_path(creator_google_id: str) -> Path:
    """One JSON file per creator (using a safe filename derived from their ID)."""
    safe = creator_google_id.replace("/", "_").replace("\\", "_")[:80]
    return MP_SAVE_DIR / f"{safe}.json"


def _mp_load_file(creator_google_id: str) -> dict:
    path = _mp_save_path(creator_google_id)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"creator_google_id": creator_google_id, "slots": {}}


def _mp_write_file(creator_google_id: str, data: dict):
    MP_SAVE_DIR.mkdir(parents=True, exist_ok=True)
    path = _mp_save_path(creator_google_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class MPSaveManager:
    """
    Manages up to 5 named multiplayer save slots per creator.
    Each slot stores: saved_at, saison, spieltag, managers list, full game_state snapshot.
    Slots are keyed 1–5 (as strings in JSON).
    """

    @staticmethod
    def list_slots(creator_google_id: str) -> dict:
        """
        Returns a dict {1: slot_or_none, ..., 5: slot_or_none}.
        slot_or_none is the full slot dict or None if empty.
        """
        data = _mp_load_file(creator_google_id)
        slots = data.get("slots", {})
        return {i: slots.get(str(i)) for i in range(1, MP_SAVE_SLOTS + 1)}

    @staticmethod
    def _slot_data(game_key: str, slot: int, managers: list, game_state) -> dict:
        return {
            "slot": slot,
            "game_key": game_key,
            "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "saison": game_state.saison,
            "spieltag": game_state.spieltag,
            "managers": managers,
            "game_state": {
                "saison": game_state.saison,
                "spieltag": game_state.spieltag,
                "phase": game_state.phase,
                "teams": {n: serialize_team(t) for n, t in game_state.teams.items()},
                "europa_teams": {n: serialize_team(t) for n, t in game_state.europa_teams.items()},
                "dfb_pokal_bracket": game_state.dfb_pokal_bracket,
                "europa_brackets": game_state.europa_brackets,
            },
        }

    @staticmethod
    def create_for_game(creator_google_id: str, game_key: str, managers: list, game_state) -> bool:
        """
        Beim Spielstart: legt neuen MP-Speicherstand an.
        Verwendet ersten freien Slot; falls alle voll, wird der älteste überschrieben.
        """
        data = _mp_load_file(creator_google_id)
        slots = data.setdefault("slots", {})
        # Ersten freien Slot finden
        slot = next((i for i in range(1, MP_SAVE_SLOTS + 1) if str(i) not in slots), None)
        if slot is None:
            # Ältesten überschreiben
            oldest_key = min(slots, key=lambda k: slots[k].get("saved_at", ""))
            slot = int(oldest_key)
        slots[str(slot)] = MPSaveManager._slot_data(game_key, slot, managers, game_state)
        try:
            _mp_write_file(creator_google_id, data)
            return True
        except Exception as e:
            log.error(f"MPSaveManager.create_for_game error: {e}")
            return False

    @staticmethod
    def update_slot(creator_google_id: str, slot: int, game_key: str, managers: list, game_state) -> bool:
        """Überschreibt einen Slot direkt (nach Slot-Nummer), z.B. beim Neustart eines geladenen MP-Spiels."""
        if slot < 1 or slot > MP_SAVE_SLOTS:
            return False
        data = _mp_load_file(creator_google_id)
        slots = data.setdefault("slots", {})
        slots[str(slot)] = MPSaveManager._slot_data(game_key, slot, managers, game_state)
        try:
            _mp_write_file(creator_google_id, data)
            return True
        except Exception as e:
            log.error(f"MPSaveManager.update_slot error: {e}")
            return False

    @staticmethod
    def update_by_game_key(creator_google_id: str, game_key: str, game_state) -> bool:
        """
        Autosave: findet den Slot anhand des game_key und aktualisiert Spielstand + Metadaten.
        """
        data = _mp_load_file(creator_google_id)
        slots = data.get("slots", {})
        slot_key = next((k for k, v in slots.items() if v.get("game_key") == game_key), None)
        if slot_key is None:
            return False  # Kein passender Slot — nichts tun
        existing = slots[slot_key]
        existing["saved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        existing["saison"] = game_state.saison
        existing["spieltag"] = game_state.spieltag
        existing["game_state"] = {
            "saison": game_state.saison,
            "spieltag": game_state.spieltag,
            "phase": game_state.phase,
            "teams": {n: serialize_team(t) for n, t in game_state.teams.items()},
            "europa_teams": {n: serialize_team(t) for n, t in game_state.europa_teams.items()},
            "dfb_pokal_bracket": game_state.dfb_pokal_bracket,
            "europa_brackets": game_state.europa_brackets,
        }
        try:
            _mp_write_file(creator_google_id, data)
            return True
        except Exception as e:
            log.error(f"MPSaveManager.update_by_game_key error: {e}")
            return False

    @staticmethod
    def load_slot(creator_google_id: str, slot: int) -> dict | None:
        """Returns the slot dict or None if empty/invalid."""
        if slot < 1 or slot > MP_SAVE_SLOTS:
            return None
        data = _mp_load_file(creator_google_id)
        return data.get("slots", {}).get(str(slot))

    @staticmethod
    def delete_slot(creator_google_id: str, slot: int) -> bool:
        """Clears a slot. Returns True on success."""
        if slot < 1 or slot > MP_SAVE_SLOTS:
            return False
        data = _mp_load_file(creator_google_id)
        if str(slot) in data.get("slots", {}):
            data["slots"].pop(str(slot))
            try:
                _mp_write_file(creator_google_id, data)
            except Exception:
                return False
        return True

    @staticmethod
    def slot_summary(slot_data: dict) -> dict | None:
        """Returns a compact summary dict safe to send to the frontend."""
        if not slot_data:
            return None
        return {
            "slot": slot_data["slot"],
            "saved_at": slot_data["saved_at"],
            "saison": slot_data["saison"],
            "spieltag": slot_data["spieltag"],
            "managers": slot_data["managers"],
        }
