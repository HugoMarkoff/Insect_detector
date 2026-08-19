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
def _int_env(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return int(default)

INTERVAL = _int_env("TIMELAPSE_INTERVAL", 180)               # seconds between captures
IR_HOLD = os.environ.get("TIMELAPSE_IR_HOLD", "0") == "1"    # force IR on, never off
PORT = 8080
# Set TIMELAPSE_DIR explicitly (the systemd unit does) so the capture service and
# the uploader service agree on one path regardless of which user they run as -
# under root, expanduser("~") would resolve to /root and the two could diverge.
IMG_DIR = os.environ.get("TIMELAPSE_DIR", os.path.expanduser("~/timelapse_images"))
MAX_STORED = _int_env("TIMELAPSE_MAX_STORED", 500)          # cap ~/timelapse_images (SD safety)
IR_LIGHT_MAX = _int_env("IR_LIGHT_MAX", 100)                # fire IR only when the light
#   sensor reads BELOW this (0-255, higher = brighter; ~215 = bright daylight).
#   100 = the field-proven legacy trap default (duskValue 400 on the raw
#   0-1023 scale / 4). Set 256 to always use IR, 0 to never.
STATUS_FILE = os.path.join(IMG_DIR, "status.json")          # telemetry for the gallery
I2C_ADDR = 0x08
IR_PIN = 0                           # CMD_SET_OUTPUT pin id 0 = IR/flash (D5)
WIDTH = _int_env("TIMELAPSE_WIDTH", 4608)                   # DAY resolution: the
HEIGHT = _int_env("TIMELAPSE_HEIGHT", 2592)                 #   IMX708's full 12 MP
NIGHT_WIDTH = _int_env("TIMELAPSE_NIGHT_WIDTH", 4608)      # NIGHT: full 12 MP too.
NIGHT_HEIGHT = _int_env("TIMELAPSE_NIGHT_HEIGHT", 2592)     #   (Set 2304x1296 here for
#   the 2x2-binned mode if night frames look grainy - binning pools 4 pixels
#   of light into one, trading resolution for cleaner darks.)
AF_RANGE = os.environ.get("TIMELAPSE_AF_RANGE", "macro")    # macro|normal|full - the
#   insect cam looks at its feet, so bias focus close
ROTATION = 180
# Sensor/SoC-specific; overridable. Missing file -> capture runs without tuning.
TUNING = os.environ.get("TIMELAPSE_TUNING", "/usr/share/libcamera/ipa/rpi/vc4/imx708_noir.json")
MIN_BYTES = 20000

os.makedirs(IMG_DIR, exist_ok=True)


# ---- I2C helpers ----
def i2c_write(cmd, data):
    if not _bus_ok:
        return False
    try:
        with smbus2.SMBus(1) as b:        # context manager closes the fd even on error
            b.write_i2c_block_data(I2C_ADDR, cmd, data)
        return True
    except Exception as e:
        print(f"[i2c] cmd 0x{cmd:02X} failed: {e}", flush=True)
        return False


HIST_DIR = os.environ.get("TIMELAPSE_HISTORY", os.path.expanduser("~/timelapse_history"))
ADMIN_PW = os.environ.get("ADMIN_PW", "123")                # LAN admin: delete frames, draw boxes
ANNOT_PATH = os.path.expanduser("~/annotations.json")
SEG_STATE = os.path.expanduser("~/timelapse_segments/encoded.json")


def admin_delete(name):
    """Delete a frame everywhere the Pi controls it: the working dir AND the
    video (by dropping the segment that contains it - its sibling frames get
    re-encoded automatically on the uploader's next cycle)."""
    p = os.path.join(IMG_DIR, name)
    if os.path.isfile(p):
        os.remove(p)
    try:
        state = json.load(open(SEG_STATE))
    except Exception:
        state = {}
    seg = state.pop(name, None)
    if isinstance(seg, str):
        segp = os.path.join(os.path.dirname(SEG_STATE), seg)
        if os.path.isfile(segp):
            os.remove(segp)
        for k in [k for k, v in state.items() if v == seg]:
            state.pop(k)                       # siblings re-encode next cycle
    try:
        with open(SEG_STATE, "w") as fh:
            json.dump(state, fh)
    except OSError:
        pass
    try:                                       # drop any annotation for it too
        annot = json.load(open(ANNOT_PATH))
        if name in annot:
            annot.pop(name)
            json.dump(annot, open(ANNOT_PATH, "w"))
    except Exception:
        pass


def prune_old(keep):
    """Move everything but the newest `keep` JPEGs into the local history
    archive (~/timelapse_history/YYYYMMDD/). Nothing is deleted - the full
    history stays on the Pi, it just never gets uploaded."""
    imgs = sorted((f for f in os.listdir(IMG_DIR) if f.endswith(".jpg")), reverse=True)
    for f in imgs[keep:]:
        day = f[:8] if f[:8].isdigit() else "misc"
        dst = os.path.join(HIST_DIR, day)
        try:
            os.makedirs(dst, exist_ok=True)
            os.replace(os.path.join(IMG_DIR, f), os.path.join(dst, f))
        except OSError:
            pass


def ir(on):
    i2c_write(0x0F, [IR_PIN, 1 if on else 0])


def set_always_on():
    if i2c_write(0x0E, [1]):
        print("[i2c] Arduino set to always-on", flush=True)


def i2c_read(cmd):
    """Read one byte for an I2C command (write cmd, then read a byte back)."""
    if not _bus_ok:
        return None
    try:
        with smbus2.SMBus(1) as b:
            b.write_byte(I2C_ADDR, cmd)
            time.sleep(0.03)
            return b.read_byte(I2C_ADDR)
    except Exception:
        return None


def write_status():
    """Pull battery / light / firmware from the Arduino and write status.json."""
    import json
    dv = i2c_read(0x13)          # battery decivolts
    status = {
        "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "battery_pct": i2c_read(0x02),
        "battery_v": round(dv / 10.0, 1) if dv is not None else None,
        "light": i2c_read(0x12),          # 0-255 (higher = brighter)
        "fw": i2c_read(0x14),
    }
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump(status, f)
    except OSError:
        pass
    print(f"  telemetry: {status['battery_pct']}%  {status['battery_v']}V  light={status['light']}",
          flush=True)


# ---- capture ----
FOOTER_TEXT = os.environ.get("TIMELAPSE_FOOTER", "InsectDetect · by Hugo Markoff")


def stamp_image(path, stamp):
    """Trail-camera footer: a half-transparent bar along the bottom with the
    timestamp (left) and the InsectDetect credit (right)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return
    try:
        im = Image.open(path).convert("RGBA")
        w, h = im.size
        bar = max(30, h // 20)
        overlay = Image.new("RGBA", (w, bar), (0, 0, 0, 115))
        im.alpha_composite(overlay, (0, h - bar))
        d = ImageDraw.Draw(im)
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(bar * 0.52))
        except Exception:
            font = ImageFont.load_default()
        ts = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}  {stamp[9:11]}:{stamp[11:13]}:{stamp[13:15]}"
        pad = bar // 2
        d.text((pad, h - bar // 2), ts, fill=(255, 255, 255, 235), font=font, anchor="lm")
        d.text((w - pad, h - bar // 2), FOOTER_TEXT, fill=(235, 235, 235, 220),
               font=font, anchor="rm")
        im.convert("RGB").save(path, "JPEG", quality=92)
    except Exception as e:
        print(f"  footer stamp failed: {e}", flush=True)


def capture(path, day=True):
    subprocess.run(["pkill", "-f", "rpicam-still"], capture_output=True)
    w, h = (WIDTH, HEIGHT) if day else (NIGHT_WIDTH, NIGHT_HEIGHT)
    cmd = ["rpicam-still", "--nopreview", "-o", path,
           "--width", str(w), "--height", str(h),
           "--rotation", str(ROTATION), "-t", "4000", "-q", "95",
           "--denoise", "cdn_hq",
           "--autofocus-on-capture", "--autofocus-range", AF_RANGE]
    if os.path.exists(TUNING):
        cmd += ["--tuning-file", TUNING]
    subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return os.path.exists(path) and os.path.getsize(path) > MIN_BYTES


# ---- web gallery ----
GALLERY_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>InsectDetect</title>
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
  <h1><span class="dot"></span>InsectDetect</h1>
  <span class="meta"><b id="count">0</b> frames</span>
  <span class="meta">latest: <b id="latest">-</b></span>
  <span class="meta">every __INTERVAL__ s &middot; next in <b id="next">-</b></span>
  <span class="meta" style="margin-left:auto"><button id="adm" onclick="admLogin()"
    style="background:none;border:1px solid #33332a;color:#9c9a8c;border-radius:6px;padding:2px 10px;cursor:pointer">admin</button></span>
</header>
<main>
  <img id="hero" alt="latest capture" style="display:none">
  <div id="herocap"></div>
  <video id="vid" controls muted loop playsinline
         style="width:100%;border-radius:12px;border:1px solid #33332a;background:#000;display:none"></video>
  <div id="vidcap" class="meta" style="margin:8px 2px 22px"></div>
  <div class="grid" id="grid"></div>
  <div class="empty" id="empty">waiting for the first capture...</div>
</main>
<script>
const INTERVAL=__INTERVAL__;
fetch('timelapse.mp4',{method:'HEAD'}).then(r=>{ if(r.ok){
  const v=document.getElementById('vid'); v.src='timelapse.mp4?'+Date.now(); v.style.display='';
  document.getElementById('vidcap').textContent='full-run timelapse video — works offline, straight from the Pi';
}}).catch(()=>{});
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
      `<figure><img loading="lazy" src="/img/${f}" onclick="cardClick('${f}')">
        <figcaption>${pretty(f)}${annot[f]?' <span style="color:#e0b93f">[box:'+annot[f].length+']':''}${PW?` <a href="#" onclick="event.preventDefault();edOpen('${f}')" title="draw boxes">[box]</a> <a href="#" onclick="event.preventDefault();admDel('${f}')" title="delete" style="color:#d66">[x]</a>`:''}</figcaption>
      </figure>`).join('');
  }
}
let PW=localStorage.admPW||'', annot={};
async function loadAnnot(){ try{annot=await (await fetch('/api/annotations',{cache:'no-store'})).json();}catch(e){annot={};} }
function cardClick(f){ location='/img/'+f; }
async function admLogin(){
  const p=prompt('admin password:'); if(!p)return;
  const r=await fetch('/api/login',{method:'POST',body:JSON.stringify({pw:p})});
  if(r.ok){ PW=p; localStorage.admPW=p; document.getElementById('adm').textContent='admin: on'; lastNewest=null; refresh(); }
  else alert('wrong password');
}
async function admDel(f){
  if(!confirm('Delete '+f+' from the Pi AND the video?'))return;
  const r=await fetch('/api/delete',{method:'POST',body:JSON.stringify({pw:PW,name:f})});
  if(r.ok){ lastNewest=null; refresh(); } else alert('failed (password?)');
}
// ---- bbox editor ----
let edName='', edBoxes=[], edDrag=null;
function edOpen(f){
  edName=f; edBoxes=(annot[f]||[]).slice();
  document.getElementById('ed').style.display='block';
  const im=document.getElementById('edImg'); im.src='/img/'+f;
  im.onload=()=>{ const cv=document.getElementById('edCv');
    cv.width=im.clientWidth; cv.height=im.clientHeight; edDraw(); };
}
function edXY(e){ const cv=document.getElementById('edCv'), r=cv.getBoundingClientRect();
  return [ (e.clientX-r.left)/r.width, (e.clientY-r.top)/r.height ]; }
function edDown(e){ edDrag=edXY(e); }
function edMove(e){ if(!edDrag)return; edDraw(edXY(e)); }
function edUp(e){ if(!edDrag)return; const [x1,y1]=edDrag,[x2,y2]=edXY(e); edDrag=null;
  const b={x:Math.min(x1,x2),y:Math.min(y1,y2),w:Math.abs(x2-x1),h:Math.abs(y2-y1)};
  if(b.w>0.01&&b.h>0.01)edBoxes.push(b); edDraw(); }
function edDraw(cur){
  const cv=document.getElementById('edCv'),c=cv.getContext('2d');
  c.clearRect(0,0,cv.width,cv.height); c.lineWidth=2; c.strokeStyle='#ffd23f';
  for(const b of edBoxes)c.strokeRect(b.x*cv.width,b.y*cv.height,b.w*cv.width,b.h*cv.height);
  if(cur&&edDrag){ c.strokeStyle='#7fd0ff';
    c.strokeRect(Math.min(edDrag[0],cur[0])*cv.width,Math.min(edDrag[1],cur[1])*cv.height,
      Math.abs(cur[0]-edDrag[0])*cv.width,Math.abs(cur[1]-edDrag[1])*cv.height); } }
async function edSave(){
  const r=await fetch('/api/bbox',{method:'POST',body:JSON.stringify({pw:PW,name:edName,boxes:edBoxes})});
  if(r.ok){ await loadAnnot(); lastNewest=null; edClose(); refresh(); } else alert('failed'); }
function edUndo(){ edBoxes.pop(); edDraw(); }
function edClear(){ edBoxes=[]; edDraw(); }
function edClose(){ document.getElementById('ed').style.display='none'; }
if(PW)document.getElementById('adm').textContent='admin: on';
loadAnnot(); setInterval(loadAnnot,8000);
function tick(){
  const left=Math.max(0,INTERVAL-Math.round((Date.now()-lastSeen)/1000));
  document.getElementById('next').textContent=left+'s';
}
setInterval(refresh,4000);setInterval(tick,1000);refresh();
</script>
<div id="ed" style="display:none;position:fixed;inset:0;background:#000d;z-index:20;padding:16px" onclick="if(event.target.id==='ed')edClose()">
  <div style="position:relative;max-width:92vw;max-height:80vh;margin:0 auto;width:fit-content">
    <img id="edImg" style="max-width:92vw;max-height:78vh;display:block">
    <canvas id="edCv" style="position:absolute;left:0;top:0;cursor:crosshair"
      onmousedown="edDown(event)" onmousemove="edMove(event)" onmouseup="edUp(event)"></canvas>
  </div>
  <div style="text-align:center;margin-top:10px">
    <button onclick="edSave()">save boxes</button> <button onclick="edUndo()">undo</button>
    <button onclick="edClear()">clear</button> <button onclick="edClose()">close</button>
  </div>
</div>
</body></html>""".replace("__INTERVAL__", str(INTERVAL))


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
        elif self.path == "/api/annotations":
            try:
                body = open(ANNOT_PATH, "rb").read()
            except OSError:
                body = b"{}"
            self._send(body, "application/json")
        else:
            self.send_error(404)

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            self.send_error(400); return
        if req.get("pw") != ADMIN_PW:
            self.send_error(403); return
        name = os.path.basename(str(req.get("name", "")))
        if self.path == "/api/login":
            self._send(b'{"ok":true}', "application/json")
        elif self.path == "/api/delete" and name.endswith(".jpg"):
            admin_delete(name)
            self._send(b'{"ok":true}', "application/json")
        elif self.path == "/api/bbox" and name.endswith(".jpg"):
            try:
                annot = json.load(open(ANNOT_PATH))
            except Exception:
                annot = {}
            boxes = req.get("boxes") or []
            if boxes:
                annot[name] = boxes
            else:
                annot.pop(name, None)
            json.dump(annot, open(ANNOT_PATH, "w"))
            self._send(b'{"ok":true}', "application/json")
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
        light = i2c_read(0x12)        # 0-255, higher = brighter
        use_ir = IR_HOLD or light is None or light < IR_LIGHT_MAX
        if use_ir:
            ir(True)                  # (re)assert IR on before the shot
            time.sleep(0.4)
        print(f"[{stamp}] capture #{n}: light={'?' if light is None else light} -> "
              f"IR {'held on' if IR_HOLD else ('on' if use_ir else 'skipped (bright)')}",
              flush=True)
        try:
            ok = capture(path, day=not use_ir)
        except Exception as e:
            ok = False
            print(f"  capture error: {e}", flush=True)
        if use_ir and not IR_HOLD:
            ir(False)
        if ok:
            stamp_image(path, stamp)
        print(f"  {'saved ' + str(os.path.getsize(path)) + ' bytes' if ok else 'FAILED'}",
              flush=True)
        prune_old(MAX_STORED)         # bound SD usage
        write_status()                # battery / light / fw for the gallery
        time.sleep(max(1, INTERVAL - (time.time() - start)))


if __name__ == "__main__":
    main()
