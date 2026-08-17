"""Retry-burner: waits for the USB-serial adapter, then keeps attempting the
target bootloader burn (through the ArduinoISP master) until it succeeds.

WINDOWS-ONLY convenience jig (uses avrdude.exe paths + a console title API). On
Linux/macOS burn the bootloader directly with PlatformIO instead:
    pio run -e fuses_bootloader_arduinoisp -t bootloader

Meant to run in its own console window while you hold the MISO wires and the
reset clip on the target. Every state change is printed and logged to burn.log.

Burn recipe (harvested from `pio run -e fuses_bootloader_arduinoisp -t bootloader -v`):
  1) chip erase + unlock + fuses: lfuse=0xF7 hfuse=0xD7 efuse=0xFD  (ext 16 MHz, BOD 2.7V, EESAVE)
  2) flash urboot (autobaud, LED on B5) + lock 0xFF
"""
import datetime
import os
import re
import subprocess
import sys
import time

import serial.tools.list_ports

if os.name == "nt":
    import ctypes
    ctypes.windll.kernel32.SetConsoleTitleW("Target bootloader burner - hold the wires!")
    os.system("")            # enable ANSI colour escapes in cmd.exe
else:
    sys.exit("burn_until_success.py is Windows-only; on Linux/macOS run:\n"
             "  pio run -e fuses_bootloader_arduinoisp -t bootloader")

HOME = os.path.expanduser("~")
AVRDUDE = os.path.join(HOME, ".platformio", "packages", "tool-avrdude", "avrdude.exe")
CONF = os.path.join(HOME, ".platformio", "packages", "tool-avrdude", "avrdude.conf")
URBOOT = os.path.join(HOME, ".platformio", "packages", "framework-arduino-avr-minicore",
                      "bootloaders", "urboot", "atmega328p", "watchdog_1_s", "autobaud",
                      "uart0_rxd0_txd1", "led+b5", "urboot_atmega328p_pr_ee_ce.hex")
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "burn.log")

G, R, Y, C, X = "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[0m"


def ts():
    return datetime.datetime.now().strftime("%H:%M:%S")


def log(line):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"[{ts()}] {line}\n")
    except OSError:
        pass


def find_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if "CP210" in (p.description or "") or "Silicon Labs" in (p.description or ""):
            return p.device
    return ports[0].device if ports else None


def run_avrdude(args, timeout=120):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, "avrdude timed out"


def classify(out):
    low = out.lower()
    sigs = re.findall(r"signature = 0x([0-9a-f]{6})", low)
    if sigs:
        uniq = sorted(set(sigs))
        s = uniq[-1]
        if s == "1e950f":
            pass  # real signature; some other error text follows
        elif s == "000000" and len(uniq) == 1:
            return ("target reads 0x000000 every time - dead line: target unpowered "
                    "(PIR pins 1+2 wires) or MISO not touching at all")
        elif s == "ffffff" and len(uniq) == 1:
            return ("target reads 0xffffff - chip NOT held in reset (is the clip on the "
                    "pair that beeps to GND? move it to the other pair) or MISO floating")
        elif all(c in "0f" for c in "".join(uniq)):
            return (f"target reads {', '.join('0x' + u for u in uniq[:3])} - MISO garbage: "
                    "wobbly wire or WRONG LEG. Beep-check both boards: PIR pin 6 <-> leg 15, "
                    "PIR pin 5 <-> leg 17; MISO is the corner leg between them")
        else:
            return (f"target answered 0x{s} (expected 0x1e950f for ATmega328P) - "
                    "half-working contact, press steadier / check leg")
    if "not in sync" in low or "programmer is not responding" in low:
        return "programmer not answering - adapter ok? master powered? DTR wire unplugged?"
    if "0x000000" in low or "invalid device signature" in low or "yikes" in low:
        return "no target contact - press the MISO wires and reset clip harder"
    if "cannot open port" in low or "access is denied" in low or "cannot find the file" in low:
        return "port vanished or busy - reseat USB"
    if "verification" in low and ("mismatch" in low or "error" in low):
        return "contact glitch mid-write - hold steadier, retrying"
    tail = " | ".join(l for l in out.strip().splitlines() if l.strip())[-160:]
    return f"unexpected: ...{tail}"


def attempt(port):
    base = [AVRDUDE, "-p", "atmega328p", "-C", CONF, "-c", "stk500v1",
            f"-P{port}", "-b19200"]
    print(f"[{ts()}] {C}step 1/2: erase + fuses...{X}", flush=True)
    rc, out = run_avrdude(base + ["-e", "-Ulock:w:0xff:m", "-Uhfuse:w:0xd7:m",
                                  "-Ulfuse:w:0xf7:m", "-Uefuse:w:0xfd:m"])
    if rc != 0:
        return False, "fuses: " + classify(out)
    print(f"[{ts()}] {G}fuses OK{X} (lfuse F7, hfuse D7, efuse FD) - "
          f"{C}step 2/2: flashing urboot...{X}", flush=True)
    rc, out = run_avrdude(base + [f"-Uflash:w:{URBOOT}:i", "-Ulock:w:0xff:m"])
    if rc != 0:
        return False, "bootloader: " + classify(out)
    return True, "fuses + urboot bootloader written and verified"


def main():
    for f in (AVRDUDE, CONF, URBOOT):
        if not os.path.isfile(f):
            print(f"{R}missing: {f}{X}")
            input("press Enter to close...")
            return
    print(f"{C}=== Target bootloader burner ==={X}")
    print("Waiting for the USB-serial adapter, then burning until it works.")
    print("Hold both MISO wires (chip leg 16) and the target reset clip. Ctrl+C to stop.\n")
    log("burner started")
    n = 0
    boards = 0
    wait_start = time.time()
    while True:
        port = find_port()
        if not port:
            print(f"\r{Y}[--] no adapter ({int(time.time() - wait_start)} s)   {X}",
                  end="", flush=True)
            time.sleep(1)
            continue
        n += 1
        print(f"\n[{ts()}] adapter on {port} - {C}attempt #{n}{X}", flush=True)
        log(f"attempt {n} on {port}")
        ok, msg = attempt(port)
        if ok:
            boards += 1
            print(f"\n[{ts()}] {G}*** SUCCESS - board #{boards} done *** {msg}{X}")
            print(f"{G}Let go of the wires. This board now takes serial uploads on Boot1.{X}")
            log(f"SUCCESS board {boards} after {n} attempts")
            print("\a", end="", flush=True)
            print(f"\n{Y}Swap in the NEXT blank board, then press Enter to keep burning.")
            print(f"Close this window (or Ctrl+C) when you're done for the day.{X}")
            try:
                input()
            except EOFError:
                return
            n = 0
            wait_start = time.time()
            continue
        print(f"[{ts()}] {R}[XX]{X} {msg}", flush=True)
        log(f"fail {n}: {msg}")
        wait_start = time.time()
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped.")
