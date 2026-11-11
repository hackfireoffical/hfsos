#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR="/opt/hackfire-gateway"
[[ "$(id -u)" -eq 0 ]] || { echo "Run with sudo/root."; exit 1; }
[[ -d "$APP_DIR/.git" ]] || { echo "App not installed at $APP_DIR"; exit 1; }
cd "$APP_DIR"
git pull --ff-only
.venv/bin/pip install -r requirements.txt
chown -R hackfire:hackfire "$APP_DIR"
systemctl restart hackfire-gateway-bot.service hackfire-gateway-api.service
systemctl --no-pager --full status hackfire-gateway-bot.service hackfire-gateway-api.service
