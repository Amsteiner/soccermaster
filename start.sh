#!/bin/bash

# Soccermaster Startup Script

# Wechsle in das Verzeichnis, in dem dieses Skript liegt
cd "$(dirname "$0")"

# Erstellt venv, installiert Dependencies, startet Server

set -e

echo "🚀 Soccermaster Server Starter"
echo "===================================="

# Prüfe ob venv existiert
if [ ! -d "venv" ]; then
    echo "📦 Erstelle Virtual Environment..."
    python3 -m venv venv
fi

echo "✓ Virtual Environment aktiviert"
source venv/bin/activate

echo "📥 Installiere Dependencies..."
pip install -q --break-system-packages -r requirements.txt

set +e  # Ab hier kein automatisches Exit bei Fehler

clear
echo "🚀 Soccermaster Server Starter"
echo "===================================="
echo ""
echo "✅ Alles ready!"
echo "   r = Neustart    q = Beenden"
echo ""

SERVER_PID=""

kill_old_server() {
    # ss/lsof zuverlässiger als fuser (funktioniert auch ohne root)
    for port in 8080 8765; do
        pids=$(ss -tlnp "sport = :$port" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u)
        if [ -n "$pids" ]; then
            echo "⚠ Port $port belegt – beende Altprozess ($pids)..."
            kill -TERM $pids 2>/dev/null
            sleep 1
            kill -KILL $pids 2>/dev/null
        fi
    done
}

start_server() {
    kill_old_server
    python3 main.py &
    SERVER_PID=$!
}

stop_server() {
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill -INT "$SERVER_PID"      # wie Ctrl+C → löst Save aus
        wait "$SERVER_PID" 2>/dev/null
    fi
}

do_restart() {
    echo "💾 Speichere & starte neu..."
    # Python-Prozess über Neustart informieren (setzt _neustart-Flag)
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill -USR1 "$SERVER_PID"
    fi
    stop_server
    echo ""
    echo "════════════════ NEUSTART ════════════════"
    echo ""
    start_server
    echo "   r = Neustart    q = Beenden"
}

trap 'stop_server; exit 0' INT TERM
trap 'do_restart' USR1

start_server

while true; do
    read -r -s -n1 key
    if [ "$key" = "r" ]; then
        do_restart
    elif [ "$key" = "q" ]; then
        echo "👋 Beende Server..."
        stop_server
        exit 0
    fi
done
