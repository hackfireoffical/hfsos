#!/usr/bin/env bash
set -Eeuo pipefail
if command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]; then
  systemctl --no-pager --full status hackfire-gateway-bot.service hackfire-gateway-api.service || true
  printf '\nRecent bot logs:\n'
  journalctl -u hackfire-gateway-bot.service -n 40 --no-pager || true
elif command -v supervisorctl >/dev/null 2>&1; then
  supervisorctl status || true
  printf '\nRecent bot logs:\n'
  tail -n 40 /var/log/hackfire-gateway-bot.log 2>/dev/null || true
else
  echo "No supported service manager found."
fi
