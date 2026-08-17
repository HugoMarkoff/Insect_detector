# Contributing

Thanks for your interest! This is a small hardware + firmware project — a wildlife
trap PCB reworked into an insect timelapse camera. Contributions of all kinds are
welcome: firmware fixes, RPi tooling, docs, enclosure designs, or just sharing a
build.

## Ways to help

- **Firmware** ([firmware/](firmware/)) — the ATmega328P timelapse logic.
- **Raspberry Pi tooling** ([rpi/](rpi/)) — capture, gallery, publishing.
- **Docs** ([docs/](docs/)) — the flashing guide especially benefits from more
  photos and gotchas from real boards.
- **Hardware** — enclosure/optics for macro insect shots, power/battery notes.

## Building the firmware

Uses [PlatformIO](https://platformio.org/) with the MiniCore core:

```bash
cd firmware
pio run                      # compile
pio run -e Upload_UART -t upload   # flash over the Boot1 serial header
```

A fresh chip needs a one-time bootloader burn first — see [docs/FLASHING.md](docs/FLASHING.md).

## Testing changes

- **Firmware:** it compiles clean and stays well under the ATmega328P's flash/RAM.
  If you change the capture/power state machine, bench-test with a serial monitor
  (`pio device monitor -b 9600`) and watch a few full cycles before trusting it on
  battery. Set `ENABLE_BATTERY_GUARD 0` when testing without a battery on VIN.
- **RPi scripts:** they're plain Python 3 (stdlib + `smbus2`). Prefer changes that
  keep the services restart-safe (they run under systemd with `Restart=always`).

## Style

- Match the surrounding code — the firmware favours small functions and explicit
  comments over cleverness; the Python favours stdlib and readability.
- Keep the I2C command table in [docs/HARDWARE.md](docs/HARDWARE.md) in sync with
  the `#define CMD_*` block in the firmware whenever you add or change a command.

## Pull requests

Small, focused PRs are easiest to review. Describe what you changed and how you
tested it (which board, which Pi, what you observed). If it touches the hardware
protocol, note backward compatibility with the existing I2C command numbers.

## A note on the origins

This derives from the Really a Robot / Animal Detect trap platform. The original
cloud (Firebase) backend has been removed — please don't reintroduce credentials
or private keys into the repo.
