import os
import re
import json
import math
import time
import base64
import struct
import hashlib
import subprocess
import requests

OLLAMA_CHAT = "http://127.0.0.1:11434/api/generate"
VISION_MODEL = "qwen2.5vl:3b"
HASH_DB = "visual_hashes.json"

BANNED_KW = [
    "pubg", "bgmi", "cod mobile", "call of duty", "fortnite",
    "valorant", "minecraft", "gta", "roblox", "free fire live giveaway",
    "redeem code", "mod apk", "hack download",
]


def probe_video(path):
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    data = json.loads(r.stdout)
    vstream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if not vstream:
        return None
    dur = float(data.get("format", {}).get("duration") or vstream.get("duration") or 0)
    w = int(vstream.get("width") or 0)
    h = int(vstream.get("height") or 0)
    return {"duration": dur, "width": w, "height": h}


def frame_gray_metrics(path, ts, size=256):
    cmd = [
        "ffmpeg", "-v", "error", "-ss", f"{ts:.2f}", "-i", path,
        "-frames:v", "1", "-vf", f"scale={size}:{size},format=gray",
        "-f", "rawvideo", "pipe:1",
    ]
    r = subprocess.run(cmd, capture_output=True, timeout=20)
    raw = r.stdout
    need = size * size
    if len(raw) < need:
        return 0.0, 0.0, b""
    px = raw[:need]
    bright = sum(px) / float(need)
    lap_sq = 0.0
    count = 0
    for y in range(1, size - 1, 2):
        row = y * size
        up = (y - 1) * size
        dn = (y + 1) * size
        for x in range(1, size - 1, 2):
            idx = row + x
            val = (4 * px[idx]) - px[idx - 1] - px[idx + 1] - px[up + x] - px[dn + x]
            lap_sq += val * val
            count += 1
    sharp = lap_sq / max(1, count)
    return sharp, bright, px


def compute_dhash(path, ts):
    cmd = [
        "ffmpeg", "-v", "error", "-ss", f"{ts:.2f}", "-i", path,
        "-frames:v", "1", "-vf", "scale=9:8,format=gray",
        "-f", "rawvideo", "pipe:1",
    ]
    r = subprocess.run(cmd, capture_output=True, timeout=15)
    px = r.stdout
    if len(px) < 72:
        return None
    bits = 0
    bit_i = 0
    for y in range(8):
        off = y * 9
        for x in range(8):
            if px[off + x] > px[off + x + 1]:
                bits |= (1 << bit_i)
            bit_i += 1
    return bits


def hamming_dist(a, b):
    return (a ^ b).bit_count()


def load_hashes():
    if os.path.exists(HASH_DB):
        try:
            with open(HASH_DB, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_hash(h_val):
    hashes = load_hashes()
    hashes.append(str(h_val))
    with open(HASH_DB, "w", encoding="utf-8") as f:
        json.dump(hashes[-300:], f)


def is_duplicate_clip(path, dur):
    sample_ts = max(1.0, dur * 0.45)
    h = compute_dhash(path, sample_ts)
    if h is None:
        return False, None
    for old_s in load_hashes():
        try:
            if hamming_dist(h, int(old_s)) <= 4:
                return True, h
        except Exception:
            pass
    return False, h


def quality_scan(path, dur=None):
    if dur is None:
        info = probe_video(path)
        if not info:
            return False, "unreadable video"
        dur = info["duration"]
    points = [0.12, 0.30, 0.50, 0.70, 0.88]
    sharps, brights, prev_px, diffs = [], [], None, []
    for i, p in enumerate(points, 1):
        ts = max(0.5, dur * p)
        s, b, px = frame_gray_metrics(path, ts, 256)
        print(f"[Quality {i}/5 @ {ts:.1f}s] sharp={s:.1f} | bright={b:.1f}")
        sharps.append(s)
        brights.append(b)
        if prev_px and px and len(px) == len(prev_px):
            step = 16
            d = sum(abs(px[k] - prev_px[k]) for k in range(0, len(px), step)) / max(1, len(px) // step)
            diffs.append(d)
        prev_px = px

    avg_s = sum(sharps) / max(1, len(sharps))
    crisp_frames = sum(1 for s in sharps if s >= 45.0)
    ok_bright = sum(1 for b in brights if 16.0 <= b <= 245.0)
    max_motion = max(diffs) if diffs else 10.0

    if crisp_frames < 3 or avg_s < 45.0:
        return False, f"blurry video (avg sharp={avg_s:.1f})"
    if ok_bright < 3:
        return False, "black or blown-out frames"
    if max_motion < 1.8:
        return False, "static slideshow / frozen frames"
    return True, f"sharp={avg_s:.1f}"


def extract_frame_b64(path, ts):
    cmd = [
        "ffmpeg", "-v", "error", "-ss", f"{ts:.2f}", "-i", path,
        "-frames:v", "1", "-vf", "scale=640:-2", "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1",
    ]
    r = subprocess.run(cmd, capture_output=True, timeout=20)
    if r.returncode != 0 or len(r.stdout) < 1500:
        return None
    return base64.b64encode(r.stdout).decode("utf-8")


def parse_conf(raw_val, is_ff):
    try:
        if isinstance(raw_val, str):
            m = re.findall(r"[\d.]+", raw_val)
            v = float(m[0]) if m else (85.0 if is_ff else 0.0)
        else:
            v = float(raw_val)
        if 0.0 < v <= 1.0:
            v *= 100.0
        c = int(round(v))
    except Exception:
        c = 85 if is_ff else 0
    if is_ff and c == 0:
        c = 85
    return max(0, min(100, c))


def ask_vision_frame(b64_img):
    prompt = (
        "Inspect this video screenshot carefully. "
        "Is this a 3D mobile shooting/battle-royale game (like Garena Free Fire or Free Fire MAX with characters, guns, loot, or touch HUD controls)? "
        "Reject IRL cameras, cartoons, chess, Minecraft, GTA, PUBG PC, or blank text screens. "
        "Return ONLY valid JSON with exact keys: "
        '{"is_free_fire": true, "is_corrupt": false, "confidence": 85, "weapon": "short weapon or unknown", "scene": "short 8 word description of actual action"}'
    )
    try:
        r = requests.post(
            OLLAMA_CHAT,
            json={
                "model": VISION_MODEL,
                "prompt": prompt,
                "images": [b64_img],
                "stream": False,
                "format": "json",
            },
            timeout=65,
        )
        raw = r.json().get("response", "").strip()
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        obj = json.loads(m.group(0) if m else raw)
        ff_raw = obj.get("is_free_fire", obj.get("free_fire", obj.get("is_ff", False)))
        ff = ff_raw if isinstance(ff_raw, bool) else str(ff_raw).lower() in ["true", "yes", "1"]
        bad_raw = obj.get("is_corrupt", obj.get("corrupt", False))
        bad = bad_raw if isinstance(bad_raw, bool) else str(bad_raw).lower() in ["true", "yes", "1"]
        conf = parse_conf(obj.get("confidence", obj.get("conf", 0)), ff)
        scene = str(obj.get("scene") or obj.get("summary") or "Free Fire gameplay combat")[:120]
        weapon = str(obj.get("weapon") or "unknown")[:40]
        return ff and (not bad), conf, weapon, scene
    except Exception as e:
        print(f"    [Vision API err] {str(e)[:90]}")
        return False, 0, "unknown", "vision error"


def verify_freefire_video(path, title=""):
    t_low = (title or "").lower()
    if any(b in t_low for b in BANNED_KW):
        return False, "banned keyword in title"

    info = probe_video(path)
    if not info:
        return False, "ffprobe failed"
    dur, w, h = info["duration"], info["width"], info["height"]
    if dur < 12.0 or dur > 600.0:
        return False, f"bad duration {dur:.1f}s"
    if min(w, h) < 360:
        return False, f"low res {w}x{h}"

    q_ok, q_msg = quality_scan(path, dur)
    if not q_ok:
        return False, q_msg

    dup, h_val = is_duplicate_clip(path, dur)
    if dup:
        return False, "duplicate visual hash already used"

    check_pts = [0.22, 0.50, 0.78]
    passes = 0
    best_scene = ""
    best_weapon = "unknown"
    for idx, p in enumerate(check_pts, 1):
        ts = max(1.0, dur * p)
        b64 = extract_frame_b64(path, ts)
        if not b64:
            continue
        ff_ok, conf, weapon, scene = ask_vision_frame(b64)
        print(f"[Agent AI {idx}/3 @ {ts:.1f}s] ff={ff_ok} | conf={conf}% | '{scene}'")
        if ff_ok and conf >= 50:
            passes += 1
            best_scene = scene
            if weapon.lower() not in ["unknown", "none", ""]:
                best_weapon = weapon

    if passes < 2:
        return False, f"Failed AI vision majority ({passes}/3 passed)"

    if h_val is not None:
        save_hash(h_val)
    try:
        with open("verified_scene.json", "w", encoding="utf-8") as f:
            json.dump({"title": title, "weapon": best_weapon, "scene": best_scene, "duration": dur}, f, indent=2)
    except Exception:
        pass
    return True, f"Verified ({passes}/3 AI pass, {q_msg})"


def crop_action_peak(in_path, out_path="raw_gameplay.mp4", clip_len=35):
    info = probe_video(in_path)
    if not info:
        return False
    dur = info["duration"]
    if dur <= clip_len + 2.0:
        cmd = [
            "ffmpeg", "-y", "-v", "error", "-i", in_path,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k", out_path,
        ]
        subprocess.run(cmd, check=True, timeout=90)
        return os.path.exists(out_path)

    best_start = max(0.0, (dur - clip_len) / 2.0)
    try:
        cmd = [
            "ffmpeg", "-v", "error", "-i", in_path, "-vn",
            "-ac", "1", "-ar", "8000", "-f", "s16le", "pipe:1",
        ]
        r = subprocess.run(cmd, capture_output=True, timeout=30)
        pcm = r.stdout
        total_samples = len(pcm) // 2
        sec_energies = []
        for s in range(0, total_samples, 8000):
            chunk = pcm[s * 2 : (s + 8000) * 2]
            if len(chunk) < 1600:
                break
            vals = struct.unpack(f"<{len(chunk)//2}h", chunk)
            sec_energies.append(sum(abs(x) for x in vals) / len(vals))

        if len(sec_energies) > clip_len:
            best_sum = -1.0
            best_sec = 0
            cur = sum(sec_energies[:clip_len])
            best_sum = cur
            for i in range(1, len(sec_energies) - clip_len + 1):
                cur += sec_energies[i + clip_len - 1] - sec_energies[i - 1]
                if cur > best_sum:
                    best_sum = cur
                    best_sec = i
            best_start = float(best_sec)
    except Exception as e:
        print(f"[!] Audio peak scan skipped ({e}), using mid-clip")

    print(f"[*] Cropping {clip_len}s peak action starting @ {best_start:.1f}s")
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-ss", f"{best_start:.2f}", "-i", in_path,
        "-t", str(clip_len), "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k", out_path,
    ]
    subprocess.run(cmd, check=True, timeout=90)
    return os.path.exists(out_path)
