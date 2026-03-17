"""
Manager Profile Management
Handles JSON-based persistence of manager profiles and statistics
"""

import json
import logging
import os
import random
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

PROFILE_DIR = Path(__file__).parent.parent / "data" / "manager_profiles"


def ensure_profile_dir():
    """Create profile directory if it doesn't exist"""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)


def _atomic_write(path: Path, data: dict):
    """Write JSON atomically: write to .tmp, then rename to avoid empty/corrupt files."""
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


class ProfileManager:
    @staticmethod
    def get_profile_path(google_id):
        """Get file path for a profile"""
        return PROFILE_DIR / f"{google_id}.json"

    @staticmethod
    def get_profile(google_id):
        """
        Load manager profile from JSON.
        Returns: dict or None if not found
        """
        ensure_profile_dir()
        profile_path = ProfileManager.get_profile_path(google_id)

        if not profile_path.exists():
            return None

        try:
            content = profile_path.read_text(encoding='utf-8').strip()
            if not content:
                return None
            return json.loads(content)
        except Exception as e:
            log.error(f"Error loading profile {google_id}: {e}")
            return None

    @staticmethod
    def create_profile(google_id, email, name, picture_url):
        """
        Create a new manager profile.
        Returns: profile dict
        """
        ensure_profile_dir()
        profile_path = ProfileManager.get_profile_path(google_id)

        # Check if already exists
        if profile_path.exists():
            return ProfileManager.get_profile(google_id)

        # Generate unique manager ID
        manager_id = f"MGR_{datetime.now().strftime('%Y%m%d%H%M%S')}_{google_id[:8]}"

        profile = {
            "google_id": google_id,
            "email": email,
            "name": name,           # Google Klarname – wird nicht angezeigt
            "nickname": ProfileManager._random_nick(),  # Zufälliger Startname
            "profile_image": picture_url,
            "manager_id": manager_id,
            "created_at": datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
            "last_login": datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
            "statistics": {
                "total_games": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "total_points": 0,
                "avg_points_per_season": 0,
                "tore": 0,
                "gegentore": 0,
                "bester_kontostand": 0,
                "beste_saison": None,
            },
            "game_history": [],
            "ongoing_games": [],
            "lieblingsverein": None,
            "erfolge": {
                "saisons": 0,
                "meisterschaften": 0,
                "dfb_pokale": 0,
                "ecl_titel": 0,
                "pokalsieger_titel": 0,
                "uefacup_titel": 0,
                "bester_kaderwert": 0,
            }
        }

        try:
            _atomic_write(profile_path, profile)
            return profile
        except Exception as e:
            log.error(f"Error creating profile {google_id}: {e}")
            return None

    @staticmethod
    def _random_nick() -> str:
        try:
            from engine.game_state import _VORNAMEN, _NACHNAMEN
            v = random.choice(_VORNAMEN) if _VORNAMEN else "Manager"
            n = random.choice(_NACHNAMEN) if _NACHNAMEN else "X"
            return f"{v}{n}{random.randint(1000, 9999)}"
        except Exception:
            return f"Manager{random.randint(1000, 9999)}"

    @staticmethod
    def validate_nickname(nickname):
        """
        Validate a nickname.
        Rules: 2-20 chars, letters/digits/spaces/hyphens/underscores/dots
        Returns: (True, None) on success, (False, error_message) on failure
        """
        import re
        if not nickname or not isinstance(nickname, str):
            return False, "Nickname darf nicht leer sein"
        nick = nickname.strip()
        if len(nick) < 2:
            return False, "Mindestens 2 Zeichen"
        if len(nick) > 20:
            return False, "Maximal 20 Zeichen"
        if not re.match(r'^[\w\s\-\.]+$', nick):
            return False, "Nur Buchstaben, Ziffern, Leerzeichen, - und _ erlaubt"
        return True, None

    @staticmethod
    def update_profile(google_id, data):
        """
        Update manager profile.
        Args:
            google_id: Google user ID
            data: dict with fields to update
        Returns: Updated profile dict
        """
        profile = ProfileManager.get_profile(google_id)
        if not profile:
            return None

        # Update allowed fields
        allowed_fields = ["name", "nickname", "profile_image", "last_login", "lieblingsverein", "radio_settings", "theme", "last_seen"]
        for field in allowed_fields:
            if field in data:
                profile[field] = data[field]

        # Always update last_login
        profile["last_login"] = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')

        try:
            profile_path = ProfileManager.get_profile_path(google_id)
            _atomic_write(profile_path, profile)
            return profile
        except Exception as e:
            log.error(f"Error updating profile {google_id}: {e}")
            return None

    @staticmethod
    def add_to_game_history(google_id, game_data):
        """
        Add a completed game to history and update statistics.
        Args:
            google_id: Google user ID
            game_data: {
                "game_key": "...",
                "date": "2026-02-25",
                "team": "FC Bayern",
                "status": "completed|paused",
                "final_position": 1,
                "points": 100
            }
        Returns: Updated profile
        """
        profile = ProfileManager.get_profile(google_id)
        if not profile:
            return None

        # Add to history
        profile["game_history"].append(game_data)

        # Update statistics
        stats = profile["statistics"]
        stats["total_games"] += 1

        if game_data.get("status") == "completed":
            position = game_data.get("final_position", 99)
            points = game_data.get("punkte", game_data.get("points", 0))
            stats["total_points"] += points

            if position == 1:
                stats["wins"] += 1
            elif position == 2:
                stats["draws"] += 1
            else:
                stats["losses"] += 1

            # Tore / Gegentore akkumulieren
            stats["tore"] = stats.get("tore", 0) + game_data.get("tore", 0)
            stats["gegentore"] = stats.get("gegentore", 0) + game_data.get("gegentore", 0)
            # Spiel-Siege/U/N über alle Saisons
            stats["match_siege"] = stats.get("match_siege", 0) + game_data.get("siege", 0)
            stats["match_unentschieden"] = stats.get("match_unentschieden", 0) + game_data.get("unentschieden", 0)
            stats["match_niederlagen"] = stats.get("match_niederlagen", 0) + game_data.get("niederlagen", 0)

            # Bester Kontostand
            konto = game_data.get("kontostand", 0)
            if konto > stats.get("bester_kontostand", 0):
                stats["bester_kontostand"] = konto

            # Beste Saison (niedrigster Platz = besser)
            beste = stats.get("beste_saison")
            if beste is None or position < beste.get("position", 99):
                stats["beste_saison"] = {
                    "position": position,
                    "team": game_data.get("team", ""),
                    "saison": game_data.get("saison", ""),
                    "punkte": points,
                }

            # Calculate average
            if stats["total_games"] > 0:
                stats["avg_points_per_season"] = int(stats["total_points"] / stats["total_games"])

        try:
            profile_path = ProfileManager.get_profile_path(google_id)
            _atomic_write(profile_path, profile)
            return profile
        except Exception as e:
            log.error(f"Error updating game history {google_id}: {e}")
            return None

    @staticmethod
    def add_ongoing_game(google_id, game_key):
        """Add game to ongoing_games list"""
        profile = ProfileManager.get_profile(google_id)
        if not profile:
            return None

        if game_key not in profile["ongoing_games"]:
            profile["ongoing_games"].append(game_key)

        try:
            profile_path = ProfileManager.get_profile_path(google_id)
            _atomic_write(profile_path, profile)
            return profile
        except Exception as e:
            log.error(f"Error adding ongoing game {google_id}: {e}")
            return None

    @staticmethod
    def remove_ongoing_game(google_id, game_key):
        """Remove game from ongoing_games list"""
        profile = ProfileManager.get_profile(google_id)
        if not profile:
            return None

        if game_key in profile["ongoing_games"]:
            profile["ongoing_games"].remove(game_key)

        try:
            profile_path = ProfileManager.get_profile_path(google_id)
            _atomic_write(profile_path, profile)
            return profile
        except Exception as e:
            log.error(f"Error removing ongoing game {google_id}: {e}")
            return None

    @staticmethod
    def update_erfolge(google_id, delta: dict, kaderwert: int):
        """
        Update manager achievements after a completed season.
        Args:
            google_id: Google user ID
            delta: dict with boolean flags for cups won this season:
                   {"meisterschaft": bool, "dfb_pokal": bool, "ecl": bool,
                    "pokalsieger": bool, "uefacup": bool}
            kaderwert: current squad market value (int)
        Returns: Updated profile dict
        """
        profile = ProfileManager.get_profile(google_id)
        if not profile:
            return None

        if "erfolge" not in profile:
            profile["erfolge"] = {
                "saisons": 0,
                "meisterschaften": 0,
                "dfb_pokale": 0,
                "ecl_titel": 0,
                "pokalsieger_titel": 0,
                "uefacup_titel": 0,
                "bester_kaderwert": 0,
            }

        e = profile["erfolge"]
        e["saisons"] = e.get("saisons", 0) + 1
        if delta.get("meisterschaft"):
            e["meisterschaften"] = e.get("meisterschaften", 0) + 1
        if delta.get("dfb_pokal"):
            e["dfb_pokale"] = e.get("dfb_pokale", 0) + 1
        if delta.get("ecl"):
            e["ecl_titel"] = e.get("ecl_titel", 0) + 1
        if delta.get("pokalsieger"):
            e["pokalsieger_titel"] = e.get("pokalsieger_titel", 0) + 1
        if delta.get("uefacup"):
            e["uefacup_titel"] = e.get("uefacup_titel", 0) + 1
        if kaderwert > e.get("bester_kaderwert", 0):
            e["bester_kaderwert"] = kaderwert

        try:
            profile_path = ProfileManager.get_profile_path(google_id)
            _atomic_write(profile_path, profile)
            return profile
        except Exception as ex:
            log.error(f"Error updating erfolge {google_id}: {ex}")
            return None

    @staticmethod
    def force_update(google_id, data: dict):
        """Direkte Profilaktualisierung ohne Feldrestriktionen (nur für serverseitige Admin-Befehle)."""
        profile = ProfileManager.get_profile(google_id)
        if not profile:
            return None
        profile.update(data)
        try:
            profile_path = ProfileManager.get_profile_path(google_id)
            _atomic_write(profile_path, profile)
            return profile
        except Exception as e:
            log.error(f"Error force-updating profile {google_id}: {e}")
            return None

    @staticmethod
    def list_profiles():
        """
        Get all manager profiles.
        Returns: list of profile dicts
        """
        ensure_profile_dir()
        profiles = []

        try:
            for profile_file in PROFILE_DIR.glob("*.json"):
                with open(profile_file, 'r', encoding='utf-8') as f:
                    profiles.append(json.load(f))
            return sorted(profiles, key=lambda p: p.get("statistics", {}).get("total_points", 0), reverse=True)
        except Exception as e:
            log.error(f"Error listing profiles: {e}")
            return []

    @staticmethod
    def get_leaderboard(limit=10):
        """
        Get top managers by points.
        Returns: list of top profiles
        """
        profiles = ProfileManager.list_profiles()
        return profiles[:limit]
