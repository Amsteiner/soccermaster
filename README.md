SOCCERMASTER
============
Retro football management game inspired by Soccermaster (Thorsten Wölki, 1987)
Bundesliga manager, 1983/84 season — C64 aesthetic, multiplayer, browser-based

## Files

| Path | Description |
|------|-------------|
| `index.html` | Frontend (single-page app, no build step required) |
| `main.py` | Server entry point |
| `requirements.txt` | Python dependencies |
| `settings.cfg` | Game parameters (match, transfers, finances, AI, …) |
| `.env` | Runtime config (OAuth, ports, domain) |
| `engine/` | Game logic (match simulation, transfers, finances, …) |
| `server/` | HTTP/WebSocket server, OAuth, profiles |
| `data/` | Player and club data (CSV) |
| `docs/` | Game rules, club list, CSV specification |
| `i18n/` | Language files (`de.json`, `en.json`, `help.de.html`, `help.en.html`) |

## Quick Start (demo, no server)

1. Open `index.html` directly in a browser
2. Click **PLAY DEMO**

## Quick Start (full server)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in Google OAuth credentials
python3 main.py
```

Then open `http://localhost:8080`.

## Live Server

<https://soccermaster.amsteiner.de>

## Configuration (.env)

| Variable | Description |
|----------|-------------|
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `REDIRECT_URI` | OAuth redirect URI, e.g. `https://HOST/auth/callback` |
| `JWT_SECRET` | Random secret string for token signing |
| `DOMAIN` | Server domain without port, e.g. `localhost` |
| `HTTP_PORT` | HTTP port (default `8080`) |
| `WS_PORT` | WebSocket port, internal (default `8765`) |
| `WS_URL` | WebSocket URL via proxy, e.g. `wss://HOST/ws` |

## Ports

| Port | Purpose |
|------|---------|
| `:8080` | HTTP — serves `index.html`, REST API, OAuth callback |
| `:8765` | WebSocket — multiplayer real-time game logic (internal; exposed via Nginx `/ws`) |

## Nginx (reverse proxy)

```nginx
# HTTP
proxy_pass http://127.0.0.1:8080;

# WebSocket
location /ws {
    proxy_pass http://127.0.0.1:8765;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "Upgrade";
}
```

HTTPS via Let's Encrypt: `certbot --nginx`

## Console shortcuts (while server is running)

| Key | Action |
|-----|--------|
| `q` | Graceful shutdown |
| `r` | Save all active games + refresh display |
| `b` | Create a manual backup |

## Features (March 2026 — v0.7.36)

- Google OAuth2 login with manager profiles and statistics
- HTTPS / WSS (Let's Encrypt, Nginx reverse proxy)
- Multiplayer lobbies: 2–4 managers per lobby with invite code
- Full season loop: transfers → squad setup → matchday → finances
- Match engine with formation bonuses, injuries, and cards
- DFB-Pokal (knockout, home & away legs, extra time, penalty shootouts)
- European cups (ECL, Cup Winners' Cup, UEFA Cup)
- Promotion/relegation (Bundesliga 1 ↔ Bundesliga 2)
- Player development: domestic players improve or decline each season
- Transfer market: domestic (shared offers) and foreign (scarce, unique)
- Save/load game states (pause & resume, solo and multiplayer)
- Manager statistics and leaderboard
- Avatar upload with crop editor (C64 pixel style)
- Retro themes: C64, ZX Spectrum, CGA, Macintosh, Commodore PET, …
- Music radio: MP3, SID chiptune, MOD tracker with track navigation
- AFK mode: inactive players are automatically counted as ready
- Spectator mode: watch cup and relegation matches live
- Admin panel with chat commands (`/kick`, `/mute`, `/announce`, …)
- Bilingual UI: German and English (flag buttons to switch language)

## Pending

- Complete player CSV (1000+ players; currently a partial dataset)

---

*March 2026 — v0.7.36*
