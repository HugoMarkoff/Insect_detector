# Open hardware — Animal Detect camera-trap family 🔓

The PCB designs and production 3D-print files behind the Really a Robot /
Animal Detect camera trap — the same hardware the [insect detector](../README.md)
is built from. Released open source under the repository's MIT license
(if you build or remix, a mention is appreciated).

## PCBs (Altium)

| Board | Newest ★ | Folder | What's inside |
|---|---|---|---|
| **IR array** (batwing illuminator) | v6.1 | `pcb/ir-array/` | v5 complete project (PrjPcb + SchDoc — the only schematic), v6 + **v6.1 ★** PcbDocs |
| **Main trap PCB** (ATmega328P host for a Pi Zero) | SMT2024 SMD-v3 | `pcb/trap-main/` | **SMD-v3 ★** complete project, early apr02 respin, v3.3 project + `full-archive-with-history.zip` (10 design snapshots V2→V3.2 **including manufacturing gerbers**) + `v3-docs/Trap_PCB_V3.pdf` |
| **PIR module** | v1.0 | `pcb/pir/` | PcbDoc + SchDoc |

Key dimensions, parsed straight from the PcbDocs:

| Board | Size | Mount holes |
|---|---|---|
| IR array v6.1 | 81.0 × 98.4 mm batwing, camera slot 37.2 wide | 2 × Ø3.0 on the centreline at (0,−6.5), (0,−29.1) |
| Main trap SMT2024 | 82.0 × 40.0 mm | 4 × Ø2.8 in a 58 × 23 pattern (= Pi Zero pattern — the Pi stacks on) |
| PIR v1.0 | 40.2 × 20.5 mm | 3 × Ø2.2 triangle: (−15, ±10) and (+15, 0) |

The magnet input is a bare reed switch on the trap PCB's MAG line — it never
had its own board.

## Camera-trap 3D parts (`cad/`)

The complete production print set (3MF), 30 files:

| Group | Parts |
|---|---|
| Enclosure | `Front-shell`, `Back-shell`, `Cam-Insert`, `IR-Insert-Folding`, `Bracket` |
| Battery | `Battery_Top`, `Battery_Buttom`, `Battery-Knob`, `BattPCB-Bracket` |
| Charger | `Charger-Top`, `Charger-buttom`, `Charger-IconInlay` |
| PIR | `PIRbracket`, `PIR-Funnel` (+ `TEST/New-PIR/` variants) |
| Antenna | `AntennaSafe`, `AntennaSafeInsert`, `AntennaSafeTip` |
| Mounting | `TreeBracket`, `Tree-Knob`, `Shade`, `Shade - Big` |
| `TEST/` | print-tuning coupons (`M3-test`, `PET-G_Test`, shell/PIR variants) |

`Cam-Insert` is worth a look even if you build nothing else: it encodes the
camera ↔ pogo-interface-board stack (camera in a 1.2 mm pocket, second board
7.4 mm seat-to-seat above it) that the insect detector's ladybug belly reuses.

## Bill of materials & docs (`docs/`, `pcb/trap-main/v3-docs/`)

| File | What |
|---|---|
| `docs/AD_BOM_list.xlsx` | AD camera bill of materials |
| `docs/Trap_v4_BOM.xls` | Trap v4 bill of materials |
| `pcb/trap-main/v3-docs/Trap_PCB_V3.pdf` | Trap PCB V3 documentation |
| `pcb/trap-main/v3-docs/Schematic_V3.jpg` | Trap V3 schematic (image) |
| `pcb/trap-main/v3-docs/i2c-Pogo-diagram-V2.jpg` | The I2C **pogo-pin interface** diagram |

## Legacy firmware & code

- `firmware-legacy/` — the original Arduino bring-up sketches: battery
  capacity (Li-Ion + NiMH), I2C tests, latch/battery-status tests.
- `legacy-camera-code/` — full snapshot of the original Bitbucket repo
  (`rmd_rar`): trap-PCB PlatformIO firmware + Raspberry Pi capture/upload
  scripts. **All credentials stripped** — see `LEGACY-NOTE.md` inside.

## Related

- The **ladybug insect-camera enclosure** (parametric FreeCAD) lives on the
  `main` branch under [`enclosure/`](../../tree/main/enclosure).
- Firmware for the trap PCB + Raspberry Pi timelapse/upload scripts:
  [`firmware/`](../../tree/main/firmware) and [`rpi/`](../../tree/main/rpi)
  on `main`.

## Notes

- Altium files are binary; folders are organised **one version per folder**
  so history stays browsable without Altium.
- No keys, credentials, or customer data are contained in any of these files.
