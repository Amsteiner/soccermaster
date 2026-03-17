#!/usr/bin/env python3
"""
SOCCERMASTER
==================
Retro Fußballmanager im C64-Style, 80er Bundesliga

Startet:
  - HTTP-Server  auf Port 8080  → liefert index.html + OAuth Routes
  - WebSocket-Server auf Port 8765 → Spiellogik
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
import socketserver
import threading
from urllib.parse import urlparse, parse_qs

from engine.settings import getlist as _cfg_list, getstr as _cfg_str
from server.console import setup as _console_setup, update_status as _update_status, teardown as _console_teardown
from server.lobby import LobbyServer
from server.google_auth import init_oauth
import server.netstat as _netstat

log = logging.getLogger(__name__)
from server.profile_manager import ProfileManager
from server.game_saver import GameSaver
from server.avatar import download_and_save as _dl_avatar, process_and_save as _proc_avatar
from server.avatar import avatar_url as _avatar_url, avatar_path as _avatar_path

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).parent
oauth_client = None
_SERVER_START = datetime.now()

# jsSID herunterladen falls noch nicht vorhanden oder nur Platzhalter (<10 KB)
def _ensure_jssid():
    import urllib.request
    dest = BASE_DIR / 'js' / 'jssid.js'
    dest.parent.mkdir(exist_ok=True)
    if dest.exists() and dest.stat().st_size > 10_000:
        return
    url = 'https://raw.githubusercontent.com/og2t/jsSID/master/source/jsSID.js'
    try:
        log.info('Lade jsSID herunter …')
        urllib.request.urlretrieve(url, dest)
        log.info(f'jsSID gespeichert ({dest.stat().st_size // 1024} KB)')
    except Exception as e:
        log.warning(f'jsSID-Download fehlgeschlagen: {e}')

_ensure_jssid()

def _ensure_chiptune2():
    import urllib.request
    js_dir = BASE_DIR / 'js'
    js_dir.mkdir(exist_ok=True)
    files = {
        'chiptune2.js':     'https://raw.githubusercontent.com/deskjet/chiptune2.js/master/chiptune2.js',
        'libopenmpt.js':    'https://raw.githubusercontent.com/deskjet/chiptune2.js/master/libopenmpt.js',
        'libopenmpt.js.mem':'https://raw.githubusercontent.com/deskjet/chiptune2.js/master/libopenmpt.js.mem',
    }
    for name, url in files.items():
        dest = js_dir / name
        if dest.exists() and dest.stat().st_size > 10_000:
            continue
        try:
            log.info(f'Lade {name} herunter …')
            urllib.request.urlretrieve(url, dest)
            log.info(f'{name} gespeichert ({dest.stat().st_size // 1024} KB)')
        except Exception as e:
            log.warning(f'{name}-Download fehlgeschlagen: {e}')

_ensure_chiptune2()

# Radio-Playlist: einmalig beim Start shuffeln, alle Clients teilen dieselbe Reihenfolge
def _mp3_meta(path) -> tuple[str, str]:
    """Liest Artist und Title aus MP3-ID3-Tags (ohne externe Lib via rohem Header)."""
    try:
        from mutagen.id3 import ID3
        tags = ID3(str(path))
        artist = str(tags.get('TPE1') or tags.get('TPE2') or '').strip()
        title  = str(tags.get('TIT2') or '').strip()
        return artist, title
    except Exception:
        return '', ''

def _sid_meta(path) -> tuple[str, str] | None:
    """Liest Name und Author aus SID-Header. Gibt None zurück bei RSID (nicht spielbar)."""
    try:
        data = open(path, 'rb').read(128)
        if data[:4] == b'RSID':
            return None  # RSID benötigt C64-ROM, jsSID kann es nicht abspielen
        title  = data[0x16:0x36].rstrip(b'\x00').decode('latin-1', 'replace').strip()
        author = data[0x36:0x56].rstrip(b'\x00').decode('latin-1', 'replace').strip()
        return author, title
    except Exception:
        return '', ''

def _mod_meta(path) -> tuple[str, str]:
    """Liest Titel aus MOD-Datei-Header (erste 20 Bytes). Autor nicht im Format."""
    try:
        data = open(path, 'rb').read(20)
        title = data.rstrip(b'\x00').decode('latin-1', 'replace').strip()
        return '', title
    except Exception:
        return '', ''

_MOD_EXTS = {'.mod', '.xm', '.it', '.s3m', '.669', '.med', '.stm'}

def _erstelle_radio_playlist() -> list[dict]:
    music_dir = BASE_DIR / 'music'
    tracks = []
    for subdir, ext in [('mp3', '.mp3'), ('ost', '.mp3'), ('sid', '.sid')]:
        d = music_dir / subdir
        if d.exists():
            for f in d.iterdir():
                if f.suffix.lower() == ext:
                    if subdir in ('mp3', 'ost'):
                        artist, title = _mp3_meta(f)
                    else:
                        meta = _sid_meta(f)
                        if meta is None:
                            continue  # RSID überspringen
                        artist, title = meta
                    if not title:
                        title = f.stem.replace('_', ' ')
                    tracks.append({'file': f'{subdir}/{f.name}', 'type': subdir,
                                   'title': title, 'artist': artist})
    mod_dir = music_dir / 'mod'
    if mod_dir.exists():
        for f in mod_dir.iterdir():
            if f.suffix.lower() in _MOD_EXTS:
                artist, title = _mod_meta(f)
                if not title:
                    title = f.stem.replace('_', ' ')
                tracks.append({'file': f'mod/{f.name}', 'type': 'mod',
                               'title': title, 'artist': artist})
    return tracks

_radio_playlist: list[str] = _erstelle_radio_playlist()

_OWNER_EMAILS = set(__import__('engine.settings', fromlist=['getlist']).getlist("dev", "reserved_emails"))
_ADMINS_FILE  = BASE_DIR / "data" / "admins.json"
_TESTERS_FILE = BASE_DIR / "data" / "testers.json"


def _load_admins() -> list:
    """Lädt zusätzliche Admin-Google-IDs aus data/admins.json."""
    try:
        if _ADMINS_FILE.exists():
            return json.loads(_ADMINS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _save_admins(google_ids: list):
    _ADMINS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ADMINS_FILE.write_text(json.dumps(google_ids, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_testers() -> list:
    """Lädt Tester-Google-IDs aus data/testers.json."""
    try:
        if _TESTERS_FILE.exists():
            return json.loads(_TESTERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _save_testers(google_ids: list):
    _TESTERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TESTERS_FILE.write_text(json.dumps(google_ids, ensure_ascii=False, indent=2), encoding="utf-8")


class APIHandler(SimpleHTTPRequestHandler):
    """
    Handles both static files and OAuth/API routes.
    Routes:
      - GET  /auth/google_config → OAuth configuration
      - POST /auth/callback → OAuth code exchange
      - GET  /api/profile → Current user profile
      - GET  /api/games → Ongoing games
      - GET  /api/leaderboard → Top managers
      - * → Static files (index.html, etc.)
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def end_headers(self):
        # No browser caching
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        super().end_headers()

    def log_message(self, *_):
        pass  # Suppress logs

    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # Google OAuth redirect callback (GET) – redirects back to index with code in URL
        if path == '/auth/callback':
            code = query.get('code', [None])[0]
            error = query.get('error', [None])[0]
            if error:
                self.send_response(302)
                self.send_header('Location', f'/?oauth_error={error}')
                self.end_headers()
            elif code:
                self.send_response(302)
                self.send_header('Location', f'/?auth_code={code}')
                self.end_headers()
            else:
                self.send_response(302)
                self.send_header('Location', '/')
                self.end_headers()

        # Google OAuth config
        elif path == '/auth/google_config':
            try:
                config = oauth_client.get_auth_endpoints()
                ws_url = os.getenv("WS_URL", "")
                if ws_url:
                    config["ws_url"] = ws_url
                else:
                    config["ws_port"] = int(os.getenv("WS_PORT", "8765"))
                self._send_json({"success": True, "data": config})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        # API: Get current user profile
        elif path == '/api/profile':
            try:
                auth_token = query.get('token', [None])[0]
                if not auth_token:
                    self._send_json({"success": False, "error": "No auth token"}, 401)
                    return

                manager_id, google_id = oauth_client.verify_auth_token(auth_token)
                if not manager_id or not google_id:
                    self._send_json({"success": False, "error": "Invalid token"}, 401)
                    return

                profile = ProfileManager.get_profile(google_id)
                self._send_json({"success": True, "data": profile})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        # API: Get ongoing games
        elif path == '/api/games':
            try:
                auth_token = query.get('token', [None])[0]
                if not auth_token:
                    self._send_json({"success": False, "error": "No auth token"}, 401)
                    return

                manager_id, google_id = oauth_client.verify_auth_token(auth_token)
                if not manager_id or not google_id:
                    self._send_json({"success": False, "error": "Invalid token"}, 401)
                    return

                saves = GameSaver.list_saves_for_google_id(google_id)
                game_details = []
                for s in saves:
                    mgr = next((m for m in s.get("managers", {}).values()
                                if m.get("google_id") == google_id), None)
                    game_details.append({
                        "game_key": s.get("game_key"),
                        "last_saved": s.get("last_saved"),
                        "matchday": s.get("matchday"),
                        "season": s.get("season"),
                        "status": s.get("status"),
                        "pinned": s.get("pinned", False),
                        "team": mgr.get("team") if mgr else None,
                    })
                self._send_json({"success": True, "data": game_details})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        # API: List music files (shuffled playlist, einmalig beim Start erstellt)
        elif path == '/api/music':
            self._send_json({"success": True, "songs": _radio_playlist})

        # API: Avatar-Bild ausliefern
        elif path.startswith('/api/avatar/'):
            google_id = path.split('/')[-1]
            p = _avatar_path(google_id)
            if p:
                try:
                    data = p.read_bytes()
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/png')
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except Exception:
                    self.send_response(500)
                    self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()

        # API: Get leaderboard
        elif path == '/api/leaderboard':
            try:
                limit = int(query.get('limit', [10])[0])
                leaderboard = ProfileManager.get_leaderboard(limit)
                self._send_json({"success": True, "data": leaderboard})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        # Admin: Prüft ob aktueller User Admin- oder Tester-Rechte hat
        elif path == '/api/admin/check':
            try:
                auth_token = query.get('token', [None])[0]
                self._send_json({"success": True, "is_admin": self._check_admin(auth_token), "is_tester": self._check_tester(auth_token), "is_dev": self._is_owner(auth_token)})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        # Admin: Admin-Liste + Online-Spieler abrufen
        elif path == '/api/admin/admins':
            try:
                auth_token = query.get('token', [None])[0]
                if not self._check_admin(auth_token):
                    self._send_json({"success": False, "error": "Forbidden"}, 403)
                    return
                from server.profile_manager import ProfileManager
                extra_ids = _load_admins()
                admins = []
                for gid in extra_ids:
                    p = ProfileManager.get_profile(gid)
                    admins.append({"google_id": gid, "nickname": (p or {}).get("nickname") or (p or {}).get("name") or gid})
                online = []
                if self._ws_server:
                    seen = set(extra_ids)
                    for u in self._ws_server.online_users.values():
                        gid = u.get("google_id") or ""
                        if gid and gid not in seen:
                            p = ProfileManager.get_profile(gid)
                            email = (p or {}).get("email", "").lower()
                            if email not in _OWNER_EMAILS:
                                seen.add(gid)
                                online.append({"google_id": gid, "nickname": u.get("name") or gid})
                self._send_json({"success": True, "admins": admins, "online": online})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        # Admin: Tester-Liste + alle registrierten Spieler abrufen
        elif path == '/api/admin/testers':
            try:
                auth_token = query.get('token', [None])[0]
                if not self._is_owner(auth_token):
                    self._send_json({"success": False, "error": "Nur der Owner darf Tester verwalten"}, 403)
                    return
                from server.profile_manager import ProfileManager, PROFILE_DIR
                tester_ids = _load_testers()
                testers = []
                for gid in tester_ids:
                    p = ProfileManager.get_profile(gid)
                    testers.append({"google_id": gid, "nickname": (p or {}).get("nickname") or (p or {}).get("name") or gid})
                # Alle registrierten Spieler (außer Owner und bereits Tester)
                alle = []
                seen = set(tester_ids)
                admin_ids = set(_load_admins())
                if PROFILE_DIR.exists():
                    for f in sorted(PROFILE_DIR.glob("*.json")):
                        gid = f.stem
                        if gid in seen:
                            continue
                        try:
                            p = json.loads(f.read_text(encoding="utf-8"))
                            email = p.get("email", "").lower()
                            if email in _OWNER_EMAILS:
                                continue
                            seen.add(gid)
                            nickname = p.get("nickname") or p.get("name") or gid
                            alle.append({"google_id": gid, "nickname": nickname, "is_admin": gid in admin_ids})
                        except Exception:
                            pass
                alle.sort(key=lambda x: x["nickname"].lower())
                self._send_json({"success": True, "testers": testers, "alle": alle})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        # Admin: settings.cfg lesen
        elif path == '/api/admin/settings':
            try:
                auth_token = query.get('token', [None])[0]
                if not self._check_admin(auth_token):
                    self._send_json({"success": False, "error": "Forbidden"}, 403)
                    return
                content = (BASE_DIR / "settings.cfg").read_text(encoding="utf-8")
                self._send_json({"success": True, "content": content})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        # Öffentliche Settings (kein Auth) – z.B. Radio-Defaults für neue Spieler
        elif path == '/api/downloads':
            dl_dir = BASE_DIR / "downloads"
            try:
                files = sorted(f.name for f in dl_dir.iterdir() if f.is_file()) if dl_dir.is_dir() else []
                self._send_json({"success": True, "files": files})
            except Exception as e:
                self._send_json({"success": False, "files": [], "error": str(e)})

        elif path == '/api/public_settings':
            try:
                import configparser as _cp
                _cfg = _cp.ConfigParser()
                _cfg.read(BASE_DIR / "settings.cfg", encoding="utf-8")
                radio = dict(_cfg['radio']) if 'radio' in _cfg else {}
                self._send_json({"success": True, "radio": radio})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        # Default: serve static files
        else:
            super().do_GET()

    def do_POST(self):
        """Handle POST requests"""
        parsed = urlparse(self.path)
        path = parsed.path

        # OAuth callback
        if path == '/auth/callback':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(body)
                auth_code = data.get('auth_code')

                if not auth_code:
                    self._send_json({"success": False, "error": "No auth_code"}, 400)
                    return

                # Exchange code for token
                access_token, user_info = oauth_client.exchange_code_for_token(auth_code)
                if not access_token or not user_info:
                    self._send_json({"success": False, "error": "Token exchange failed"}, 401)
                    return

                google_id = user_info.get('google_id')
                email = user_info.get('email')
                name = user_info.get('name')
                picture = user_info.get('picture')

                # Create or update profile
                existing = ProfileManager.get_profile(google_id)
                if existing:
                    profile = ProfileManager.update_profile(google_id, {
                        "last_login": datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
                    })
                else:
                    profile = ProfileManager.create_profile(google_id, email, name, picture)

                if not profile:
                    self._send_json({"success": False, "error": "Failed to create profile"}, 500)
                    return

                # Google-Avatar herunterladen und lokal als C64-Bild speichern
                if picture and not _avatar_path(google_id):
                    if _dl_avatar(picture, google_id):
                        profile = ProfileManager.update_profile(google_id, {"profile_image": _avatar_url(google_id)})

                manager_id = profile.get("manager_id")
                auth_token = oauth_client.generate_auth_token(manager_id, google_id)

                self._send_json({
                    "success": True,
                    "data": {
                        "auth_token": auth_token,
                        "manager_id": manager_id,
                        "profile": profile
                    }
                })
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        # API: Update profile (nickname)
        elif path == '/api/profile':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(body)
                auth_token = data.get('token')
                nickname = data.get('nickname', '').strip() if 'nickname' in data else None
                lieblingsverein = data.get('lieblingsverein')  # None = clear, string = set

                if not auth_token:
                    self._send_json({"success": False, "error": "No auth token"}, 401)
                    return

                manager_id, google_id = oauth_client.verify_auth_token(auth_token)
                if not manager_id or not google_id:
                    self._send_json({"success": False, "error": "Invalid token"}, 401)
                    return

                update_data = {}

                if nickname is not None:
                    valid, error = ProfileManager.validate_nickname(nickname)
                    if not valid:
                        self._send_json({"success": False, "error": error}, 400)
                        return

                    # Reservierte Nicknames – nur für den Dev-Admin
                    RESERVED = {n.lower() for n in _cfg_list("dev", "reserved_nicknames")}
                    RESERVED_OWNERS = {e.lower() for e in _cfg_list("dev", "reserved_emails")}
                    if nickname.lower() in RESERVED:
                        current = ProfileManager.get_profile(google_id)
                        if not current or current.get("email", "").lower() not in RESERVED_OWNERS:
                            self._send_json({"success": False, "error": "Dieser Nickname ist reserviert"}, 403)
                            return

                    update_data["nickname"] = nickname

                if 'lieblingsverein' in data:
                    update_data["lieblingsverein"] = lieblingsverein

                if 'radio_settings' in data and isinstance(data['radio_settings'], dict):
                    update_data["radio_settings"] = data['radio_settings']

                profile = ProfileManager.update_profile(google_id, update_data)
                if not profile:
                    self._send_json({"success": False, "error": "Profile not found"}, 404)
                    return

                self._send_json({"success": True, "data": {
                    "nickname": profile.get("nickname"),
                    "lieblingsverein": profile.get("lieblingsverein")
                }})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        # Google One-Tap / Sign-In Button credential verification
        elif path == '/auth/google_credential':
            try:
                if not oauth_client:
                    self._send_json({"success": False, "error": "OAuth not configured"}, 500)
                    return

                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(body)
                credential = data.get('credential')

                if not credential:
                    self._send_json({"success": False, "error": "No credential"}, 400)
                    return

                user_info = oauth_client.verify_google_credential(credential)
                if not user_info:
                    self._send_json({"success": False, "error": "Invalid credential"}, 401)
                    return

                google_id = user_info.get('google_id')
                email = user_info.get('email')
                name = user_info.get('name')
                picture = user_info.get('picture')

                existing = ProfileManager.get_profile(google_id)
                if existing:
                    profile = ProfileManager.update_profile(google_id, {
                        "last_login": datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
                    })
                else:
                    profile = ProfileManager.create_profile(google_id, email, name, picture)

                if not profile:
                    self._send_json({"success": False, "error": "Failed to create profile"}, 500)
                    return

                # Google-Avatar herunterladen und lokal als C64-Bild speichern
                if picture and not _avatar_path(google_id):
                    if _dl_avatar(picture, google_id):
                        profile = ProfileManager.update_profile(google_id, {"profile_image": _avatar_url(google_id)})

                manager_id = profile.get("manager_id")
                auth_token = oauth_client.generate_auth_token(manager_id, google_id)

                self._send_json({
                    "success": True,
                    "data": {
                        "auth_token": auth_token,
                        "manager_id": manager_id,
                        "profile": profile
                    }
                })
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        # API: Avatar hochladen (base64 JSON)
        elif path == '/api/avatar':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 4 * 1024 * 1024:  # 4 MB deckt 2 MB Datei + Base64-Overhead
                    self._send_json({"success": False, "error": "Bild zu groß (max 2 MB)"}, 413)
                    return
                body = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(body)
                auth_token = data.get('token')
                image_b64 = data.get('image_b64', '')

                if not auth_token:
                    self._send_json({"success": False, "error": "No auth token"}, 401)
                    return

                manager_id, google_id = oauth_client.verify_auth_token(auth_token)
                if not manager_id or not google_id:
                    self._send_json({"success": False, "error": "Invalid token"}, 401)
                    return

                # Base64-Präfix entfernen (data:image/...;base64,)
                if ',' in image_b64:
                    image_b64 = image_b64.split(',', 1)[1]

                import base64
                img_bytes = base64.b64decode(image_b64)
                ok = _proc_avatar(img_bytes, google_id)
                if not ok:
                    self._send_json({"success": False, "error": "Bildverarbeitung fehlgeschlagen"}, 500)
                    return

                url = _avatar_url(google_id)
                ProfileManager.update_profile(google_id, {"profile_image": url})
                self._send_json({"success": True, "profile_image": url})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        # API: Pin/Unpin game
        elif path == '/api/game/pin':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(body)
                auth_token = data.get('token')
                game_key = data.get('game_key')
                pinned = bool(data.get('pinned', True))

                if not auth_token:
                    self._send_json({"success": False, "error": "No auth token"}, 401)
                    return

                manager_id, google_id = oauth_client.verify_auth_token(auth_token)
                if not manager_id or not google_id:
                    self._send_json({"success": False, "error": "Invalid token"}, 401)
                    return

                ok = GameSaver.pin_game_save(game_key, google_id, pinned)
                if ok:
                    self._send_json({"success": True, "pinned": pinned})
                else:
                    self._send_json({"success": False, "error": "Save not found or not authorized"}, 404)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        # Admin: Admin hinzufügen / entfernen
        elif path == '/api/admin/admins':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(body)
                if not self._is_owner(data.get('token')):
                    self._send_json({"success": False, "error": "Nur der Owner darf Admins verwalten"}, 403)
                    return
                action = data.get('action')  # 'add' | 'remove'
                gid = data.get('google_id', '').strip()
                if not gid:
                    self._send_json({"success": False, "error": "Keine google_id"}, 400)
                    return
                admins = _load_admins()
                if action == 'add':
                    if gid not in admins:
                        admins.append(gid)
                    _save_admins(admins)
                elif action == 'remove':
                    admins = [a for a in admins if a != gid]
                    _save_admins(admins)
                else:
                    self._send_json({"success": False, "error": "Unbekannte Aktion"}, 400)
                    return
                # Betroffenen User live benachrichtigen
                if self._ws_server and self._loop and not self._loop.is_closed():
                    is_now_admin = gid in admins
                    async def _notify_admin_change(server=self._ws_server, target_gid=gid, is_admin=is_now_admin):
                        for u in server.online_users.values():
                            if u.get("google_id") == target_gid:
                                try:
                                    await u["ws"].send(json.dumps({"typ": "admin_status_changed", "is_admin": is_admin}))
                                except Exception:
                                    pass
                    asyncio.run_coroutine_threadsafe(_notify_admin_change(), self._loop)
                self._send_json({"success": True})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        # Admin: Tester hinzufügen / entfernen
        elif path == '/api/admin/testers':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(body)
                if not self._is_owner(data.get('token')):
                    self._send_json({"success": False, "error": "Nur der Owner darf Tester verwalten"}, 403)
                    return
                action = data.get('action')
                gid = data.get('google_id', '').strip()
                if not gid:
                    self._send_json({"success": False, "error": "Keine google_id"}, 400)
                    return
                testers = _load_testers()
                if action == 'add':
                    if self._check_admin_by_gid(gid):
                        self._send_json({"success": False, "error": "Admins können nicht als Tester eingetragen werden"}, 400)
                        return
                    if gid not in testers:
                        testers.append(gid)
                    _save_testers(testers)
                elif action == 'remove':
                    testers = [t for t in testers if t != gid]
                    _save_testers(testers)
                else:
                    self._send_json({"success": False, "error": "Unbekannte Aktion"}, 400)
                    return
                if self._ws_server and self._loop and not self._loop.is_closed():
                    is_now_tester = gid in testers
                    async def _notify_tester_change(server=self._ws_server, target_gid=gid, is_tester=is_now_tester):
                        for u in server.online_users.values():
                            if u.get("google_id") == target_gid:
                                try:
                                    await u["ws"].send(json.dumps({"typ": "tester_status_changed", "is_tester": is_tester}))
                                except Exception:
                                    pass
                    asyncio.run_coroutine_threadsafe(_notify_tester_change(), self._loop)
                self._send_json({"success": True})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        # Admin: settings.cfg speichern
        elif path == '/api/admin/settings':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(body)
                google_id, profile = self._verify_token(data.get('token'))
                if not google_id or not self._check_admin(data.get('token')):
                    self._send_json({"success": False, "error": "Forbidden"}, 403)
                    return
                cfg_path = BASE_DIR / "settings.cfg"
                # Backup der vorherigen settings.cfg anlegen
                if cfg_path.exists():
                    bak_dir = BASE_DIR / "data" / "settings.bak"
                    bak_dir.mkdir(parents=True, exist_ok=True)
                    nick = (profile or {}).get("nickname") or (profile or {}).get("name") or google_id
                    nick_safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in nick)
                    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    bak_path = bak_dir / f"{nick_safe}_{ts}.cfg"
                    bak_path.write_bytes(cfg_path.read_bytes())
                cfg_content = data.get('content', '')
                cfg_path.write_text(cfg_content, encoding="utf-8")
                self._send_json({"success": True})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        # Admin: Server neu starten
        elif path == '/api/admin/restart':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(body)
                if not self._check_admin(data.get('token')):
                    self._send_json({"success": False, "error": "Forbidden"}, 403)
                    return
                self._send_json({"success": True})
                import threading as _th, os as _os, signal as _sig
                if self._ws_server:
                    self._ws_server._neustart = True
                _th.Timer(0.3, lambda: _os.kill(_os.getppid(), _sig.SIGUSR1)).start()
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        """Handle DELETE requests"""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == '/api/game':
            try:
                auth_token = query.get('token', [None])[0]
                game_key = query.get('game_key', [None])[0]

                if not auth_token:
                    self._send_json({"success": False, "error": "No auth token"}, 401)
                    return

                manager_id, google_id = oauth_client.verify_auth_token(auth_token)
                if not manager_id or not google_id:
                    self._send_json({"success": False, "error": "Invalid token"}, 401)
                    return

                ok = GameSaver.delete_game_save(game_key, google_id)
                if ok:
                    self._send_json({"success": True})
                else:
                    self._send_json({"success": False, "error": "Save not found or not authorized"}, 404)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)
        else:
            self.send_response(404)
            self.end_headers()

    _ws_server = None  # Wird in main() gesetzt
    _loop = None       # Wird in main() gesetzt

    def _verify_token(self, auth_token):
        """Gibt (google_id, profile) zurück oder (None, None) bei Fehler."""
        if not oauth_client or not auth_token:
            return None, None
        try:
            manager_id, google_id = oauth_client.verify_auth_token(auth_token)
            if not manager_id or not google_id:
                return None, None
            from server.profile_manager import ProfileManager
            profile = ProfileManager.get_profile(google_id)
            return google_id, profile
        except Exception:
            return None, None

    def _check_admin(self, auth_token) -> bool:
        """Prüft ob auth_token Owner oder zusätzlicher Admin ist."""
        google_id, profile = self._verify_token(auth_token)
        if not google_id or not profile:
            return False
        email = profile.get("email", "").lower()
        if email in _OWNER_EMAILS:
            return True
        return google_id in _load_admins()

    def _check_admin_by_gid(self, google_id: str) -> bool:
        """Prüft ob eine google_id Admin-Rechte hat (ohne Token)."""
        return google_id in _load_admins()

    def _is_owner(self, auth_token) -> bool:
        """Prüft ob auth_token der Owner (Dev-Admin laut settings.cfg [dev] reserved_emails) ist."""
        _, profile = self._verify_token(auth_token)
        return bool(profile and profile.get("email", "").lower() in _OWNER_EMAILS)

    def _check_tester(self, auth_token) -> bool:
        """Prüft ob auth_token ein Tester ist."""
        google_id, profile = self._verify_token(auth_token)
        if not google_id or not profile:
            return False
        return google_id in _load_testers()

    def _send_json(self, data, status=200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))


def erstelle_backup():
    """Erstellt ein Zip-Backup des Projektordners im backups/-Verzeichnis.
    Dateiname: soccermaster_vX.Y.Z.zip (wie in der Versions-Konvention)."""
    try:
        version = (BASE_DIR / "VERSION").read_text(encoding="utf-8").strip()
        backup_name = f"soccermaster_v{version}.zip"
        backup_dir = BASE_DIR / "backups"
        backup_dir.mkdir(exist_ok=True)
        backup_path = backup_dir / backup_name
        proj_name = BASE_DIR.name
        log.info(f"Erstelle Backup soccermaster_v{version}.zip ...")
        result = subprocess.run(
            ["zip", "-r", str(backup_path), proj_name,
             "--exclude", f"{proj_name}/backups/*",
             "--exclude", f"{proj_name}/music/*",
             "--exclude", f"{proj_name}/venv/*",
             "--exclude", f"{proj_name}/__pycache__/*",
             "--exclude", f"{proj_name}/**/__pycache__/*"],
            capture_output=True,
            cwd=str(BASE_DIR.parent),
        )
        if result.returncode == 0:
            size_mb = backup_path.stat().st_size / 1_048_576
            log.info(f"Backup fertig: {backup_path} ({size_mb:.1f} MB)")
        else:
            log.error(f"Backup fehlgeschlagen: {result.stderr.decode()}")
    except Exception as e:
        log.error(f"Backup-Fehler: {e}")


def erstelle_nachtbackup():
    """Nachtbackup: YYMMDD + nightlybackup.zip, ohne music/-Ordner."""
    try:
        dateiname = datetime.now().strftime("%y%m%d") + "nightlybackup.zip"
        backup_dir = BASE_DIR / "backups" / "nightly"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / dateiname
        proj_name = BASE_DIR.name
        log.info(f"Nachtbackup wird erstellt: {dateiname} ...")
        result = subprocess.run(
            ["zip", "-r", str(backup_path), proj_name,
             "--exclude", f"{proj_name}/backups/*",
             "--exclude", f"{proj_name}/music/*",
             "--exclude", f"{proj_name}/venv/*",
             "--exclude", f"{proj_name}/__pycache__/*",
             "--exclude", f"{proj_name}/**/__pycache__/*"],
            capture_output=True,
            cwd=str(BASE_DIR.parent),
        )
        if result.returncode == 0:
            size_mb = backup_path.stat().st_size / 1_048_576
            log.info(f"Nachtbackup fertig: {backup_path} ({size_mb:.1f} MB)")
            _log_leeren_nach_backup(dateiname)
        else:
            log.error(f"Nachtbackup fehlgeschlagen: {result.stderr.decode()}")
    except Exception as e:
        log.error(f"Nachtbackup-Fehler: {e}")


def _log_leeren_nach_backup(backup_dateiname: str):
    """Log-Datei leeren und ersten Eintrag mit Server-Startzeit + Backup-Hinweis schreiben."""
    import logging
    log_path = BASE_DIR / "logs" / "server.log"
    try:
        # Alle FileHandler des Root-Loggers kurz schließen, Datei leeren, wieder öffnen
        root = logging.getLogger()
        fh = next((h for h in root.handlers if isinstance(h, logging.FileHandler)
                   and "server.log" in str(h.baseFilename)), None)
        if fh:
            fh.acquire()
            try:
                fh.stream.close()
                with open(log_path, "w", encoding="utf-8") as f:
                    jetzt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(
                        f"[{jetzt}] INFO   === LOG GELEERT nach Nachtbackup: {backup_dateiname} ===\n"
                        f"[{jetzt}] INFO   === SERVER läuft seit {_SERVER_START.strftime('%d.%m.%Y %H:%M:%S')} ===\n"
                    )
                fh.stream = open(log_path, "a", encoding="utf-8")
            finally:
                fh.release()
    except Exception as e:
        log.error(f"Log-Leeren fehlgeschlagen: {e}")


async def _nachtbackup_task():
    """Läuft täglich um 03:00 Uhr und erstellt ein Nachtbackup."""
    while True:
        jetzt = datetime.now()
        naechste = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
        if naechste <= jetzt:
            from datetime import timedelta
            naechste = naechste + timedelta(days=1)
        warte_sek = (naechste - jetzt).total_seconds()
        log.info(f"Nächstes Nachtbackup um {naechste.strftime('%d.%m.%Y 00:00')} ({warte_sek/3600:.1f} h)")
        await asyncio.sleep(warte_sek)
        await asyncio.get_running_loop().run_in_executor(None, erstelle_nachtbackup)


def starte_stdin_listener(ws_server=None, loop=None):
    """Liest direkt von /dev/tty (Raw-Mode). 'b' → Backup, 'r' → Speichern+Refresh, 'q' → Beenden."""
    try:
        import termios, os, signal
        tty_fd = open('/dev/tty', 'rb')
        old = termios.tcgetattr(tty_fd)
        try:
            # Kein Echo, kein Canonical-Mode → getippte Zeichen erscheinen nicht im Terminal
            new = termios.tcgetattr(tty_fd)
            new[3] &= ~(termios.ECHO | termios.ICANON)
            new[6][termios.VMIN] = 1
            new[6][termios.VTIME] = 0
            termios.tcsetattr(tty_fd, termios.TCSADRAIN, new)
            while True:
                ch = tty_fd.read(1)
                if ch in (b'b', b'B'):
                    erstelle_backup()
                elif ch in (b'r', b'R'):
                    if ws_server and loop and not loop.is_closed():
                        asyncio.run_coroutine_threadsafe(ws_server.save_all_games(), loop)
                    sys.stdout.write("\033[2J\033[H")
                    sys.stdout.flush()
                    _console_setup()
                elif ch in (b'q', b'Q'):
                    termios.tcsetattr(tty_fd, termios.TCSADRAIN, old)
                    tty_fd.close()
                    os.kill(os.getpid(), signal.SIGTERM)
                    return
        finally:
            termios.tcsetattr(tty_fd, termios.TCSADRAIN, old)
            tty_fd.close()
    except Exception:
        pass


class QuietTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        import sys
        if sys.exc_info()[0] in (ConnectionResetError, BrokenPipeError):
            return  # Browser TCP-Reset – kein echtes Disconnect
        super().handle_error(request, client_address)


def starte_http_server(port: int = 8080):
    with QuietTCPServer(("", port), APIHandler) as httpd:
        httpd.serve_forever()


async def _status_task(ws_server: LobbyServer):
    """Aktualisiert die fixe Statuszeile alle 2 Sekunden."""
    import psutil
    INTERVAL = 2
    proc = psutil.Process()
    proc.cpu_percent(interval=None)  # Erster Aufruf initialisiert den Zähler
    rx_prev = _netstat.rx
    tx_prev = _netstat.tx
    while True:
        await asyncio.sleep(INTERVAL)
        try:
            cpu = proc.cpu_percent(interval=None)
            mem = proc.memory_info().rss // (1024 * 1024)
            ws_conns = len(ws_server.verbindungen)
            active_lobbies = sum(1 for lb in ws_server.lobbys.values() if lb.phase != "warten")
            rx_cur = _netstat.rx
            tx_cur = _netstat.tx
            rx_kb = (rx_cur - rx_prev) / INTERVAL / 1024
            tx_kb = (tx_cur - tx_prev) / INTERVAL / 1024
            rx_prev = rx_cur
            tx_prev = tx_cur
            ts = datetime.now().strftime("%H:%M:%S")
            _update_status(
                f" CPU {cpu:4.1f}%  RAM {mem} MB  "
                f"↓{rx_kb:5.1f} KB/s  ↑{tx_kb:5.1f} KB/s  "
                f"WS {ws_conns}  Lobbys {active_lobbies}  {ts}"
            )
        except Exception:
            pass


async def main():
    global _SERVER_START
    _SERVER_START = datetime.now()
    _console_setup()

    # Initialize OAuth client
    global oauth_client
    try:
        oauth_client = init_oauth()
        log.info("Google OAuth2 initialisiert")
    except ValueError as e:
        log.warning(f"OAuth2 nicht konfiguriert: {e}")
        oauth_client = None

    _http_port = int(os.getenv("HTTP_PORT", "8080"))
    _ws_port   = int(os.getenv("WS_PORT",   "8765"))

    # HTTP-Server in eigenem Thread
    http_thread = threading.Thread(target=starte_http_server, args=(_http_port,), daemon=True)
    http_thread.start()
    log.info(f"HTTP-Server läuft auf http://0.0.0.0:{_http_port}")

    # Stdin-Listener für Backup-Befehl (wird nach ws_server-Init gestartet, s.u.)
    _stdin_thread_holder = [None]

    # WebSocket-Server (async, Hauptthread)
    ws_server = LobbyServer(host="0.0.0.0", port=_ws_port)
    ws_server.oauth_client = oauth_client
    APIHandler._ws_server = ws_server

    loop = asyncio.get_running_loop()
    APIHandler._loop = loop

    # Stdin-Listener jetzt starten, damit ws_server und loop übergeben werden können
    _stdin_thread_holder[0] = threading.Thread(
        target=starte_stdin_listener, args=(ws_server, loop), daemon=True)
    _stdin_thread_holder[0].start()

    def _on_sigint():
        loop.create_task(ws_server.shutdown())

    def _on_sigusr1():
        ws_server._neustart = True

    loop.add_signal_handler(__import__('signal').SIGINT, _on_sigint)
    loop.add_signal_handler(__import__('signal').SIGTERM, _on_sigint)
    loop.add_signal_handler(__import__('signal').SIGUSR1, _on_sigusr1)

    # Status-Task und Nachtbackup-Task starten
    asyncio.create_task(_status_task(ws_server))
    asyncio.create_task(_nachtbackup_task())

    await ws_server.start()

    _console_teardown()
    log.info("Server beendet.")
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())

