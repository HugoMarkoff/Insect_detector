#!/usr/bin/env python3
"""Push the newest timelapse frames to GitHub as a rolling window.

Keeps only the last KEEP images and force-pushes a single squashed commit to
the `images` branch, so repo history never grows and the Pages branch is never
rebuilt. The Pages site lists these via the GitHub API.

Auth: SSH deploy key at ~/.ssh/insectcam_deploy (write access to this one repo).
"""
import os
import shutil
import subprocess
import time

OWNER = os.environ.get("GH_OWNER", "HugoMarkoff")
REPO = os.environ.get("GH_REPO", "Insect_detector")
BRANCH = os.environ.get("GH_BRANCH", "images")
SRC = os.environ.get("TIMELAPSE_DIR", os.path.expanduser("~/timelapse_images"))
WORK = os.path.expanduser("~/insect-cam-git")
KEY = os.path.expanduser("~/.ssh/insectcam_deploy")
KEEP = int(os.environ.get("GH_KEEP", "60"))
INTERVAL = int(os.environ.get("GH_UPLOAD_INTERVAL", "90"))
REMOTE = f"git@github.com:{OWNER}/{REPO}.git"

ENV = dict(os.environ, GIT_SSH_COMMAND=(
    f"ssh -i {KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"))


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
            f.write("*.jpg -text\n")
    os.makedirs(imgdir, exist_ok=True)
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


def push():
    git("add", "-A")
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        return False
    if git("rev-parse", "-q", "--verify", "HEAD", check=False).returncode == 0:
        git("commit", "-q", "--amend", "-m", "rolling window")
    else:
        git("commit", "-q", "-m", "rolling window")
    r = git("push", "-f", REMOTE, f"HEAD:{BRANCH}", check=False)
    if r.returncode != 0:
        print("[push] failed:", (r.stderr or "").strip()[:200], flush=True)
        return False
    return True


def main():
    if "GH_OWNER" not in os.environ:
        print("gh_uploader: GH_OWNER not set, defaulting to 'HugoMarkoff' - "
              "forks must set GH_OWNER (setup.sh sets it in the service unit).", flush=True)
    print(f"uploader: {OWNER}/{REPO} branch {BRANCH}, keep {KEEP}, every {INTERVAL}s", flush=True)
    imgdir = None
    while True:
        try:
            if imgdir is None:                # (re)initialise inside the loop so a
                imgdir = ensure_repo()        # git error retries instead of crash-looping
            if sync_window(imgdir) and push():
                n = len([f for f in os.listdir(imgdir) if f.endswith(".jpg")])
                print(f"pushed rolling window ({n} images)", flush=True)
        except Exception as e:
            print(f"cycle error: {e}", flush=True)
            imgdir = None
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
