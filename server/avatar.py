"""
Avatar-Verarbeitung: C64-Pixeloptik mit echten VIC-II 16 Farben.
Avatare werden als 44×44 PNG in data/avatars/ gespeichert.
"""

import io
import logging
from pathlib import Path
import requests as _requests
from PIL import Image

log = logging.getLogger(__name__)

AVATAR_DIR = Path(__file__).parent.parent / "data" / "avatars"
AVATAR_SIZE = 44   # gespeicherte und angezeigte Größe (px)
PIXEL_SIZE  = 2    # Pixelraster-Faktor → 22×22 interne Pixel

# Originale C64 VIC-II Farben (VICE-Emulator Referenz)
C64_COLORS = [
    (0,   0,   0),    # 0  Schwarz
    (255, 255, 255),  # 1  Weiß
    (136, 57,  50),   # 2  Rot
    (103, 182, 189),  # 3  Cyan
    (139, 63,  150),  # 4  Lila
    (85,  160, 73),   # 5  Grün
    (64,  49,  141),  # 6  Blau
    (191, 206, 114),  # 7  Gelb
    (139, 84,  41),   # 8  Orange
    (87,  66,  0),    # 9  Braun
    (184, 105, 98),   # 10 Hellrot
    (80,  80,  80),   # 11 Dunkelgrau
    (120, 120, 120),  # 12 Grau
    (148, 224, 137),  # 13 Hellgrün
    (120, 105, 196),  # 14 Hellblau
    (159, 159, 159),  # 15 Hellgrau
]


def _nearest_c64(r: int, g: int, b: int) -> tuple:
    best, best_d = 0, float('inf')
    for i, (cr, cg, cb) in enumerate(C64_COLORS):
        d = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
        if d < best_d:
            best_d = d
            best = i
    return C64_COLORS[best]


def process_and_save(img_bytes: bytes, google_id: str) -> bool:
    """
    Verarbeitet Bild-Bytes: quadratisch zuschneiden, auf 22×22 verkleinern,
    C64-Palette anwenden, als 44×44 PNG speichern.
    Gibt True bei Erfolg zurück.
    """
    try:
        AVATAR_DIR.mkdir(parents=True, exist_ok=True)
        img = Image.open(io.BytesIO(img_bytes)).convert('RGB')

        # Quadratisch zuschneiden (zentriert)
        w, h = img.size
        side = min(w, h)
        left, top = (w - side) // 2, (h - side) // 2
        img = img.crop((left, top, left + side, top + side))

        # Auf interne Pixelrastergröße skalieren
        internal = AVATAR_SIZE // PIXEL_SIZE
        img = img.resize((internal, internal), Image.LANCZOS)

        # C64-Palette per Pixel anwenden
        out = Image.new('RGB', (internal, internal))
        src_px = img.load()
        out_px = out.load()
        for y in range(internal):
            for x in range(internal):
                out_px[x, y] = _nearest_c64(*src_px[x, y])

        # Auf Zielgröße hochskalieren (Nearest-Neighbor für Pixellook)
        out = out.resize((AVATAR_SIZE, AVATAR_SIZE), Image.NEAREST)

        # Altes Avatar löschen und neu speichern
        delete_avatar(google_id)
        out.save(AVATAR_DIR / f"{google_id}.png", 'PNG')
        return True
    except Exception as e:
        log.error(f"Avatar-Fehler ({google_id}): {e}")
        return False


def download_and_save(picture_url: str, google_id: str) -> bool:
    """Lädt Google-Profilbild herunter und speichert es verarbeitet."""
    try:
        resp = _requests.get(picture_url, timeout=5)
        if resp.status_code != 200:
            return False
        return process_and_save(resp.content, google_id)
    except Exception as e:
        log.error(f"Avatar-Download-Fehler ({google_id}): {e}")
        return False


def delete_avatar(google_id: str):
    """Löscht vorhandenes Avatar-Bild."""
    for ext in ('png', 'jpg', 'jpeg'):
        p = AVATAR_DIR / f"{google_id}.{ext}"
        if p.exists():
            p.unlink()


def avatar_path(google_id: str) -> Path | None:
    """Gibt den Pfad zum gespeicherten Avatar zurück, oder None."""
    p = AVATAR_DIR / f"{google_id}.png"
    return p if p.exists() else None


def avatar_url(google_id: str) -> str:
    """Gibt die HTTP-URL zum Avatar zurück."""
    return f"/api/avatar/{google_id}"
