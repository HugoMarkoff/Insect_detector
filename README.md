# 🐛 Insect Detector

[![Live gallery](https://img.shields.io/badge/live-gallery-4fce8d)](https://hugomarkoff.github.io/Insect_detector/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
![Platform](https://img.shields.io/badge/ATmega328P%20%2B%20Raspberry%20Pi-informational)

A wildlife-trap PCB repurposed into an **insect timelapse camera**, with a live
public gallery. An ATmega328P controller drives an infrared illuminator and a
Raspberry Pi + NoIR camera to take a frame every few minutes — no motion
trigger, just steady frames, day and night.

### ▶ Live gallery: **https://hugomarkoff.github.io/Insect_detector/**

Built on the **Animal Detect Trap PCB V3.3** — ATmega328P +
Raspberry Pi + IMX708 NoIR camera, reverse-engineered from the Altium project
and the original Animal Detect firmware.

---

## What's here

| Path | What it is |
|---|---|
| **[docs/FLASHING.md](docs/FLASHING.md)** | **How to flash a board** — the two-stage procedure (one-time bootloader burn over ISP, then serial uploads), with a photo of exactly which pins to hold |
| [docs/HARDWARE.md](docs/HARDWARE.md) | Board reference: every connector pinout, the MCU pin map, power architecture, and the full I2C command table |
| [docs/RPI.md](docs/RPI.md) | The Raspberry Pi side: timelapse capture, the live web gallery, and how it publishes to GitHub Pages |
| [firmware/](firmware/) | PlatformIO project — the ATmega328P timelapse firmware (v0.2) |
| [programmer/](programmer/) | Turn a working board into an ISP programmer (ArduinoISP) + a retry-until-it-works bootloader burner |
| [rpi/](rpi/) | Raspberry Pi scripts: `timelapse.py` (capture + gallery), `gh_uploader.py` (push to GitHub), systemd units |
| [web/](web/) | The GitHub Pages gallery front-end (`index.html`) |

---

## How it works

The board can run in two modes; the firmware supports both.

**1. WiFi timelapse (what's deployed here)** — the Raspberry Pi stays powered and
runs the show:

```
Raspberry Pi (always on, WiFi)                 ATmega328P (I2C slave @0x08)
  every 3 min:                                   ┌───────────────────────┐
  ├─ I2C: IR on  (0x0F) ───────────────────────► │ drives IR illuminator │
  ├─ capture frame (NoIR camera)                 │ reads battery / light │
  ├─ I2C: IR off (0x0F) ───────────────────────► │ level-shifted 5V↔3V3  │
  ├─ save + serve local gallery (:8080)          └───────────────────────┘
  └─ git push rolling window ─► GitHub ─► Pages ─► public gallery
```

**2. Battery trap (low-power)** — the ATmega328P is the scheduler: it power-gates
the Pi, wakes it on an interval (or PIR/reed), lets it capture, then cuts power
and sleeps. Set always-on (`0x0E`) to keep the Pi up, or let it cycle to save
battery. See the command table in [docs/HARDWARE.md](docs/HARDWARE.md).

> ⚡ **On battery the Pi's 5 V is gated by the Arduino**, so without an always-on
> command the firmware will power-cycle the Pi every ~80 s by design. [docs/RPI.md](docs/RPI.md)
> explains the always-on setup that keeps it running for the WiFi timelapse.

---

## Quick start

1. **Flash the board** → [docs/FLASHING.md](docs/FLASHING.md). A fresh chip needs a
   one-time bootloader burn over ISP; after that it takes normal serial uploads.
2. **Build & upload the firmware:**
   ```bash
   cd firmware
   pio run -e Upload_UART -t upload      # over the Boot1 serial header
   ```
3. **Set up the Raspberry Pi** — clone this repo on the Pi and run the installer:
   ```bash
   cd Insect_detector/rpi && GH_USER=<you> ./setup.sh
   ```
   It installs the capture loop, local gallery, and GitHub Pages publisher as
   systemd services, and walks you through the deploy key. Details in
   [docs/RPI.md](docs/RPI.md).
4. **Watch it** at your Pages URL, or locally at `http://<pi-ip>:8080/`.

Tuning (all in [firmware/src/main.cpp](firmware/src/main.cpp) or at runtime over I2C):

- Interval: `#define DEFAULT_INTERVAL_SECONDS`, or I2C `0x0D` (2 bytes of seconds).
- Quiet window: I2C `0x06` (from/to h,m,s) — skip captures at night.
- Bench testing without a battery: `#define ENABLE_BATTERY_GUARD 0` (a floating
  A0 reads garbage and would otherwise sleep the MCU forever).

---

## Hardware

Animal Detect Trap PCB V3.3 · ATmega328P @ 16 MHz · Raspberry Pi · IMX708 NoIR
camera · IR illuminator · 2S Li-ion. The board carries connectors for PIR, reed
(MAG), an IR/flash output, a spare trigger output, an LDR (dusk sensing), and a
`Boot1` serial header for programming. Full pinout in [docs/HARDWARE.md](docs/HARDWARE.md).

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Ideas and open
improvements are tracked in [docs/IMPROVEMENTS.md](docs/IMPROVEMENTS.md).

## License

[MIT](LICENSE) © 2026 Hugo Markoff.

## Credits

Derived from the Animal Detect trap platform. Firmware and the
RPi stack rewritten here for standalone insect timelapse use (no cloud backend —
images publish straight to GitHub Pages).
