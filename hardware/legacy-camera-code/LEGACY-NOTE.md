# Legacy camera code (archived)

Snapshot of the original Animal Detect camera repo, archived here from
`bitbucket.org/hugo_markoff/rmd_rar` (last commit: `73fb3eb` — "Reduced time
and improved sensitivity code").

- `ArduinoCode/TrapCode/` — PlatformIO project for the ATmega328P on the trap
  PCB (the ancestor of the firmware on `main`'s `firmware/`).
- `RPiCode/` — the Raspberry Pi side: capture (`main.py`, `camera.sh`),
  Firebase upload, setup scripts.

**Credentials removed:** the original repo contained a Firebase service
account (`trapapp-…-adminsdk-….json`). It has been stripped from this
archive. The code still references it by filename — to run the Firebase
parts, supply your **own** service-account JSON at the path the scripts
expect. Never commit that file.

Archived for preservation; the maintained insect-camera code lives on the
`main` branch (`firmware/`, `rpi/`).
