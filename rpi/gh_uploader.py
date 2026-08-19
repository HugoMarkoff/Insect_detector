#!/usr/bin/env python3
"""Push the insect-cam state to GitHub: a small rolling window of recent JPEGs
plus ONE growing timelapse video.

Design (v2):
  * Every frame is encoded (H.264) into a tiny MP4 segment on the Pi; all
    segments are then stream-copied (no re-encode) into a single
    `timelapse.mp4`. Unlimited frames, one file.
  * Only the newest KEEP JPEGs ride along (for the gallery's "recent" and
    "insect" rows). Older frames stay ON THE PI, archived by timelapse.py
    into ~/timelapse_history/ - history is kept, never uploaded.
  * The branch holds a single squashed commit (amend + force push). Because
    the previous commit's objects stay in the local repo, git only transfers
    NEW blobs - and since the video grows by appending, its delta is roughly
    just the new tail. No more re-uploading everything.
  * If the video passes VIDEO_MAX_MB (GitHub caps files at 100 MB) it is
    archived locally to ~/timelapse_history/ and a fresh one starts.

Auth: SSH deploy key at ~/.ssh/insectcam_deploy (write access to this repo).
"""
import json
import os
import shutil
import subprocess
import time

try:
    import detect                         # optional insect/change detection (needs Pillow)
except ImportError:
    detect = None

OWNER = os.environ.get("GH_OWNER", "HugoMarkoff")
REPO = os.environ.get("GH_REPO", "Insect_detector")
BRANCH = os.environ.get("GH_BRANCH", "images")
SRC = os.environ.get("TIMELAPSE_DIR", os.path.expanduser("~/timelapse_images"))
HIST = os.environ.get("TIMELAPSE_HISTORY", os.path.expanduser("~/timelapse_history"))
SEG = os.path.expanduser("~/timelapse_segments")
STATE = os.path.join(SEG, "encoded.json")
WORK = os.path.expanduser("~/insect-cam-git")
KEY = os.path.expanduser("~/.ssh/insectcam_deploy")
KEEP = int(os.environ.get("GH_KEEP", "30"))
INTERVAL = int(os.environ.get("GH_UPLOAD_INTERVAL", "90"))
CAPTURE_INTERVAL = int(os.environ.get("TIMELAPSE_INTERVAL", "180"))  # for the manifest
VID_FPS = int(os.environ.get("VIDEO_FPS", "8"))
VID_W = int(os.environ.get("VIDEO_WIDTH", "800"))
VIDEO_MAX_MB = int(os.environ.get("VIDEO_MAX_MB", "85"))
REMOTE = f"git@github.com:{OWNER}/{REPO}.git"

ENV = dict(os.environ, GIT_SSH_COMMAND=(
    f"ssh -i {KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"))

FFMPEG = shutil.which("ffmpeg")


def git(*args, check=True):
    return subprocess.run(["git", "-C", WORK, *args], env=ENV,
                          capture_output=True, text=True, check=check)


def ensure_repo():
    imgdir = os.path.join(WORK, "images")
    if not os.path.isdir(os.path.join(WORK, ".git")):
        os.makedirs(imgdir, exist_ok=True)
        git("init", "-q")
        git("checkout", "-q", "--orphan", BRANCH)
        git("config", "user.email", "cam@insect-detector.local")
        git("config", "user.name", "insect-cam")
        with open(os.path.join(WORK, ".gitattributes"), "w") as f:
            f.write("*.jpg -text\n*.mp4 -text\n")
    os.makedirs(imgdir, exist_ok=True)
    os.makedirs(SEG, exist_ok=True)
    os.makedirs(HIST, exist_ok=True)
    return imgdir


def sync_window(imgdir):
    src = sorted((f for f in os.listdir(SRC) if f.endswith(".jpg")), reverse=True)[:KEEP]
    keep = set(src)
    changed = False
    for f in os.listdir(imgdir):
        if f not in keep:
            os.remove(os.path.join(imgdir, f)); changed = True
    for f in src:
        dst = os.path.join(imgdir, f)
        srcp = os.path.join(SRC, f)
        # Re-copy if the source grew since a prior copy (guards against pushing a
        # frame that rpicam-still was still writing when first copied).
        if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(srcp):
            shutil.copy2(srcp, dst); changed = True
    return changed


# ---------------- video pipeline ----------------
def _load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {}


def _save_state(state):
    with open(STATE, "w") as fh:
        json.dump(state, fh)


def encode_new_segment():
    """Encode all not-yet-encoded frames (chronological) into one MP4 segment.
    Returns True if a new segment was produced."""
    if not FFMPEG:
        return False
    state = _load_state()
    frames = sorted(f for f in os.listdir(SRC) if f.endswith(".jpg") and f not in state)
    # skip the newest frame - it may still be mid-write by the camera
    if frames and time.time() - os.path.getmtime(os.path.join(SRC, frames[-1])) < 10:
        frames = frames[:-1]
    if not frames:
        return False
    tmp = os.path.join(SEG, "_tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    for i, f in enumerate(frames):
        os.symlink(os.path.join(SRC, f), os.path.join(tmp, "f_%05d.jpg" % i))
    seg = os.path.join(SEG, "seg_%d.mp4" % int(time.time()))
    r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                        "-framerate", str(VID_FPS), "-i", os.path.join(tmp, "f_%05d.jpg"),
                        "-vf", f"scale={VID_W}:-2", "-c:v", "libx264",
                        "-preset", "ultrafast", "-crf", "28", "-pix_fmt", "yuv420p",
                        seg], capture_output=True, text=True)
    shutil.rmtree(tmp, ignore_errors=True)
    if r.returncode != 0 or not os.path.exists(seg):
        print("[video] segment encode failed:", (r.stderr or "")[:200], flush=True)
        return False
    for f in frames:
        state[f] = 1
    _save_state(state)
    print(f"[video] encoded segment with {len(frames)} frame(s)", flush=True)
    return True


def rebuild_video():
    """Stream-copy all segments into WORK/timelapse.mp4 (no re-encode). Roll
    to a fresh video (archiving locally) when it outgrows VIDEO_MAX_MB."""
    out = os.path.join(WORK, "timelapse.mp4")
    segs = sorted(f for f in os.listdir(SEG) if f.startswith("seg_") and f.endswith(".mp4"))
    if not segs:
        return False
    lst = os.path.join(SEG, "concat.txt")
    with open(lst, "w") as fh:
        for s in segs:
            fh.write("file '%s'\n" % os.path.join(SEG, s))
    r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "concat", "-safe", "0", "-i", lst,
                        "-c", "copy", "-movflags", "+faststart", out],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out):
        print("[video] concat failed:", (r.stderr or "")[:200], flush=True)
        return False
    link = os.path.join(SRC, "timelapse.mp4")          # expose to the local
    if not os.path.islink(link) and not os.path.exists(link):   # :8080 gallery
        try:
            os.symlink(out, link)
        except OSError:
            pass
    if os.path.getsize(out) > VIDEO_MAX_MB * 1024 * 1024:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        arch = os.path.join(HIST, "video-archive-" + stamp)
        os.makedirs(arch, exist_ok=True)
        shutil.move(out, os.path.join(arch, "timelapse.mp4"))
        for s in segs:
            shutil.move(os.path.join(SEG, s), os.path.join(arch, s))
        _save_state({})
        print(f"[video] hit {VIDEO_MAX_MB} MB - archived to {arch}, starting fresh", flush=True)
        return True                        # WORK video removed -> commit the removal
    return True


def video_frame_count():
    return len(_load_state())


# ---------------- manifest + push ----------------
def build_manifest(imgdir):
    """Score each frame for insect activity (once, cached) and write manifest.json
    at the branch root. The gallery reads this single file."""
    meta_path = os.path.join(WORK, "meta.json")
    try:
        meta = json.load(open(meta_path))
    except Exception:
        meta = {}
    files = sorted(f for f in os.listdir(imgdir) if f.endswith(".jpg"))   # chronological
    prev = None
    for f in files:
        if f not in meta:
            if prev is not None and detect and detect.available():
                insect, score = detect.score_frame(os.path.join(imgdir, prev),
                                                    os.path.join(imgdir, f))
            else:
                insect, score = False, 0.0
            meta[f] = {"insect": bool(insect), "score": float(score)}
        prev = f
    meta = {k: v for k, v in meta.items() if k in set(files)}             # drop rolled-out
    with open(meta_path, "w") as fh:
        json.dump(meta, fh)
    frames = [{"name": f, "insect": meta[f]["insect"], "score": meta[f]["score"]}
              for f in sorted(files, reverse=True)]                        # newest first
    status = {}                                                            # telemetry from timelapse.py
    try:
        with open(os.path.join(SRC, "status.json")) as fh:
            status = json.load(fh)
    except Exception:
        pass
    vid = os.path.join(WORK, "timelapse.mp4")
    manifest = {"interval": CAPTURE_INTERVAL, "count": len(frames),
                "insects": sum(1 for f in frames if f["insect"]),
                "video": "timelapse.mp4" if os.path.exists(vid) else None,
                "video_frames": video_frame_count(),
                "video_fps": VID_FPS,
                "status": status, "frames": frames}
    with open(os.path.join(WORK, "manifest.json"), "w") as fh:
        json.dump(manifest, fh)


def push():
    git("add", "-A")
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        return False
    if git("rev-parse", "-q", "--verify", "HEAD", check=False).returncode == 0:
        git("commit", "-q", "--amend", "-m", "rolling window + timelapse video")
    else:
        git("commit", "-q", "-m", "rolling window + timelapse video")
    r = git("push", "-f", REMOTE, f"HEAD:{BRANCH}", check=False)
    if r.returncode != 0:
        print("[push] failed:", (r.stderr or "").strip()[:200], flush=True)
        return False
    return True


def main():
    if not FFMPEG:
        print("gh_uploader: ffmpeg not found - video disabled, images only", flush=True)
    print(f"uploader v2: {OWNER}/{REPO} branch {BRANCH}, keep {KEEP} jpgs, "
          f"one video @{VID_FPS}fps w{VID_W}, every {INTERVAL}s", flush=True)
    imgdir = None
    while True:
        try:
            if imgdir is None:                # (re)initialise inside the loop so a
                imgdir = ensure_repo()        # git error retries instead of crash-looping
            changed = sync_window(imgdir)
            if encode_new_segment():
                changed = rebuild_video() or changed
            if changed:
                build_manifest(imgdir)        # score frames -> manifest.json
                if push():
                    n = len([f for f in os.listdir(imgdir) if f.endswith(".jpg")])
                    print(f"pushed: {n} jpgs in window, video {video_frame_count()} frames",
                          flush=True)
        except Exception as e:
            print(f"cycle error: {e}", flush=True)
            imgdir = None
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
