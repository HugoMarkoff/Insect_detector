#!/usr/bin/env bash
# Insect Detector - Raspberry Pi setup.
#
# Installs the timelapse capture loop, the local web gallery, and the GitHub
# Pages publisher as systemd services. Run it on the Pi from a clone of this repo:
#
#     git clone https://github.com/<you>/Insect_detector.git
#     cd Insect_detector/rpi && ./setup.sh
#
# Everything is driven by the variables below or matching env vars, so a fork
# only needs to change GH_USER / GH_REPO (or export them before running).
set -euo pipefail

# ---- config (override via env, e.g. GH_USER=me ./setup.sh) ----
GH_USER="${GH_USER:-HugoMarkoff}"       # your GitHub username
GH_REPO="${GH_REPO:-Insect_detector}"   # the repo to publish into (must be public)
INTERVAL="${INTERVAL:-180}"             # seconds between captures
KEEP="${KEEP:-60}"                      # images kept in the rolling window
UPLOAD_INTERVAL="${UPLOAD_INTERVAL:-90}" # seconds between GitHub pushes

PI_USER="$(id -un)"
HOME_DIR="$HOME"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
KEY="$HOME_DIR/.ssh/insectcam_deploy"
say(){ printf '\n\033[1;32m==>\033[0m %s\n' "$*"; }

say "Config:  user=$PI_USER  repo=$GH_USER/$GH_REPO  interval=${INTERVAL}s  keep=$KEEP"

# ---- 1. dependencies ----
say "Installing dependencies (git, smbus2)…"
sudo apt-get update -qq
sudo apt-get install -y -qq git python3 python3-pip
python3 -c 'import smbus2' 2>/dev/null || sudo apt-get install -y -qq python3-smbus2 \
    || pip3 install --break-system-packages smbus2
command -v rpicam-still >/dev/null || command -v libcamera-still >/dev/null \
    || { echo "WARNING: no rpicam-still/libcamera-still found - install the camera stack"; }

# ---- 2. scripts into place ----
say "Copying scripts to $HOME_DIR…"
cp "$SCRIPT_DIR/timelapse.py" "$SCRIPT_DIR/gh_uploader.py" "$HOME_DIR/"

# ---- 3. deploy key ----
if [ ! -f "$KEY" ]; then
    say "Generating an SSH deploy key…"
    mkdir -p "$HOME_DIR/.ssh"; chmod 700 "$HOME_DIR/.ssh"
    ssh-keygen -t ed25519 -N '' -f "$KEY" -C insectcam-pi -q
fi
ssh-keygen -F github.com >/dev/null 2>&1 || ssh-keyscan -t ed25519 github.com >> "$HOME_DIR/.ssh/known_hosts" 2>/dev/null
echo
echo "  Add this PUBLIC key as a deploy key WITH WRITE ACCESS at:"
echo "    https://github.com/$GH_USER/$GH_REPO/settings/keys/new"
echo
echo "    $(cat "$KEY.pub")"
echo
read -rp "  Press Enter once you've added it… "

SSH_CMD="ssh -i $KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
if ! $SSH_CMD -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    echo "ERROR: deploy key not working yet. Add it (with write access) and re-run."; exit 1
fi
say "Deploy key OK."

# ---- 4. publish the gallery front-end to gh-pages ----
say "Publishing web/index.html to the gh-pages branch…"
GP="$(mktemp -d)"; cp "$REPO_DIR/web/index.html" "$GP/index.html"
git -C "$GP" init -q
git -C "$GP" checkout -q --orphan gh-pages
git -C "$GP" -c user.email=cam@insect-detector.local -c user.name=insect-cam add index.html
git -C "$GP" -c user.email=cam@insect-detector.local -c user.name=insect-cam commit -q -m "gallery"
GIT_SSH_COMMAND="$SSH_CMD" git -C "$GP" push -f "git@github.com:$GH_USER/$GH_REPO.git" HEAD:gh-pages
rm -rf "$GP"

# ---- 5. systemd services (generated from the config above) ----
say "Installing systemd services…"
sudo tee /etc/systemd/system/insect-timelapse.service >/dev/null <<UNIT
[Unit]
Description=Insect Detector timelapse capture + live web gallery
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=$PI_USER
Environment=TIMELAPSE_DIR=$HOME_DIR/timelapse_images
Environment=TIMELAPSE_INTERVAL=$INTERVAL
ExecStartPre=-/usr/bin/python3 -c "import smbus2; b=smbus2.SMBus(1); b.write_i2c_block_data(0x08,0x0E,[1]); b.close()"
ExecStart=/usr/bin/python3 $HOME_DIR/timelapse.py
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
UNIT

sudo tee /etc/systemd/system/insect-uploader.service >/dev/null <<UNIT
[Unit]
Description=Insect Detector - push timelapse frames to GitHub Pages
After=network-online.target insect-timelapse.service
Wants=network-online.target
[Service]
Type=simple
User=$PI_USER
Environment=TIMELAPSE_DIR=$HOME_DIR/timelapse_images
Environment=GH_OWNER=$GH_USER
Environment=GH_REPO=$GH_REPO
Environment=GH_BRANCH=images
Environment=GH_KEEP=$KEEP
Environment=GH_UPLOAD_INTERVAL=$UPLOAD_INTERVAL
ExecStart=/usr/bin/python3 $HOME_DIR/gh_uploader.py
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target
UNIT

# ---- 6. remove the old Firebase autostart if present ----
if grep -q "main.py\|camera.sh" /etc/rc.local 2>/dev/null; then
    say "Disabling the old Firebase autostart in /etc/rc.local (backup: /etc/rc.local.firebase.bak)…"
    sudo cp -n /etc/rc.local /etc/rc.local.firebase.bak
    printf '#!/bin/bash\n# insect-timelapse services handle startup now.\nexit 0\n' | sudo tee /etc/rc.local >/dev/null
    sudo chmod +x /etc/rc.local
fi

# ---- 7. go ----
say "Enabling and starting services…"
sudo systemctl daemon-reload
sudo systemctl enable --now insect-timelapse.service insect-uploader.service

cat <<DONE

  Done. Two things left, in the GitHub web UI:
    1. Make the repo PUBLIC   → Settings → Danger Zone → Change visibility.
       (Required so visitors' browsers can read the image list.)
    2. Enable Pages           → Settings → Pages → Branch: gh-pages / root → Save.

  Local feed now:   http://$(hostname -I | awk '{print $1}'):8080/
  Public gallery:   https://$GH_USER.github.io/$GH_REPO/

  Logs:  journalctl -u insect-timelapse -f
         journalctl -u insect-uploader -f
DONE
