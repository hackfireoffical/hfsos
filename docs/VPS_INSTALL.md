# Ubuntu VPS installation

The supported installer targets Ubuntu 24.04 (and compatible Ubuntu/Debian releases) with systemd.

## Install

From an existing checkout:

```bash
sudo bash install.sh
```

Or download and run the installer directly:

```bash
curl -fsSL https://raw.githubusercontent.com/hackfireoffical/hfsos/main/install.sh -o install.sh
sudo bash install.sh
rm -f install.sh
```

The installer:
- Installs Git and Python tooling.
- Clones or fast-forward updates this repository under `/opt/hackfire-gateway`.
- Creates a restricted `hackfire` system account.
- Creates a Python virtual environment and installs requirements.
- Prompts for the Rubika token without echoing it.
- Writes the token to a root-created, restricted root-owned `.env` file (readable only by the service group).
- Installs and enables separate systemd services for the Rubika bot and localhost-only API.

The installer never asks you to paste your token into a command or commit it to Git.

## Check services

```bash
systemctl status hackfire-gateway-bot
systemctl status hackfire-gateway-api
journalctl -u hackfire-gateway-bot -f
curl http://127.0.0.1:8000/health
```

## Update

```bash
sudo bash /opt/hackfire-gateway/scripts/update.sh
```

## Configure optional provider keys

Edit the local secret file:

```bash
sudo nano /opt/hackfire-gateway/.env
```

Optional values include `GITHUB_TOKEN`, `YOUTUBE_API_KEY`, and `CURSEFORGE_API_KEY`. After changes:

```bash
sudo systemctl restart hackfire-gateway-bot
sudo systemctl restart hackfire-gateway-api
```

## Security notes

- Keep port 8000 bound to 127.0.0.1. The API does not yet have user authentication.
- Never publish or commit `.env`.
- Search and download commands are available for GitHub releases, Modrinth versions, and CurseForge files (the latter requires an approved API key).
- YouTube currently provides search metadata and watch links only; it does not download media.
- Verify the bot can reach Rubika from the VPS before relying on it during a connectivity disruption.
