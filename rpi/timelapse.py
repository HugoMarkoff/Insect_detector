#!/usr/bin/env python3
"""Insect Detector - WiFi timelapse with live web gallery.

Runs on the trap Raspberry Pi. Every INTERVAL seconds it drives the IR output
on the Arduino, captures a frame, drives IR back off, and stores the JPEG. A
built-in threaded web server serves an auto-refreshing gallery so you can watch
the captures live from any browser on the LAN (http://<pi-ip>:8080/).

The RPi stays powered the whole time (no shutdown handshake) and tells the
Arduino to stay always-on so it never cuts power on its own timeout.

I2C to Arduino @0x08 (firmware v0.2):
  0x0E [1]      -> always-on
  0x0F [0,1/0]  -> IR output (D5) on / off
"""
import datetime
import http.server
import json
import os
import socketserver
import subprocess
import threading
import time

try:
    import smbus2
    _bus_ok = True
except ImportError:
    _bus_ok = False

# ---- config ----
# INTERVAL and IR_HOLD are env-overridable so the same script serves both the
# normal timelapse and a hardware IR test (IR held on, fast captures):
#   TIMELAPSE_IR_HOLD=1 TIMELAPSE_INTERVAL=15 python3 timelapse.py
INTERVAL = int(os.environ.get("TIMELAPSE_INTERVAL", "180"))   # seconds between captures
IR_HOLD = os.environ.get("TIMELAPSE_IR_HOLD", "0") == "1"     # force IR on, never off
PORT = 8080
# absolute-safe: rc.local runs this as root, but keep images in tester's home
IMG_DIR = os.environ.get("TIMELAPSE_DIR", os.path.expanduser("~/timelapse_images"))
I2C_ADDR = 0x08
IR_PIN = 0                           # CMD_SET_OUTPUT pin id 0 = IR/flash (D5)
WIDTH, HEIGHT = 1920, 1080
ROTATION = 180
TUNING = "/usr/share/libcamera/ipa/rpi/vc4/imx708_noir.json"
MIN_BYTES = 20000

os.makedirs(IMG_DIR, exist_ok=True)


# ---- I2C helpers ----
def i2c_write(cmd, data):
    if not _bus_ok:
        return False
    try:
        b = smbus2.SMBus(1)
        b.write_i2c_block_data(I2C_ADDR, cmd, data)
        b.close()
        return True
    except Exception as e:
        print(f"[i2c] cmd 0x{cmd:02X} failed: {e}", flush=True)
        return False


def ir(on):
    i2c_write(0x0F, [IR_PIN, 1 if on else 0])


def set_always_on():
    if i2c_write(0x0E, [1]):
        print("[i2c] Arduino set to always-on", flush=True)


# ---- capture ----
def capture(path):
    subprocess.run(["pkill", "-f", "rpicam-still"], capture_output=True)
    cmd = ["rpicam-still", "--nopreview", "--immediate", "-o", path,
           "--width", str(WIDTH), "--height", str(HEIGHT),
           "--rotation", str(ROTATION), "-t", "1200"]
    if os.path.exists(TUNING):
        cmd += ["--tuning-file", TUNING]
    subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return os.path.exists(path) and os.path.getsize(path) > MIN_BYTES


# ---- web gallery ----
GALLERY_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Insect Timelapse</title>
<style>
  :root{color-scheme:dark}
  *{box-sizing:border-box}
  body{margin:0;background:#14140f;color:#e8e6dc;font:15px/1.5 system-ui,sans-serif}
  header{position:sticky;top:0;background:#1c1c15;border-bottom:1px solid #33332a;
    padding:12px 18px;display:flex;gap:18px;align-items:baseline;flex-wrap:wrap;z-index:5}
  h1{font-size:17px;font-weight:600;margin:0}
  .meta{color:#9c9a8c;font-size:13px}
  .dot{width:8px;height:8px;border-radius:50%;background:#5dca8f;display:inline-block;
    margin-right:6px;animation:pulse 2s ease-in-out infinite;vertical-align:middle}
  @keyframes pulse{50%{opacity:.35}}
  main{padding:18px;max-width:1100px;margin:0 auto}
  #hero{width:100%;border-radius:12px;border:1px solid #33332a;background:#000}
  #herocap{color:#9c9a8c;font-size:13px;margin:8px 2px 22px}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
  figure{margin:0}
  figure img{width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:8px;
    border:1px solid #33332a;background:#000;cursor:pointer}
  figcaption{color:#8a887c;font-size:11px;margin-top:3px;text-align:center}
  .empty{color:#9c9a8c;padding:40px 0;text-align:center}
</style></head><body>
<header>
  <h1><span class="dot"></span>Insect Timelapse</h1>
  <span class="meta"><b id="count">0</b> frames</span>
  <span class="meta">latest: <b id="latest">-</b></span>
  <span class="meta">every __INTERVAL__ s &middot; next in <b id="next">-</b></span>
</header>
<main>
  <img id="hero" alt="latest capture" style="display:none">
  <div id="herocap"></div>
  <div class="grid" id="grid"></div>
  <div class="empty" id="empty">waiting for the first capture...</div>
</main>
<script>
const INTERVAL=__INTERVAL__;
let lastNewest=null, lastSeen=Date.now();
function pretty(f){const m=f.match(/(\\d{4})(\\d{2})(\\d{2})_(\\d{2})(\\d{2})(\\d{2})/);
  return m?`${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}:${m[6]}`:f;}
async function refresh(){
  let files=[];
  try{files=await (await fetch('/list',{cache:'no-store'})).json();}catch(e){return;}
  document.getElementById('count').textContent=files.length;
  const empty=document.getElementById('empty'),hero=document.getElementById('hero');
  if(!files.length){empty.style.display='';hero.style.display='none';return;}
  empty.style.display='none';hero.style.display='';
  const newest=files[0];
  document.getElementById('latest').textContent=pretty(newest);
  if(newest!==lastNewest){
    lastNewest=newest;lastSeen=Date.now();
    hero.src='/img/'+newest;
    document.getElementById('herocap').textContent='newest: '+pretty(newest);
    document.getElementById('grid').innerHTML=files.map(f=>
      `<figure><img loading="lazy" src="/img/${f}" onclick="location='/img/${f}'"><figcaption>${pretty(f)}</figcaption></figure>`).join('');
  }
}
function tick(){
  const left=Math.max(0,INTERVAL-Math.round((Date.now()-lastSeen)/1000));
  document.getElementById('next').textContent=left+'s';
}
setInterval(refresh,4000);setInterval(tick,1000);refresh();
</script></body></html>""".replace("__INTERVAL__", str(INTERVAL))


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self._send(GALLERY_HTML.encode(), "text/html; charset=utf-8")
        elif self.path == "/list":
            files = sorted((f for f in os.listdir(IMG_DIR) if f.endswith(".jpg")),
                           reverse=True)
            self._send(json.dumps(files).encode(), "application/json")
        elif self.path.startswith("/img/"):
            name = os.path.basename(self.path[5:])
            p = os.path.join(IMG_DIR, name)
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    self._send(f.read(), "image/jpeg")
            else:
                self.send_error(404)
        else:
            self.send_error(404)


class ThreadingHTTP(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve():
    ThreadingHTTP(("0.0.0.0", PORT), Handler).serve_forever()


def main():
    threading.Thread(target=serve, daemon=True).start()
    print(f"gallery serving on http://0.0.0.0:{PORT}/  (open the Pi's IP)", flush=True)
    print(f"mode: interval={INTERVAL}s  IR_HOLD={IR_HOLD}", flush=True)
    set_always_on()
    if IR_HOLD:
        ir(True)
        print("[i2c] IR forced ON and held (test mode)", flush=True)
    n = 0
    while True:
        start = time.time()
        n += 1
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(IMG_DIR, f"{stamp}.jpg")
        ir(True)                      # (re)assert IR on before every shot
        time.sleep(0.4)
        print(f"[{stamp}] capture #{n}: IR {'held on' if IR_HOLD else 'on -> shoot -> off'}",
              flush=True)
        try:
            ok = capture(path)
        except Exception as e:
            ok = False
            print(f"  capture error: {e}", flush=True)
        if not IR_HOLD:
            ir(False)
        print(f"  {'saved ' + str(os.path.getsize(path)) + ' bytes' if ok else 'FAILED'}",
              flush=True)
        time.sleep(max(1, INTERVAL - (time.time() - start)))


if __name__ == "__main__":
    main()
