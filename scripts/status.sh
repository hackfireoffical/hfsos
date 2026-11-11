#!/usr/bin/env bash
set -Eeuo pipefail
systemctl --no-pager --full status hackfire-gateway-bot.service hackfire-gateway-api.service || true
printf '\nRecent bot logs:\n'
journalctl -u hackfire-gateway-bot.service -n 40 --no-pager || true
