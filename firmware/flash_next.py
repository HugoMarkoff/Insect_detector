"""Batch firmware flasher: waits for the USB-serial adapter, uploads the
timelapse firmware over the urclock bootloader, then waits for Enter before
the next board. Wire per board: Boot1 GND, TX, RX, DTR (+5V if no battery).
"""
import ctypes
import datetime
import os
import subprocess
import sys
import time

import serial.tools.list_ports

ctypes.windll.kernel32.SetConsoleTitleW("Firmware flasher - one board at a time")
os.system("")

FIRMWARE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(FIRMWARE_DIR, "flash.log")
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
    return ports[0].device if ports else None


def flash(port):
    r = subprocess.run(
        [sys.executable, "-m", "platformio", "run", "-e", "Upload_UART",
         "-t", "upload", "--upload-port", port],
        cwd=FIRMWARE_DIR, capture_output=True, text=True, timeout=300)
    out = (r.stdout or "") + (r.stderr or "")
    ok = r.returncode == 0 and "SUCCESS" in out
    if not ok:
        tail = "\n".join(out.strip().splitlines()[-8:])
        return False, tail
    return True, "flash written + verified over urclock"


def main():
    print(f"{C}=== Project Mariehoene firmware flasher (v0.2) ==={X}")
    print("Wire a bootloaded board to the adapter: GND, TX, RX, DTR (+5V/battery).")
    print("Each board takes ~10 s. Ctrl+C or close the window to stop.\n")
    log("flasher started")
    boards = 0
    wait_start = time.time()
    while True:
        port = find_port()
        if not port:
            print(f"\r{Y}[--] no adapter ({int(time.time() - wait_start)} s)   {X}",
                  end="", flush=True)
            time.sleep(1)
            continue
        print(f"\n[{ts()}] adapter on {port} - {C}flashing board #{boards + 1}...{X}", flush=True)
        try:
            ok, msg = flash(port)
        except subprocess.TimeoutExpired:
            ok, msg = False, "pio upload timed out"
        if ok:
            boards += 1
            print(f"[{ts()}] {G}*** board #{boards} flashed *** {msg}{X}")
            log(f"board {boards} flashed on {port}")
            print("\a", end="", flush=True)
            print(f"\n{Y}Connect the NEXT board, then press Enter (close window when done).{X}")
            try:
                input()
            except EOFError:
                return
            wait_start = time.time()
        else:
            print(f"[{ts()}] {R}[XX] flash failed:{X}\n{msg}")
            log(f"flash failed: {msg[:200]}")
            print(f"{Y}Check wiring (TX/RX crossed? DTR connected? board powered?) - retrying in 3 s{X}")
            time.sleep(3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped.")
