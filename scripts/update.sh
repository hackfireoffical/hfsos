#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR="/opt/hackfire-gateway"
[[ "$(id -u)" -eq 0 ]] || { echo "Run with sudo/root."; exit 1; }
[[ -d "$APP_DIR/.git" ]] || { echo "App not installed at $APP_DIR"; exit 1; }
cd "$APP_DIR"
git pull --ff-only
.venv/bin/pip install -r requirements.txt
bash -n install.sh scripts/*.sh
.venv/bin/python -m compileall -q app tests
.venv/bin/python -m unittest discover -s tests -v
chown -R hackfire:hackfire "$APP_DIR"
chown root:hackfire "$APP_DIR/.env"
chmod 640 "$APP_DIR/.env"
if command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]; then
  systemctl restart hackfire-gateway-bot.service hackfire-gateway-api.service
  systemctl --no-pager --full status hackfire-gateway-bot.service hackfire-gateway-api.service
elif command -v supervisorctl >/dev/null 2>&1; then
  supervisorctl restart hackfire-gateway-bot hackfire-gateway-api
  supervisorctl status
else
  echo "No supported service manager found. Re-run install.sh to configure Supervisor." >&2
  exit 1
fi
