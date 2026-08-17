# Raspberry Pi setup — capture, gallery & publishing

The Pi runs three moving parts, all as systemd services so they survive reboots
(important on battery, where the board can brown-out and restart):

1. **`timelapse.py`** — captures a frame every N seconds, drives the IR output on
   the Arduino around each shot, and serves a live local gallery on `:8080`.
2. **`gh_uploader.py`** — pushes the newest frames to GitHub as a rolling window.
3. **GitHub Pages** — serves the public gallery from the pushed images.

```
timelapse.py ──► ~/timelapse_images/*.jpg ──► gh_uploader.py ──► GitHub (images branch)
      │                                                                    │
   :8080 local gallery                          gh-pages branch (index.html) + GitHub Pages
                                                                           │
                                                          public gallery (auto-refreshes)
```

## Files

| File | Role |
|---|---|
| [rpi/timelapse.py](../rpi/timelapse.py) | Capture loop + local web gallery |
| [rpi/gh_uploader.py](../rpi/gh_uploader.py) | Rolling-window push to GitHub over an SSH deploy key |
| [rpi/insect-timelapse.service](../rpi/insect-timelapse.service) | systemd unit for capture (sets Arduino always-on on start) |
| [rpi/insect-uploader.service](../rpi/insect-uploader.service) | systemd unit for the GitHub push |
| [rpi/rc.local](../rpi/rc.local) | Neutralised boot script (replaces the old Firebase autostart) |
| [web/index.html](../web/index.html) | The Pages front-end (lists images via the GitHub API) |

## Capture (`timelapse.py`)

Configurable entirely by environment variables (set in the service unit):

| Env | Default | Meaning |
|---|---|---|
| `TIMELAPSE_INTERVAL` | `180` | Seconds between captures |
| `TIMELAPSE_IR_HOLD` | `0` | `1` = force the IR output on continuously (hardware test) |
| `TIMELAPSE_DIR` | `~/timelapse_images` | Where frames are written |

Each cycle: assert IR on (I2C `0x0F`), capture with `rpicam-still` (NoIR tuning),
IR off, save a timestamped JPEG, sleep to the next slot. It also sends the
Arduino **always-on** (`0x0E`) on startup so the board doesn't power-cycle the Pi.

Browse the raw feed locally at `http://<pi-ip>:8080/`.

## Publishing (`gh_uploader.py`)

Keeps only the last `GH_KEEP` (default 60) images and **force-pushes a single
squashed commit** to the `images` branch — so repo history never grows and the
Pages branch is never rebuilt. The page lists images via the GitHub API, so image
pushes don't trigger a Pages build (which would hit the ~10 builds/hour limit).

Auth is an **SSH deploy key** scoped to this one repo (`~/.ssh/insectcam_deploy`),
not a token. The repo must be **public** for anonymous visitors' browsers to read
the image list.

## First-time setup

```bash
# 1. Dependencies
sudo apt-get update && sudo apt-get install -y git python3-smbus2   # (smbus2 via pip if unavailable)

# 2. Deploy key (grant the Pi push access to just this repo)
ssh-keygen -t ed25519 -N '' -f ~/.ssh/insectcam_deploy -C insectcam-pi
cat ~/.ssh/insectcam_deploy.pub
#   → add at github.com/<you>/Insect_detector/settings/keys  (✅ Allow write access)

# 3. Copy scripts to ~/ , then install the services
sudo cp insect-timelapse.service insect-uploader.service /etc/systemd/system/
sudo cp rc.local /etc/rc.local && sudo chmod +x /etc/rc.local   # removes old Firebase autostart
sudo systemctl daemon-reload
sudo systemctl enable --now insect-timelapse.service insect-uploader.service

# 4. Gallery front-end → push web/index.html to a gh-pages branch, then enable
#    GitHub Pages (Settings → Pages → gh-pages / root). Repo must be public.
```

## Changing settings

```bash
# capture interval → edit TIMELAPSE_INTERVAL in the unit, then:
sudo systemctl daemon-reload && sudo systemctl restart insect-timelapse

# watch logs
journalctl -u insect-timelapse -f
journalctl -u insect-uploader -f
```

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Pi reboots every ~80 s on battery | Arduino gate timeout — the always-on command isn't reaching it. Confirm `insect-timelapse.service` runs on boot (it sends `0x0E`). |
| Gallery page loads but is empty | Repo is **private** — GitHub blocks anonymous API access. Make the repo public. |
| `git: command not found` | `sudo apt-get install -y git` |
| Uploader `push failed` | Deploy key missing write access, or not added to the repo. Re-check `ssh -i ~/.ssh/insectcam_deploy -T git@github.com`. |
| Camera busy / capture fails | A stray `rpicam-still` is holding the device: `pkill -f rpicam-still`. |

> The old Animal Detect Firebase flow (`camera.sh` + `main.py` via `/etc/rc.local`)
> is intentionally disabled here. A backup of the original rc.local is kept at
> `/etc/rc.local.firebase.bak` on the Pi.
