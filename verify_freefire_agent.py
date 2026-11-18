import os, re, json, base64, struct, subprocess, requests

OLLAMA_CHAT = "http://127.0.0.1:11434/api/generate"
VISION_MODEL = "qwen2.5vl:3b"
HASH_DB = "visual_hashes.json"
BANNED_KW = ["pubg", "bgmi", "cod mobile", "call of duty", "fortnite", "valorant", "minecraft", "gta", "roblox", "giveaway", "redeem code", "mod apk"]
VISION_SCHEMA = {
    "type": "object",
    "properties": {
        "is_free_fire": {"type": "boolean"},
        "is_corrupt": {"type": "boolean"},
        "confidence": {"type": "integer"},
        "weapon": {"type": "string"},
        "scene": {"type": "string"},
    },
    "required": ["is_free_fire", "is_corrupt", "confidence", "weapon", "scene"],
}


def probe_video(path):
    r = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path], capture_output=True, text=True, timeout=20)
    if r.returncode != 0 or not r.stdout.strip(): return None
    data = json.loads(r.stdout)
    vs = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if not vs: return None
    return {"duration": float(data.get("format", {}).get("duration") or vs.get("duration") or 0), "width": int(vs.get("width") or 0), "height": int(vs.get("height") or 0)}


def frame_gray_metrics(path, ts, size=256):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ts:.2f}", "-i", path, "-frames:v", "1", "-vf", f"scale={size}:{size},format=gray", "-f", "rawvideo", "pipe:1"], capture_output=True, timeout=20)
    need = size * size
    if len(r.stdout) < need: return 0.0, 0.0, b""
    px = r.stdout[:need]
    lap_sq, cnt = 0.0, 0
    for y in range(1, size - 1, 2):
        row, up, dn = y * size, (y - 1) * size, (y + 1) * size
        for x in range(1, size - 1, 2):
            i = row + x
            v = (4 * px[i]) - px[i - 1] - px[i + 1] - px[up + x] - px[dn + x]
            lap_sq += v * v; cnt += 1
    return lap_sq / max(1, cnt), sum(px) / float(need), px


def compute_dhash(path, ts):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ts:.2f}", "-i", path, "-frames:v", "1", "-vf", "scale=9:8,format=gray", "-f", "rawvideo", "pipe:1"], capture_output=True, timeout=15)
    px = r.stdout
    if len(px) < 72: return None
    bits, bi = 0, 0
    for y in range(8):
        off = y * 9
        for x in range(8):
            if px[off + x] > px[off + x + 1]: bits |= (1 << bi)
            bi += 1
    return bits


def quality_scan(path, dur=None):
    if dur is None:
        info = probe_video(path)
        if not info: return False, "unreadable video"
        dur = info["duration"]
    sharps, brights, prev_px, diffs = [], [], None, []
    for i, p in enumerate([0.12, 0.30, 0.50, 0.70, 0.88], 1):
        ts = max(0.5, dur * p)
        s, b, px = frame_gray_metrics(path, ts, 256)
        print(f"[Quality {i}/5 @ {ts:.1f}s] sharp={s:.1f} | bright={b:.1f}")
        sharps.append(s); brights.append(b)
        if prev_px and px and len(px) == len(prev_px):
            diffs.append(sum(abs(px[k] - prev_px[k]) for k in range(0, len(px), 16)) / max(1, len(px) // 16))
        prev_px = px
    avg_s = sum(sharps) / max(1, len(sharps))
    if sum(1 for s in sharps if s >= 45.0) < 3 or avg_s < 45.0: return False, f"blurry ({avg_s:.1f})"
    if sum(1 for b in brights if 16.0 <= b <= 245.0) < 3: return False, "dark/blown frames"
    if diffs and max(diffs) < 1.8: return False, "frozen/static slideshow"
    return True, f"sharp={avg_s:.1f}"


def extract_frame_b64(path, ts):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ts:.2f}", "-i", path, "-frames:v", "1", "-vf", "scale=384:384:force_original_aspect_ratio=decrease", "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1"], capture_output=True, timeout=20)
    return base64.b64encode(r.stdout).decode("utf-8") if r.returncode == 0 and len(r.stdout) >= 1200 else None


def ask_vision_frame(b64_img):
    prompt = "Look at this frame. Is it 3D mobile shooting/battle-royale gameplay like Garena Free Fire? Set is_free_fire true if shooter characters, guns, or mobile controls appear; set is_corrupt true only if blank or broken. Fill confidence (0-100), weapon, and a short 8-word scene."
    try:
        r = requests.post(OLLAMA_CHAT, json={"model": VISION_MODEL, "prompt": prompt, "images": [b64_img], "stream": False, "format": VISION_SCHEMA, "keep_alive": "3m", "options": {"num_ctx": 1024, "num_predict": 95, "temperature": 0.0}}, timeout=120)
        obj = json.loads(r.json().get("response", "{}"))
        ff = bool(obj.get("is_free_fire"))
        bad = bool(obj.get("is_corrupt"))
        conf = int(obj.get("confidence") or (85 if ff else 0))
        if ff and conf == 0: conf = 85
        return ff and (not bad), max(0, min(100, conf)), str(obj.get("weapon") or "unknown")[:40], str(obj.get("scene") or "Free Fire gameplay")[:120]
    except Exception as e:
        print(f"[Vision API err] {str(e)[:90]}")
        return False, 0, "unknown", "vision error"


def verify_freefire_video(path, title=""):
    if any(b in (title or "").lower() for b in BANNED_KW): return False, "banned keyword"
    info = probe_video(path)
    if not info: return False, "ffprobe failed"
    dur, w, h = info["duration"], info["width"], info["height"]
    if dur < 12.0 or dur > 600.0 or min(w, h) < 360: return False, f"bad dims/dur {w}x{h} {dur:.1f}s"
    q_ok, q_msg = quality_scan(path, dur)
    if not q_ok: return False, q_msg

    old_hashes = json.load(open(HASH_DB, "r", encoding="utf-8")) if os.path.exists(HASH_DB) else []
    h_val = compute_dhash(path, max(1.0, dur * 0.45))
    if h_val is not None and any((h_val ^ int(o)).bit_count() <= 4 for o in old_hashes if str(o).isdigit()):
        return False, "duplicate visual hash"

    passes, timeouts, best_scene, best_w = 0, 0, "", "unknown"
    for idx, pct in enumerate([0.25, 0.60, 0.80], 1):
        if idx == 3 and passes >= 2: break
        if idx == 3 and passes == 0 and timeouts == 0: break
        b64 = extract_frame_b64(path, max(1.0, dur * pct))
        if not b64: continue
        ff_ok, conf, weapon, scene = ask_vision_frame(b64)
        if scene == "vision error": timeouts += 1
        print(f"[Agent AI {idx}/3 @ {dur*pct:.1f}s] ff={ff_ok} | conf={conf}% | '{scene}'")
        if ff_ok and conf >= 50:
            passes += 1; best_scene = scene
            if weapon.lower() not in ["unknown", "none", ""]: best_w = weapon

    if passes < 2: return False, f"Failed AI majority ({passes}/3 passed)"
    if h_val is not None:
        old_hashes.append(str(h_val))
        json.dump(old_hashes[-300:], open(HASH_DB, "w", encoding="utf-8"))
    try: json.dump({"title": title, "weapon": best_w, "scene": best_scene, "duration": dur}, open("verified_scene.json", "w", encoding="utf-8"), indent=2)
    except Exception: pass
    return True, f"Verified ({passes} AI pass, {q_msg})"


def crop_action_peak(in_path, out_path="raw_gameplay.mp4", clip_len=35):
    info = probe_video(in_path)
    if not info: return False
    dur = info["duration"]
    best_start = max(0.0, (dur - clip_len) / 2.0)
    if dur > clip_len + 2.0:
        try:
            r = subprocess.run(["ffmpeg", "-v", "error", "-i", in_path, "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "pipe:1"], capture_output=True, timeout=30)
            pcm = r.stdout
            eng = [sum(abs(x) for x in struct.unpack(f"<{len(pcm[s*2:(s+8000)*2])//2}h", pcm[s*2:(s+8000)*2])) / 8000.0 for s in range(0, (len(pcm) // 2) - 8000, 8000)]
            if len(eng) > clip_len:
                cur = sum(eng[:clip_len]); best_sum, best_sec = cur, 0
                for i in range(1, len(eng) - clip_len + 1):
                    cur += eng[i + clip_len - 1] - eng[i - 1]
                    if cur > best_sum: best_sum, best_sec = cur, i
                best_start = float(best_sec)
        except Exception: pass
    print(f"[*] Cropping {min(clip_len, int(dur))}s peak @ {best_start:.1f}s")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{best_start:.2f}", "-i", in_path, "-t", str(clip_len), "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-c:a", "aac", "-b:a", "128k", out_path], check=True, timeout=90)
    return os.path.exists(out_path)
