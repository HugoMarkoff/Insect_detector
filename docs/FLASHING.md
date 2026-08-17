# Flashing the Trap PCB V3.3 (ATmega328P)

Reconstructed from the Altium schematic (`Trap_PCB_V3.3.SchDoc`) and the original
`platformio.ini` of the Animal Detect arduino-controller repo. This is the
procedure you half-remembered: **the DTR header is for everyday uploads, but a
factory-fresh ATmega328P is completely blank, so once per board you must burn
the bootloader over ISP — and this PCB has no ISP header, so two of the six ISP
signals have to be held directly against pins.**

## The two stages

| Stage | When | Interface | Command |
|---|---|---|---|
| 1. Burn fuses + urboot bootloader | **Once per fresh chip** | ISP (SPI) via USBasp + held wires | `pio run -e fuses_bootloader -t bootloader` |
| 2. Upload sketches | Every code change | `Boot1` 6-pin serial header (DTR auto-reset, urclock @ 115200) | `pio run -e Upload_UART -t upload` |

Fuse config burned in stage 1 (from the original project): external 16 MHz
crystal, BOD 2.7 V, EEPROM preserved, **urboot** bootloader on UART0 @ 115200.

---

## Stage 1 — bootloader over ISP (the "holding cables on pins" part)

ISP needs 6 signals: VCC, GND, RESET, SCK, MOSI, MISO. On this board they are
scattered — the PIR connector happens to carry the SPI bus (it drives the
digital potentiometer on the PIR sensor board), but **MISO reaches no connector
at all**:

| ISP signal | Where on the board | Notes |
|---|---|---|
| VCC (5V) | **PIR connector pin 1** (5.1V) | Only feed 5 V if **no battery** is on VIN. With a battery attached, leave programmer VCC disconnected (USBasp: remove the self-supply jumper). Boot1 pin 4 is the same net |
| GND | **PIR connector pin 2** | Boot1 pin 5 is the same net |
| SCK | **PIR connector pin 5** (`SCK`) | JST-PH 2.0 mm, 6-pin |
| MOSI | **PIR connector pin 6** (`SI`) | ditto |
| RESET | **Held/clipped: reset button leg** — the pair that is **not** continuous with GND (or TQFP pin 29) | Held wire #1. The Reset net has a 10K pull-up to 5.1V |
| MISO | **Held directly on the chip: TQFP-32 pin 16 (PB4)** | Held wire #2. No pad, no connector anywhere |

So the historical procedure was: a PH-6 pigtail (or dupont wires) into the PIR
connector for power + SCK + MOSI, plus **two hand-held wires** — MISO on the
chip leg and RESET on the button leg — for the ~20 s the burn takes.

### Finding MISO without counting pins

MISO sits at a package corner directly between the two legs you can identify by
continuity beep:

1. Beep from **PIR pin 6 (SI)** → finds TQFP pin 15 (MOSI), last-but-one leg on one side.
2. Beep from **PIR pin 5 (SCK)** → finds TQFP pin 17, first leg around the corner
   (it also connects to the onboard LED resistor — the LED lives on the SCK net).
3. **MISO = TQFP pin 16 = the single corner leg between those two.**

Hold a jumper-wire tip (or a pogo pin, or tack-solder a thin wire) on it for the
~20 s the burn takes. That plus the RESET clip is the "1–2 cables held on pins"
you remembered.

### USBasp 10-pin IDC pinout (for reference)

```
 1 MOSI   2 VCC
 3 NC     4 GND
 5 RESET  6 GND
 7 SCK    8 GND
 9 MISO  10 GND
```

### Run it

```bash
cd firmware
pio run -e fuses_bootloader -t bootloader
```

- Windows USBasp driver: install with **Zadig** → select "USBasp" → libusbK.
- The env already passes `-B8` (slow SPI clock) — required because a fresh chip
  runs at 1 MHz internal clock until the external-crystal fuse is set.
- If it can't sync: re-seat the MISO wire (most common), check RESET actually
  pulls to 0 V, try `-B32`.
- No USBasp? Use an Arduino Uno running the ArduinoISP example sketch and the
  `fuses_bootloader_arduinoisp` env in `platformio.ini` (same wiring, Uno pins
  10→RESET, 11→MOSI, 12→MISO, 13→SCK).

Success looks like avrdude writing lfuse/hfuse/efuse and flashing `urboot` with
verification OK. From this moment the chip has a bootloader forever (EESAVE +
serial uploads never erase it).

---

## Stage 2 — everyday uploads via `Boot1` (the DTR header)

The black 6-pin, 2.5 mm female header (bottom-right, next to the RST button) is
called `Boot1` in the schematic. Wire any 5 V USB-serial adapter
(FT232 / CP2102 / CH340 with a DTR pin):

| Boot1 pin | Net | USB-serial adapter |
|---|---|---|
| 1 | DTR | DTR (→ 100 nF cap → RESET auto-reset) |
| 2 | TX (board transmits) | RXD |
| 3 | RX (board receives) | TXD |
| 4 | 5.1V | 5V — only when not battery-powered |
| 5 | GND | GND |
| 6 | NC | — |

**Which physical end is pin 1?** Beep test once and mark the header with a
paint dot: the pin continuous with battery-minus / the electrolytic caps'
negative side is GND (pin 5); its direct neighbour is 5.1V (pin 4); the far end
is then DTR (pin 1). (Expect pin 1 to be the end nearest the `DTR` silk label.)

```bash
cd firmware
pio run -e Upload_UART -t upload      # urclock protocol @ 115200
pio device monitor -b 9600            # debug output
```

The original config hardcoded a macOS port (`/dev/cu.usbserial*`); the version
in this repo autodetects. If autodetection grabs the wrong port, uncomment
`upload_port = COMx` (see Device Manager → Ports).

If the upload retries without syncing: TX/RX swapped is the usual suspect; next
suspect is DTR not reaching reset — press the RST button just as avrdude starts
connecting as a manual fallback.

---

## Troubleshooting quick table

| Symptom | Cause → fix |
|---|---|
| ISP: `target doesn't answer` / `initialization failed` | MISO wire contact (hold steadier / tack-solder), RESET not held low, no power → check 5 V on Boot1 pin 4 |
| ISP: `cannot find USB device "USBasp"` | Driver → Zadig, libusbK |
| ISP works but chip later runs at wrong speed | Fuses not burned (you flashed only) → rerun the `-t bootloader` target, it sets fuses first |
| Serial upload: `urclock_recv(): programmer is not responding` | Wrong COM port, TX/RX swapped, DTR not wired, board unpowered, or stage 1 never happened |
| Serial monitor shows garbage | Baud mismatch — monitor is 9600, bootloader is 115200 (different things, both correct) |
| Board "dead" on the bench, no serial output | Battery guard put it to sleep (floating A0) → `ENABLE_BATTERY_GUARD 0` for bench work |
