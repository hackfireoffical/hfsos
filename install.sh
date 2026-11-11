#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="https://github.com/hackfireoffical/hfsos.git"
APP_DIR="/opt/hackfire-gateway"
SERVICE_USER="hackfire"
PYTHON_BIN="python3"

log() { printf '\n[HackFire Gateway] %s\n' "$*"; }
fail() { printf '\n[ERROR] %s\n' "$*" >&2; exit 1; }

[[ "$(id -u)" -eq 0 ]] || fail "Run as root: sudo bash install.sh"
command -v apt-get >/dev/null 2>&1 || fail "This installer supports Ubuntu/Debian with apt."

log "Installing system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y git curl ca-certificates python3 python3-venv python3-pip build-essential supervisor

if [[ -d "$APP_DIR/.git" ]]; then
  log "Updating existing checkout..."
  git -C "$APP_DIR" pull --ff-only
else
  if [[ -e "$APP_DIR" ]]; then
    fail "$APP_DIR exists but is not a Git checkout. Move it aside before installing."
  fi
  log "Cloning HackFire Gateway..."
  git clone "$REPO_URL" "$APP_DIR"
fi

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

cd "$APP_DIR"
mkdir -p data/downloads
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --upgrade pip wheel
.venv/bin/pip install -r requirements.txt

if [[ ! -f .env ]]; then
  install -m 600 /dev/null .env
  {
    printf 'APP_NAME="HackFire Gateway"\n'
    printf 'APP_ENV=production\n'
    printf 'LOG_LEVEL=INFO\n'
    printf 'GITHUB_TOKEN=\nYOUTUBE_API_KEY=\nCURSEFORGE_API_KEY=\n'
    printf 'DOWNLOAD_DIR=%s/data/downloads\n' "$APP_DIR"
    printf 'MAX_CONCURRENT_DOWNLOADS=2\nMAX_DOWNLOAD_SIZE_MB=512\nDOWNLOAD_ORPHAN_MAX_AGE_SECONDS=3600\nDOWNLOAD_COOLDOWN_SECONDS=15\nMAX_ACTIVE_HANDLERS=8\n'
  } > .env
fi

if ! grep -Eq '^RUBIKA_BOT_TOKEN=.+$' .env; then
  log "Configure the Rubika bot token (input is hidden)."
  read -r -s -p "Rubika bot token: " RUBIKA_TOKEN
  printf '\n'
  [[ -n "$RUBIKA_TOKEN" ]] || fail "A Rubika token is required."
  sed -i '/^RUBIKA_BOT_TOKEN=/d' .env
  printf 'RUBIKA_BOT_TOKEN=%s\n' "$RUBIKA_TOKEN" >> .env
  unset RUBIKA_TOKEN
fi
chmod 600 .env

chown -R "$SERVICE_USER":"$SERVICE_USER" "$APP_DIR"
chown root:"$SERVICE_USER" .env
chmod 640 .env

if command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]; then
  cat > /etc/systemd/system/hackfire-gateway-bot.service <<UNIT
[Unit]
Description=HackFire Gateway Rubika Bot
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/python -m app.bot
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
Environment=PYTHONDONTWRITEBYTECODE=1
ReadWritePaths=$APP_DIR/data

[Install]
WantedBy=multi-user.target
UNIT

  cat > /etc/systemd/system/hackfire-gateway-api.service <<UNIT
[Unit]
Description=HackFire Gateway Local API
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
Environment=HOST=127.0.0.1
Environment=PORT=8000
ExecStart=$APP_DIR/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
Environment=PYTHONDONTWRITEBYTECODE=1
ReadWritePaths=$APP_DIR/data

[Install]
WantedBy=multi-user.target
UNIT

  systemctl daemon-reload
  systemctl enable --now hackfire-gateway-bot.service
  systemctl enable --now hackfire-gateway-api.service
  log "Services installed with systemd."
  printf '\nBot status: systemctl status hackfire-gateway-bot\n'
  printf 'API status: systemctl status hackfire-gateway-api\n'
  printf 'Bot logs:   journalctl -u hackfire-gateway-bot -f\n'
else
  log "systemd is unavailable; configuring Supervisor instead..."
  mkdir -p /etc/supervisor/conf.d
  cat > /etc/supervisor/conf.d/hackfire-gateway.conf <<UNIT
[program:hackfire-gateway-bot]
command=/bin/bash -c 'set -a; . $APP_DIR/.env; exec $APP_DIR/.venv/bin/python -m app.bot'
directory=$APP_DIR
user=$SERVICE_USER
environment=HOME="$APP_DIR",PYTHONDONTWRITEBYTECODE="1"
autostart=true
autorestart=true
startsecs=5
stopasgroup=true
killasgroup=true
redirect_stderr=true
stdout_logfile=/var/log/hackfire-gateway-bot.log

[program:hackfire-gateway-api]
command=/bin/bash -c 'set -a; . $APP_DIR/.env; exec $APP_DIR/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000'
directory=$APP_DIR
user=$SERVICE_USER
environment=HOME="$APP_DIR",HOST="127.0.0.1",PORT="8000",PYTHONDONTWRITEBYTECODE="1"
autostart=true
autorestart=true
startsecs=5
stopasgroup=true
killasgroup=true
redirect_stderr=true
stdout_logfile=/var/log/hackfire-gateway-api.log
UNIT
  if ! supervisorctl pid >/dev/null 2>&1; then
    supervisord -c /etc/supervisor/supervisord.conf
  fi
  supervisorctl reread
  supervisorctl update
  log "Services installed with Supervisor."
  printf '\nService status: supervisorctl status\n'
  printf 'Bot logs:       tail -f /var/log/hackfire-gateway-bot.log\n'
fi

printf 'API health: curl http://127.0.0.1:8000/health\n'
printf 'App path:   %s\n' "$APP_DIR"
printf '\nKeep port 8000 private. Do not expose the API publicly without authentication.\n'
