# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Retro multiplayer football management game inspired by SoccerMaster (Thorsten Wölki, 1987). Bundesliga season 1983/84, C64 aesthetic (Press Start 2P font, brown/gold palette). Live server: https://soccermaster.amsteiner.de. Current version in `VERSION` file.

## Quick Start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # fill Google OAuth credentials, JWT_SECRET, domain, ports
python3 main.py          # or ./start.sh  (adds auto-restart on 'r', quit on 'q')
```

- **Port 8080**: HTTP (`index.html`, REST, OAuth callback `/auth/callback`)
- **Port 8765**: WebSocket (multiplayer game logic; behind Nginx as `/ws` in prod)

Demo mode: open `index.html` directly; multiplayer features disabled.

### Server console shortcuts (while `python3 main.py` is running)
- `q` — graceful shutdown
- `r` — save all active games + refresh display
- `b` — manual backup

## Architecture

### Backend — `main.py` (1200+ lines)
Entry point. Boots the HTTP server, the WebSocket server, static routing, REST endpoints, OAuth callback handling, and console input loop. *Not* just a launcher — treat it as the HTTP/REST layer.

### Backend — `server/` (session, auth, persistence)
- `lobby.py` (4000+ lines) — **central game orchestrator**. Manages lobbies (2–4 managers, invite code), routes every WebSocket message (`{"type": "...", "data": {...}}`), drives the season state machine (management → match → finances → injuries), handles chat, admin commands, spectator mode, AFK.
- `google_auth.py` — Google OAuth2 flow, JWT issuance
- `profile_manager.py` — persistent manager profiles + lifetime stats (`data/manager_profiles/`)
- `game_saver.py` — pause/resume save files (`data/game_saves/`, `data/mp_saves/`)
- `avatar.py` — avatar upload + C64-pixel crop editor
- `console.py` — keyboard shortcuts (`q`/`r`/`b`)
- `logger.py`, `netstat.py` — utilities

### Game Engine — `engine/`
- `game_state.py` — domain models (`Spieler`, `Team`, `GameState`). Loads players/clubs from CSV, names from `namen.cfg` (per-country name lists for random player generation).
- `match.py` — match simulation. Formations, position-dependent strength, real-time event callbacks (goals, cards, injuries), extra time & penalty shootouts for cup matches.
- `draft.py` — balanced initial squad distribution
- `transfer.py` — two tiers:
  - **Inlandsmarkt**: 3 offers/week, partly shared between managers (encourages trading)
  - **Ausland**: 1 unique offer per manager (scarce)
- `finanzen.py` — weekly salaries, matchday revenue by league position
- `spielplan.py` — double round-robin schedule generator
- `cpu_ai.py` — AI-controlled managers (transfers, lineup, formation)
- `settings.py` — reads tunables from `settings.cfg`

### Frontend — `index.html`
Single-page app, ~6900 lines, 355 KB, **no build step, no framework**. Contains all screens (lobby, team selection, squad, transfers, match view, standings, cups, admin panel, themes, music radio). WebSocket client to port 8765 (or `/ws` via proxy). All game state lives server-side; frontend is presentation only.

### Configuration surfaces
- `settings.cfg` — gameplay tunables (match engine, transfers, finances, AI weights). Read via `engine/settings.py`. `settings.local.cfg` overrides (gitignored).
- `.env` — runtime secrets + network config (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `REDIRECT_URI`, `JWT_SECRET`, `DOMAIN`, `HTTP_PORT`, `WS_PORT`, `WS_URL`). Gitignored; template in `.env.example`.
- `namen.cfg` — first/last name pools keyed by nationality section

### Key patterns
- **Hidden strength**: player strength is a category string in CSV (`Weltklasse`, `Sehr stark`, `Stark`, `Durchschnitt`, `Schwach`, `Sehr schwach`); numeric resolution happens server-side via position mapping in `match.py`. Frontend never sees numbers.
- **Position-dependent strength**: a "Stark" midfielder may compute as "Weltklasse" when slotted as defender and "Gut" as striker.
- **WebSocket protocol**: JSON `{"type": "action_name", "data": {...}}`, request/response.
- **Cups**: DFB-Pokal, ECL, Cup Winners' Cup, UEFA-Pokal — home/away legs, ET, penalty shootouts.

## Data

- `data/spieler.csv` — `name,position,staerke,nationalitaet`; `position` ∈ {T,A,M,S}; `staerke` stored as category string; `nationalitaet` ∈ {D, A}. Partial dataset (1000+ planned).
- `data/vereine.csv` — 18 Bundesliga + 20 2. Bundesliga clubs, 1983/84.
- `data/internationale_vereine.csv` — European clubs (for cup draws).
- `data/{manager_profiles,game_saves,mp_saves,avatars}/` — runtime user data (gitignored).
- `data/{admins,testers,global_chat}.json` — server state (gitignored).
- CSV format spec: `docs/csv_regeln_spielerpool.txt`.

## i18n

Trilingual UI: `i18n/de.json`, `en.json`, `fa.json` + per-language help pages (`help.{de,en,fa}.html`). Flag buttons in the frontend switch language. Separate translation-editor tool in `i18n-dev/`.

## Scripts & Tooling

- `scripts/generate_clubs.py`, `scripts/generate_players.py` — CSV generators.
- `backups/` — versioned release zips (`soccermaster_v*.zip`) + `backups/nightly/`.

## Publishing to GitHub

**The working directory is NOT a git repo.** Publishing goes through a second checkout under `github/` that mirrors `https://github.com/Amsteiner/soccermaster.git`.

Workflow:
1. Copy changed files from the working directory into `github/` (respecting `github/.gitignore`, which excludes `.env`, user data, logs, backups, local music).
2. In `github/`: `git add`, `git commit`, `git push`.

**⚠ Security note**: `github/.git/config` currently contains a GitHub Personal Access Token embedded in the remote URL. Prefer `git remote set-url origin https://github.com/Amsteiner/soccermaster.git` + credential helper, or switch to SSH. Rotate the token in GitHub if this config has ever left the machine.

**Mirror is often behind**: local `VERSION` regularly jumps several releases ahead of the pushed `origin/HEAD`. Before assuming "what's on GitHub" check `cd github && git log --oneline -1` and `git status`.

## Documentation

- `README.md` / `LIESMICH.txt` — quick-start (EN / DE)
- `docs/regelwerk_fussball_fegefeuer.txt` — complete game rules (DE)
- `docs/vereinsliste_fussball_fegefeuer.txt` — club list
- `docs/csv_regeln_spielerpool.txt` — CSV spec
- `docs/anleitung_neue_spieler.txt` — new-player guide

## Development Notes

- No automated tests; manual browser testing.
- Code and comments are in German; match that when extending.
- When touching game rules: edit the relevant `engine/` module → update `GameState` if schema changes → add/adjust WebSocket messages in `server/lobby.py` → update `index.html` screens → add translation keys to `i18n/*.json`.
