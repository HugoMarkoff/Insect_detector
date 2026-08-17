# Trap PCB V3.3 — hardware reference

Reverse-engineered from `Trap_PCB_V3.3.SchDoc` (net-traced programmatically) and
the assembled board. Note: the schematic in the project folder lags the fabbed
V3.3 in component *packages* (it draws a DIP ATmega328-PU and an LM2576 buck;
the board carries a TQFP-32 MEGA328P-AU and an RT7272B buck) — but the **net
topology matches the firmware pin usage exactly**, so the pinouts below are the
fabbed board's.

## Power

- `VIN` JST (2-pin): 2S battery, ~6.0–8.8 V. Reverse diodes 1N5406, big input electrolytic.
- Buck regulator → **5.1 V rail**: MCU (AVCC/AREF too — that's why the firmware
  uses `analogReference(EXTERNAL)` with 5.0 as reference constant), sensors, and
  the switched RPi supply.
- Battery sense: A0 through 30K/7K5 divider (matches `R1=30000, R2=7500` in firmware).
- RPi power is **high-side switched by an IRLZ44N** driven from `A2-GATE`
  (Arduino pin 16 / A2, `RELAY_PIN` in firmware). Two more IRLZ44Ns low-side
  switch the `Trig` and `IR` JST loads (gates on D4 / D5).

## MCU pin map (ATmega328P, Arduino numbering)

| Arduino | Net | Function |
|---|---|---|
| D0/D1 | RX / TX | Serial: debug + urclock upload (Boot1 header) |
| D2 | D2-PIR | PIR signal (INT0) |
| D3 | D3-MAG | Reed/magnet sensor (INT1) |
| D4 | D4-Trig | Low-side switch for `Trig` JST |
| D5 | D5-IR | Low-side switch for `IR` JST (IR flash board) |
| D10 | CS | Digipot chip-select (digipot sits on the PIR sensor board) |
| D11 (MOSI) | SI | Digipot data — also on PIR connector pin 6 |
| D12 (MISO) | MISO | **Chip leg only — no connector.** Needed for ISP |
| D13 (SCK) | SCK + D13-LED | Digipot clock, PIR pin 5, onboard LED (220R) |
| A0 | A0-BATT | Battery divider |
| A1 | A1-LDR | Photoresistor (`LDR` JST) — dusk detection for IR flash |
| A2 (D16) | A2-GATE | RPi power gate (firmware `RELAY_PIN`) |
| A4/A5 | SDA/SCL | I2C slave @ 0x08 to the RPi, level-shifted by 2N7000 pair |
| RESET | Reset | 10K pull-up, RST button to GND, 100 nF from Boot1 DTR |
| XTAL | Crystal1/2 | 16 MHz + 22 pF |

## Connectors

### Boot1 — programming/serial header (6-pin 2.5 mm female, bottom-right)

| Pin | Net |
|---|---|
| 1 | DTR (cap-coupled to RESET) |
| 2 | TX |
| 3 | RX |
| 4 | 5.1V |
| 5 | GND |
| 6 | NC |

### PIR Sensor (JST-PH 2.0 mm, 6-pin)

| Pin | Net | Note |
|---|---|---|
| 1 | 5.1V | |
| 2 | GND | |
| 3 | D2-PIR | Motion signal |
| 4 | CS | Digipot (sensitivity) on sensor board |
| 5 | SCK | **ISP tap point** |
| 6 | SI (=MOSI) | **ISP tap point** |

### Small JSTs

| Conn | Pin 1 | Pin 2 |
|---|---|---|
| VIN | Battery + (VIN net) | GND |
| Trig | 5.1V | switched drain (low-side FET, D4) |
| IR | 5.1V | switched drain (low-side FET, D5) |
| LDR | A1 divider | (photoresistor) |
| MAG | GND / 5V / SIG(D3) | 3-wire sensor |

### Pogo pins P1–P7 (press onto the RPi Zero 2 W header holes 1–6 + GND)

| Pogo | Net | RPi header pin |
|---|---|---|
| P4 | POGO-3V | 1 (3V3 — used only as level-shifter reference) |
| P1, P2 | 5.1V (switched) | 2, 4 (5V in) |
| P5 | POGO-SDA | 3 |
| P6 | POGO-SCL | 5 |
| P3, P7 | POGO-GND | 6, 9 |

The 2N7000 pair shifts SDA/SCL between the AVR's 5 V and the RPi's 3.3 V using
POGO-3V as the low-side pull-up rail — the classic bidirectional MOSFET shifter.

## I2C protocol (Arduino = slave @ 0x08, firmware v0.2)

**Writes** (`i2cset -y 1 0x08 CMD data…`):

| Cmd | Payload | Meaning |
|---|---|---|
| 0x00 | s, m, h | Sync wall clock |
| 0x04 | hours | Ping interval |
| 0x05 | h, m, s | Ping time |
| 0x06 | from h,m,s + to h,m,s | Quiet window (no captures inside it) |
| 0x08 | seconds | IR flash on (respects dusk value) |
| 0x09 | value/4 | Dusk threshold |
| 0x0B | 1–254 | PIR sensitivity (digipot) |
| 0x0C | minutes (254=default) | Capture interval, coarse |
| 0x0D | hi, lo (seconds, ≥15) | **Capture interval in seconds** |
| 0x0E | 0/1 | **Always-on: 1 = never cut RPi power on timeout** |
| 0x0F | pin, state | **Direct output write: 0=IR, 1=Trig, 2=RPi gate** |
| 0x15 | seconds (10–255) | RPi on-time budget per cycle (default 80) |

**Reads** (`i2cset -y 1 0x08 CMD` then `i2cget -y 1 0x08`, or smbus write+read):

| Cmd | Returns |
|---|---|
| 0x01 | Setup status (0 = fresh boot, wants full config) |
| 0x02 | Battery % |
| 0x03 | Trigger reason: 1 PIR, 2 ping, 3 reed, **4 timelapse** |
| 0x07 | (Request shutdown — Arduino cuts RPi power after this) |
| 0x0A | Image type (0 RGB, 1 IR) |
| 0x10 | **PIR input level** |
| 0x11 | **Reed/MAG input level** |
| 0x12 | **LDR reading /4 (0–255)** |
| 0x13 | **Battery voltage in decivolts (74 = 7.4 V)** |
| 0x14 | **Firmware version (2)** |

Cadence math: the capture schedule anchors at cycle start —
`next = cycle_start + interval` — so RPi boot/capture/shutdown time is absorbed
into the sleep and shot-to-shot spacing equals the configured interval exactly
(as long as interval > cycle time, i.e. ≥ ~60 s intervals are safe with a 45 s cycle).

Always-on: send `0x0E 0x01` at boot and simply never send `0x07` — the Arduino
freezes its timeout clock and leaves power up indefinitely. An explicit `0x07`
still shuts down even in always-on. Direct gate control (`0x0F 0x02 0x00`)
cuts your own power — that's the intended way for the RPi to hard-poweroff
outside the normal handshake (run `sudo poweroff` first, gate off ~10 s later
via a shutdown service, or just let cmd 0x07 handle it).
