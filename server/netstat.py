"""
Applikationsweiter Netzwerk-Byte-Zähler.
Wird von lobby.py (WebSocket) und main.py (HTTP) befüllt.
"""

rx: int = 0  # empfangene Bytes
tx: int = 0  # gesendete Bytes
