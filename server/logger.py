"""
Einfaches Datei-Logging für Soccermaster.
Schreibt täglich eine neue Logdatei in logs/YY-MM-DD.txt.
Geloggt werden: Connects, Disconnects, Reconnects und Chat-Nachrichten.
"""

from datetime import datetime
from pathlib import Path

_LOG_DIR = Path(__file__).parent.parent / "logs"


def _email_fuer(google_id: str) -> str | None:
    """Schlägt die Email-Adresse für eine Google-ID nach."""
    if not google_id:
        return None
    try:
        from server.profile_manager import ProfileManager
        profil = ProfileManager.get_profile(google_id)
        return profil.get("email") if profil else None
    except Exception:
        return None


def _absender(name: str, google_id: str = None) -> str:
    email = _email_fuer(google_id)
    if email:
        return f"{name} <{email}>"
    return name


def _schreiben(ereignis: str, details: str = ""):
    _LOG_DIR.mkdir(exist_ok=True)
    now = datetime.now()
    datum = now.strftime("%y/%m/%d")
    zeit = now.strftime("%H:%M:%S")
    dateiname = now.strftime("%y-%m-%d") + ".txt"
    zeile = f"{datum} {zeit} | {ereignis}"
    if details:
        zeile += f" | {details}"
    with open(_LOG_DIR / dateiname, "a", encoding="utf-8") as f:
        f.write(zeile + "\n")


def log_connect(name: str, google_id: str = None, email: str = None):
    if email:
        details = f"{name} <{email}>"
    else:
        details = _absender(name, google_id)
    _schreiben("CONNECT", details)


def log_disconnect(name: str, google_id: str = None):
    _schreiben("DISCONNECT", _absender(name, google_id))


def log_reconnect(name: str, google_id: str = None):
    _schreiben("RECONNECT", _absender(name, google_id))


def log_chat(name: str, text: str, bereich: str = "global", google_id: str = None):
    kanal = bereich.upper()
    _schreiben(f"CHAT/{kanal}", f"{_absender(name, google_id)}: {text}")
