# Soccermaster: Google OAuth2 & Manager Profile

Dieses Dokument beschreibt die Google OAuth2-Integration und das Manager-Profile-System.

## Überblick

Das Spiel verwendet Google OAuth2-Authentifizierung:
- Manager-Profile mit vollständigen Statistiken und Erfolgen
- Spielstände speichern und laden (Pause/Resume)
- Manager-Historien tracken
- Leaderboards generieren

**Keine Datenbank erforderlich** – alles wird als JSON-Dateien in `data/` gespeichert.

---

## Installation & Setup

### 1. Google Cloud Project erstellen

1. Gehe zu https://console.cloud.google.com/
2. Erstelle ein neues Projekt
3. Aktiviere die **Google+ API** oder **People API**:
   - „APIs & Services" → „Library" → suche nach „Google People API" → Enable

### 2. OAuth2 Credentials erstellen

1. „APIs & Services" → „Credentials" → „Create Credentials" → „OAuth client ID"
2. Wähle **Web application**
3. Unter „Authorized redirect URIs" eintragen:
   - `http://localhost:8080/auth/callback` (Entwicklung)
   - `http://DEINE-DOMAIN:8080/auth/callback` (Production)
4. „Create" → Client ID und Client Secret kopieren

### 3. .env-Datei erstellen

```bash
cp .env.example .env
```

Bearbeite `.env`:

```env
GOOGLE_CLIENT_ID=518333125740-xxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxx
JWT_SECRET=dein-zufaelliger-secret-string

# Server-Konfiguration
DOMAIN=localhost          # Nur Domain, kein http:// und kein Port
HTTP_PORT=8080
WS_PORT=8765

# Optional – wird auto-hergeleitet als http://$DOMAIN:$HTTP_PORT/auth/callback
# REDIRECT_URI=http://localhost:8080/auth/callback
```

### 4. Python-Dependencies installieren

```bash
pip install -r requirements.txt
```

### 5. Server starten

```bash
python3 main.py
```

Server läuft auf:
- **HTTP**: `http://localhost:8080`
- **WebSocket**: `ws://localhost:8765`

---

## Authentifizierungsfluss

### Benutzer-Perspektive

1. Öffne `http://localhost:8080`
2. Klick „MIT GOOGLE ANMELDEN"
3. Google zeigt Consent Screen
4. Autorisieren → Weiterleitung zurück
5. Manager-Profil wird automatisch erstellt / aktualisiert
6. Lobby-Optionen erscheinen

### Technischer Fluss

```
Client Browser
  ↓ Klick "MIT GOOGLE ANMELDEN"
  ↓ Öffnet Google OAuth Consent URL
Google Consent Screen
  ↓ User autorisiert
  ↓ Google sendet auth_code zu /auth/callback
Server (main.py)
  ↓ /auth/callback empfängt auth_code
  ↓ Tauscht code gegen access_token
  ↓ Holt user_info von Google
  ↓ Erstellt/aktualisiert Manager-Profil (JSON)
  ↓ Generiert JWT auth_token
  ↓ Sendet zurück: {auth_token, manager_id, profile}
Client Browser
  ↓ Speichert auth_token in sessionStorage
  ↓ Verbindet WebSocket (Port aus /auth/google_config)
  ↓ Zeigt Lobby-Optionen
WebSocket (Lobby)
  ↓ Alle Nachrichten enthalten auth_token
  ↓ Server validiert Token vor jeder Aktion
```

---

## Manager-Profile

### Profil-Struktur

Gespeichert in `data/manager_profiles/{google_id}.json`:

```json
{
  "google_id": "118...",
  "email": "spieler@example.com",
  "name": "Max Mustermann",
  "nickname": "MaxM",
  "profile_image": "https://...",
  "manager_id": "MGR_20260228120000_118",
  "created_at": "2026-02-28T12:00:00Z",
  "last_login": "2026-03-08T15:30:00Z",
  "lieblingsverein": "FC Bayern München",
  "statistics": {
    "total_games": 5,
    "wins": 3,
    "draws": 1,
    "losses": 1,
    "total_points": 450,
    "avg_points_per_season": 90,
    "tore": 134,
    "gegentore": 67,
    "bester_kontostand": 12500000,
    "beste_saison": {
      "position": 1,
      "team": "FC Bayern München",
      "saison": 3,
      "punkte": 98
    },
    "match_siege": 87,
    "match_unentschieden": 22,
    "match_niederlagen": 13
  },
  "erfolge": {
    "saisons": 5,
    "meisterschaften": 3,
    "dfb_pokale": 1,
    "ecl_titel": 1,
    "pokalsieger_titel": 0,
    "uefacup_titel": 0,
    "bester_kaderwert": 13400000
  },
  "game_history": [
    {
      "game_key": "118_20260225120000_abc123",
      "date": "2026-02-25",
      "team": "FC Bayern München",
      "status": "completed",
      "final_position": 1,
      "punkte": 98,
      "saison": 1,
      "tore": 87,
      "gegentore": 31,
      "siege": 30,
      "unentschieden": 8,
      "niederlagen": 4,
      "kontostand": 12500000
    }
  ],
  "ongoing_games": ["118_20260308115500_xyz789"]
}
```

### Profile API-Endpunkte

#### Eigenes Profil abrufen
```
GET /api/profile?token={auth_token}
```

#### Laufende Spiele abrufen
```
GET /api/games?token={auth_token}
```

#### Leaderboard abrufen
```
GET /api/leaderboard?limit=10
```

#### WS-Port und Auth-Konfiguration
```
GET /auth/google_config
```
Antwort enthält u.a. `ws_port` – wird vom Client zum WebSocket-Verbindungsaufbau genutzt.

---

## WebSocket-Nachrichten mit OAuth

Alle WebSocket-Nachrichten müssen einen `auth_token` enthalten:

### Lobby erstellen
```javascript
wsSend({
  aktion: 'lobby_erstellen',
  auth_token: 'eyJhbGciOiJIUzI1NiI...',
  email: 'spieler@example.com',
  name: 'Max Mustermann'
});
```

### Spiel fortsetzen
```javascript
wsSend({
  aktion: 'resume_game',
  auth_token: 'eyJhbGciOiJIUzI1NiI...',
  game_key: '118_20260308115500_xyz789'
});
```

### Token-Validierung

- Gültiger Token → Aktion ausgeführt
- Ungültiger/abgelaufener Token → Fehler `"Authentifizierung erforderlich"`

---

## Profil-Synchronisation (Client)

Nach Login empfängt der Client bei jedem `online_spieler`-Broadcast sein eigenes Profil (erkannt via `google_id`-Abgleich) und speichert es als `S.meinProfil` – diese Variable ist die **einzige Quelle** für alle drei Profilansichten:

- Schnellprofil (Tooltip am Spielernamen)
- Profil-Modal (Klick auf eigenen Namen)
- Hauptmenü-Profil

Nach Admin-Stats-Edits sendet der Server zusätzlich `profil_refresh` direkt an den betroffenen Client.

---

## Admin-Konsole: Stats-Befehle

```
/stats list                           → Alle Profile anzeigen
/stats show <nickname>                → Ein Profil anzeigen
/stats edit <nickname> wins <n>       → Wins setzen
/stats edit <nickname> losses <n>     → Losses setzen
/stats edit <nickname> saisons <n>    → Abgeschlossene Saisons setzen
/stats edit <nickname> game_history reset   → Kompletten Reset (inkl. Erfolge)
```

---

## Datenverzeichnis-Struktur

```
data/
├── spieler.csv               # Spielerdatenbank
├── vereine.csv               # Vereinsdatenbank
├── manager_profiles/         # Manager-Profile (je 1 JSON pro Google-User)
│   ├── 118123456789.json
│   └── ...
└── game_saves/               # Gespeicherte Spielstände
    ├── 118_20260308_abc123.json
    └── ...
```

---

## Session & Token-Sicherheit

### sessionStorage vs localStorage

**Verwendet: `sessionStorage`** (sicherer)
- Token wird gelöscht wenn Browser-Tab geschlossen wird
- Kein Tab-übergreifendes Teilen
- Bleibt während einer Sitzung erhalten

**Nicht verwendet: `localStorage`**
- Würde Token dauerhaft speichern → XSS-anfälliger

### Token-Gültigkeitsdauer

- JWT-Tokens laufen nach **30 Tagen** ab
- Nach Ablauf: User muss sich neu anmelden

---

## Fehlerbehandlung

### Häufige Fehler

#### „OAuth2 not configured"
**Problem:** `GOOGLE_CLIENT_ID` oder `GOOGLE_CLIENT_SECRET` fehlen in `.env`

#### „Token exchange failed"
**Problem:** Ungültiger `auth_code` von Google
**Lösung:** Erneut anmelden, `/auth/callback` in Google Cloud prüfen

#### „Failed to create profile"
**Problem:** Dateisystem-Fehler
**Lösung:** `data/manager_profiles/` beschreibbar machen

#### „Spiel konnte nicht geladen werden"
**Problem:** Game-Save-Datei nicht gefunden
**Lösung:** `game_key` prüfen, Datei in `data/game_saves/` prüfen

---

## Troubleshooting

```bash
# Ports prüfen
lsof -i :8080
lsof -i :8765

# .env prüfen
cat .env

# Dependencies prüfen
pip list | grep -E "google|PyJWT|websockets|dotenv"
```

---

**Version:** 0.5.2
**Datum:** März 2026
