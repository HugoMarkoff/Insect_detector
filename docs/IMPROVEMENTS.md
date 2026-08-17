# Improvements & roadmap

A living list of where this project can get better, roughly prioritized. Good
first issues are marked 🟢. Contributions welcome — see [CONTRIBUTING.md](../CONTRIBUTING.md).

## P1 — correctness / reliability (do these first)

- [ ] **Prune the capture directory.** `timelapse.py` writes to `~/timelapse_images`
      forever and never deletes — at 3-min intervals (~86 MB/day) it will fill the
      SD card over weeks. The GitHub uploader keeps a rolling window in its *own*
      working copy, but the source folder is unbounded. Fix: cap `~/timelapse_images`
      to the last N frames (or age them out) in the capture loop. 🟢
- [ ] **Get sensor reads out of the I2C interrupt.** The Arduino's `requestEvent`
      (I2C `onRequest`, runs in interrupt context) calls `analogRead()` / `digitalRead()`,
      and `receiveEvent` does `Serial.print()`. Blocking work in an ISR can stall
      the bus and drop bytes. Fix: sample sensors in the main loop into `volatile`
      cache variables and have the I2C callbacks only read those; move Serial logging
      out of the callbacks.
- [ ] **Recoverable battery guard.** On an out-of-range reading the firmware does
      `LowPower.powerDown(SLEEP_FOREVER)`. A single bad ADC sample then bricks the
      node until a manual reset. Fix: sleep for a bounded interval and re-measure.
- [ ] **Use the watchdog.** `avr/wdt.h` is included but unused. A watchdog reset
      would recover the MCU from any hang in the field.

## P2 — robustness / quality

- [ ] **Two ways to set the interval.** Legacy `CMD_SET_TIME_INTERVAL` (minutes)
      and new `CMD_SET_TIMELAPSE_SECONDS` (seconds) both exist. Keep both for
      compatibility but document clearly which the RPi should use.
- [ ] **Uploader backoff.** `gh_uploader.py` retries every cycle on failure; add
      exponential backoff on repeated push errors to avoid hammering on an outage.
- [ ] **Gallery API rate limit.** The Pages front-end polls the GitHub API
      (60 req/hr per anonymous IP). Many simultaneous viewers on one NAT could hit
      it. Mitigate with a longer poll, or publish a small `manifest.json` alongside
      the images and read that instead.
- [ ] **Timestamp overlay** burned into each frame (date/time, maybe battery %),
      so images are self-describing.
- [ ] **Name the magic numbers** in the firmware (61 Timer2 overflows/sec, 80 000 ms
      on-time, retry counts) as named constants.

## P3 — features

- [ ] **Daily timelapse video** — an `ffmpeg` job that stitches each day's frames
      into an MP4 and links it from the gallery.
- [ ] **Software motion/change detection** to keep only frames where something
      moved (huge storage/bandwidth win for a bug trap).
- [ ] **On-device storage fallback** — keep capturing to USB/SD when WiFi is down,
      backfill on reconnect.
- [ ] **Focus-stacking / macro optics** notes and mounts for sharp insect shots.
- [ ] **Power budget** — measure sleep current and per-shot Wh; publish a battery
      sizing table for the low-power trap mode.

## Portability (for forks)

- [x] Setup no longer hardcodes the Pi user / repo — `rpi/setup.sh` generates the
      systemd units from `GH_USER` / `GH_REPO` / `INTERVAL` variables.
- [ ] **Template the front-end too.** `web/index.html` still hardcodes
      `OWNER`/`REPO` at the top; have `setup.sh` substitute these so a fork needs
      to touch nothing by hand. 🟢
- [ ] Note the fixed assumptions (`I2C addr 0x08`, bus `1`, camera rotation `180`)
      in one place so they're easy to change.

## Infrastructure

- [x] MIT license, contributing guide.
- [ ] **CI: compile the firmware on every push/PR** (PlatformIO in GitHub Actions)
      so contributions are validated automatically. *(workflow added — see
      `.github/workflows/firmware.yml`.)*
- [ ] Basic tests for the Python (parse/rolling-window logic).

---

*Code-review findings from an automated pass are folded into P1/P2 above.*
