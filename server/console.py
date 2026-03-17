"""
Console UI
Strukturierte Logs + fixe Status-Zeile via ANSI-Scroll-Region
"""

import sys
import shutil
import logging
from datetime import datetime
from pathlib import Path

# Anzahl Zeilen am unteren Rand für Status reservieren
_STATUS_LINES = 2
_initialized = False


def _rows() -> int:
    return shutil.get_terminal_size((80, 24)).lines


def _cols() -> int:
    return shutil.get_terminal_size((80, 24)).columns


def setup():
    """Scroll-Region setzen und Logging konfigurieren."""
    global _initialized
    rows = _rows()
    scroll_end = rows - _STATUS_LINES

    # Scroll-Region: nur bis zur vorletzten Zeile
    sys.stdout.write(f"\033[1;{scroll_end}r")
    # Cursor ans Ende der Scroll-Region
    sys.stdout.write(f"\033[{scroll_end};1H")
    sys.stdout.flush()

    # Separator + leere Statuszeile zeichnen
    _draw_separator()

    # Root-Logger konfigurieren
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Vorhandene Handler entfernen (vermeidet Duplikate)
    root.handlers.clear()
    root.addHandler(_ScrollHandler())

    # File-Handler: logs/server.log (unlimitiert; wird nach Nachtbackup geleert)
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    fh = logging.FileHandler(log_dir / "server.log", mode="a", encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)-5s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(fh)
    logging.getLogger().info(f"=== SERVER GESTARTET um {datetime.now().strftime('%d.%m.%Y %H:%M:%S')} ===")

    _initialized = True


def teardown():
    """Scroll-Region zurücksetzen beim Beenden."""
    sys.stdout.write("\033[r")       # Scroll-Region aufheben
    sys.stdout.write("\033[?25h")    # Cursor einblenden
    sys.stdout.flush()


def _draw_separator():
    cols = _cols()
    rows = _rows()
    sep_row = rows - _STATUS_LINES + 1
    sys.stdout.write(
        f"\033[s"
        f"\033[{sep_row};1H\033[2K"
        f"\033[38;5;240m{'─' * cols}\033[0m"
        f"\033[u"
    )
    sys.stdout.flush()


def update_status(text: str):
    """Statuszeile ganz unten aktualisieren (thread-safe via einfaches Write)."""
    rows = _rows()
    status_row = rows
    sys.stdout.write(
        f"\033[s"
        f"\033[{status_row};1H\033[2K"
        f"\033[1m{text}\033[0m"
        f"\033[u"
    )
    sys.stdout.flush()


class _ScrollHandler(logging.Handler):
    """Logging-Handler der Ausgaben in die Scroll-Region schreibt."""

    LEVEL_COLORS = {
        logging.DEBUG:    "\033[38;5;244m",   # grau
        logging.INFO:     "\033[38;5;252m",   # hell
        logging.WARNING:  "\033[38;5;214m",   # orange
        logging.ERROR:    "\033[38;5;196m",   # rot
        logging.CRITICAL: "\033[38;5;196;1m", # rot+fett
    }
    LEVEL_LABELS = {
        logging.DEBUG:    "DEBUG",
        logging.INFO:     "INFO ",
        logging.WARNING:  "WARN ",
        logging.ERROR:    "ERROR",
        logging.CRITICAL: "CRIT ",
    }
    RESET = "\033[0m"

    def emit(self, record: logging.LogRecord):
        try:
            ts = datetime.now().strftime("%H:%M:%S")
            label = self.LEVEL_LABELS.get(record.levelno, "?    ")
            color = self.LEVEL_COLORS.get(record.levelno, "")
            msg = self.format(record)
            # Kein Traceback-Prefix-Leerzeile nötig
            line = f"{color}[{ts}] {label}  {msg}{self.RESET}\n"
            sys.stdout.write(line)
            sys.stdout.flush()
        except Exception:
            pass
