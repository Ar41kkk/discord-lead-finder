#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/discord_listener"
VENV="$APP_DIR/.venv"

cd "$APP_DIR"

echo "[deploy] git pull..."
git fetch --all
git checkout main
git pull --ff-only

echo "[deploy] python deps..."
python3 -m venv "$VENV" >/dev/null 2>&1 || true
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install -r requirements.txt

echo "[deploy] restart services..."
sudo systemctl restart discord-dashboard.service || true
sudo systemctl restart discord-bot.service || true

echo "[deploy] done."
