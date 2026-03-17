"""
Lädt settings.cfg einmalig beim Import.
Zugriff: from engine.settings import CFG
"""

import configparser
from pathlib import Path

_base = Path(__file__).parent.parent / "settings.cfg"
_local = Path(__file__).parent.parent / "settings.local.cfg"
CFG = configparser.ConfigParser()
CFG.read([_base, _local], encoding="utf-8")  # local überschreibt base


def getint(section: str, key: str) -> int:
    return CFG.getint(section, key)

def getfloat(section: str, key: str) -> float:
    raw = CFG.get(section, key).replace(',', '.')
    return float(raw)

def getstr(section: str, key: str, fallback: str = "") -> str:
    return CFG.get(section, key, fallback=fallback).strip()

def getlist(section: str, key: str) -> list:
    """Kommagetrennte Liste aus der Config lesen. Leere Einträge werden ignoriert."""
    raw = CFG.get(section, key, fallback="")
    return [v.strip() for v in raw.split(",") if v.strip()]
