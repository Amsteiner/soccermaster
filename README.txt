SOCCERMASTER – Retro Fußballmanager
====================================
Multiplayer-Fußballmanager im C64-Stil, Bundesliga-Saison 1983/84.
1–4 Spieler, Browser-basiert, kein Build-Schritt.


VORAUSSETZUNGEN
---------------
- Python 3.12 oder neuer
- Google-Account (für OAuth2-Login)
- Optional: eigene Domain + Nginx (für Produktivbetrieb)


SCHRITT 1: GOOGLE OAUTH2 EINRICHTEN
-------------------------------------
1. https://console.cloud.google.com/ aufrufen
2. Neues Projekt anlegen (beliebiger Name)
3. "APIs & Dienste" > "OAuth-Zustimmungsbildschirm"
   - Benutzertyp: Extern
   - App-Name und Support-E-Mail ausfüllen, speichern
4. "APIs & Dienste" > "Anmeldedaten" > "+ Anmeldedaten erstellen"
   > "OAuth 2.0-Client-ID"
   - Anwendungstyp: Webanwendung
   - Autorisierte Weiterleitungs-URIs:
       http://localhost:8080/auth/callback   (lokal)
       https://deine-domain.de/auth/callback (Produktion, falls gewünscht)
5. Client-ID und Client-Secret kopieren


SCHRITT 2: .ENV DATEI ANLEGEN
-------------------------------
.env.example kopieren und umbenennen:

    cp .env.example .env

Datei öffnen und Werte eintragen:

    GOOGLE_CLIENT_ID=     → Client-ID aus Schritt 1
    GOOGLE_CLIENT_SECRET= → Client-Secret aus Schritt 1
    REDIRECT_URI=         → http://localhost:8080/auth/callback
    JWT_SECRET=           → beliebige lange Zufallszeichenkette (geheim halten!)
    DOMAIN=               → localhost
    HTTP_PORT=            → 8080
    WS_PORT=              → 8765
    WS_URL=               → ws://localhost:8765


SCHRITT 3: DEV-ADMIN EINRICHTEN (OPTIONAL)
-------------------------------------------
In settings.cfg unter [dev]:

    reserved_emails = deine@googlemail.com

Diese E-Mail bekommt Owner-Rechte (Admin-Verwaltung, Debug-Befehle).
Leer lassen wenn nicht benötigt.


SCHRITT 4: PYTHON-UMGEBUNG EINRICHTEN
---------------------------------------
    python3 -m venv venv
    source venv/bin/activate          # Linux/Mac
    venv\Scripts\activate             # Windows
    pip install -r requirements.txt


SCHRITT 5: SERVER STARTEN
---------------------------
    python3 main.py

Browser öffnen: http://localhost:8080

Der Server startet:
  - HTTP-Server  auf Port 8080  (Webseite + API)
  - WebSocket    auf Port 8765  (Spiellogik)


MUSIK (OPTIONAL)
-----------------
Nur der OST-Ordner ist im Repository enthalten (music/ost/).
Weitere Formate können lokal hinzugefügt werden:

  music/sid/   → C64 SID-Dateien (*.sid)
  music/mod/   → Amiga MOD-Dateien (*.mod)
  music/mp3/   → MP3-Dateien (*.mp3)

Einstellungen unter [radio] in settings.cfg.


PRODUKTIVBETRIEB MIT NGINX
---------------------------
Beispiel-Nginx-Konfiguration für deine-domain.de:

    server {
        listen 80;
        server_name deine-domain.de;

        location /ws {
            proxy_pass http://127.0.0.1:8765;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }

        location / {
            proxy_pass http://127.0.0.1:8080;
            proxy_set_header Host $host;
        }
    }

In .env dann anpassen:
    DOMAIN=               → deine-domain.de
    REDIRECT_URI=         → https://deine-domain.de/auth/callback
    WS_URL=               → wss://deine-domain.de/ws


VERZEICHNISSTRUKTUR
--------------------
data/
  spieler.csv                  → Spielerdatenbank
  vereine.csv                  → Vereinsliste (BL1 + BL2)
  internationale_vereine.csv   → Europacup-Gegner
  manager_profiles/            → wird automatisch angelegt
  game_saves/                  → wird automatisch angelegt
  avatars/                     → wird automatisch angelegt

engine/      → Spiellogik (Match, Transfer, Finanzen usw.)
server/      → WebSocket-Server, OAuth, Profilverwaltung
music/ost/   → Soccermaster-Soundtrack
docs/        → Regelwerk und Spielbeschreibung (Deutsch)
