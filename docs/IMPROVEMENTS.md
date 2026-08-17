# Improvements & roadmap

A living list of where this project can get better. Good first issues are marked
🟢. Contributions welcome — see [CONTRIBUTING.md](../CONTRIBUTING.md).

## ✅ Fixed in the pre-release hardening pass

An automated code review + fixes landed these:

- **I2C ISR no longer does Serial/`analogRead`.** The firmware's `receiveEvent`/
  `requestEvent` run in interrupt context; they now only latch bytes and return
  values cached by the main loop (`sampleSensors()`), removing a real
  bus-stall / potential deadlock that hit on every capture.
- **Capture directory is bounded.** `timelapse.py` prunes `~/timelapse_images`
  to the newest `TIMELAPSE_MAX_STORED` (500) frames — no more silent SD fill.
- **Battery guard is recoverable + bench-safe.** Requires two consecutive
  out-of-range readings before shutdown, and `ENABLE_BATTERY_GUARD` defaults to
  `0` (a floating A0 was bricking fresh bench builds).
- **SMBus fd leak fixed** (`with smbus2.SMBus(1)`), and the uploader no longer
  crash-loops on a git error (`ensure_repo` retries inside the loop).
- **Explicit gate-off honored.** `0x0F` pin 2 → 0 now actually cuts RPi power
  (was defeated by the capture loop re-asserting the pin).
- **Truncated-frame guard** in the uploader (re-copies if the source grew),
  `volatile` on ISR-shared globals, `LED_PIN` pinMode, atomic time reads, and
  the Windows-only burn tool no longer crashes on import on Linux/macOS.

## P1 — still open

- [ ] **Use the watchdog.** `avr/wdt.h` is included but unused; a watchdog reset
      would recover the MCU from any hang in the field.
- [ ] **Wall-clock sync for the ping/quiet paths.** `timelapse.py` never sends
      `CMD_TIME`, so the firmware clock free-runs — fine today (those paths are
      inactive) but the quiet-window feature needs it. Send `0x00` periodically
      if you enable quiet hours. 🟢

## P2 — robustness / quality

- [ ] **Uploader backoff.** Add exponential backoff on repeated push failures
      instead of retrying every cycle during an outage.
- [ ] **Gallery API rate limit.** The Pages front-end polls the GitHub API
      (60 req/hr per anonymous IP). For many simultaneous viewers, publish a
      small `manifest.json` alongside the images and read that instead.
- [ ] **Timestamp overlay** burned into each frame (date/time, battery %).
- [ ] **`volatile` for multi-byte ISR state.** `updateTimeStruct` / `pingTime` /
      `ignoreTime*` are written in the I2C ISR and read in `loop()`; guard those
      reads with `ATOMIC_BLOCK` if you enable the ping/PIR paths.

## P3 — features

- [x] **Change detection** ([rpi/detect.py](../rpi/detect.py)) flags frames with a
      small, localized change ("likely insect") into `manifest.json`; the gallery
      has a dedicated insect view + a timelapse player. It's a motion proxy on the
      static scene — a **trained insect classifier** is the next step up.
- [ ] **Daily timelapse video** — an `ffmpeg` job stitching each day's frames.
- [ ] **On-device storage fallback** — keep capturing when WiFi is down.
- [ ] **Focus-stacking / macro optics** notes and mounts for sharp insect shots.
- [ ] **Power budget** — measure sleep current and per-shot Wh for the low-power
      trap mode.

## Portability (for forks)

- [x] `rpi/setup.sh` generates the systemd units + templates the front-end from
      `GH_USER`/`GH_REPO`/`INTERVAL` — a fork edits nothing by hand.
- [x] Camera tuning path is now `TIMELAPSE_TUNING` (env), with graceful fallback.
- [x] The uploader warns when `GH_OWNER` is unset instead of silently pushing to
      the author's repo.
- [ ] Collect the remaining fixed assumptions (`I2C addr 0x08`, bus `1`, camera
      rotation `180`) into one documented config block.

## Infrastructure

- [x] MIT license, `CONTRIBUTING.md`, and CI that compiles the firmware on every
      push/PR (`.github/workflows/firmware.yml`).
- [ ] Basic unit tests for the Python (filename parsing, rolling-window logic).
