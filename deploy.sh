#!/usr/bin/env bash
# Deploy the project to the Raspberry Pi and restart the systemd service.
#
#   ./deploy.sh            # rsync + restart + show version and last log lines
#   ./deploy.sh --install  # also (re)install the systemd unit and enable it
#
# PI_HOST overrides the target (default cockemc@192.168.1.54).
set -euo pipefail

PI_HOST="${PI_HOST:-cockemc@192.168.1.54}"
REMOTE_DIR="tidal-voice-assistant"
SERVICE="tidal-assistant"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "Deploying v$(cat "$HERE/VERSION") to $PI_HOST:~/$REMOTE_DIR"
rsync -a --delete \
  --exclude venv --exclude 'vosk-model*' --exclude '.env' \
  --exclude tidal_session.json --exclude lastfm_session.json \
  --exclude logs --exclude __pycache__ --exclude .git --exclude '.claude' \
  "$HERE/" "$PI_HOST:~/$REMOTE_DIR/"

ssh "$PI_HOST" "cd ~/$REMOTE_DIR && ./venv/bin/pip install -q -r requirements.txt"

if [[ "${1:-}" == "--install" ]]; then
  ssh "$PI_HOST" "sudo cp ~/$REMOTE_DIR/$SERVICE.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable $SERVICE"
fi

ssh "$PI_HOST" "sudo systemctl restart $SERVICE; sleep 20; systemctl --no-pager --lines=0 status $SERVICE | head -3; tail -n 5 ~/$REMOTE_DIR/logs/assistant.log"
