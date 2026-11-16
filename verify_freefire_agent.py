# verify_freefire_agent.py - Full-Video Blur, Duplicate Hash, Action-Crop & AI Vision Agent
import os, re, sys, json, time, array, base64, tempfile, subprocess, urllib.request

OLLAMA_CHAT = "http://localhost:11434/api/chat"
OLLAMA_TAGS = "http://localhost:11434/api/tags"
VISION_MODEL = "qwen2.5vl:3b"
HASH_FILE = "visual_hashes.json"

BANNED_WORDS = [
    "pubg", "bgmi", "codm", "call of duty", "valorant", "gta", "minecraft",
    "roblox", "fortnite", "csgo", "mod menu", "hack", "panel", "apk",
    "redeem code", "giveaway", "podcast", "vlog", "unboxing", "news", "movie",
    "song", "lyrics", "whatsapp status", "shayari", "reaction", "face reveal",
    "prank", "live stream", "earning app", "diamond generator"
]
FF_SIGNALS = [
    "free fire", "freefire", "garena", "booyah", "m1887", "desert eagle",
    "mp40", "awm", "clash squad", "bermuda", "one tap", "1v4", "headshot"
]
VISION_SCHEMA = {
    "type": "object",
    "properties": {
        "is_gameplay": {"type": "boolean"},
        "is_mobile_shooter": {"type": "boolean"},
        "is_free_fire": {"type": "boolean"},
        "is_clear_sharp": {"type": "boolean"},
        "what_is_shown": {"type": "string"},
        "confidence": {"type": "integer"}
    },
    "required": ["is_gameplay", "is_mobile_shooter", "is_free_fire", "is_clear_sharp", "what_is_shown", "confidence"]
}

def reject_del(path, reason, remove_on_fail=True):
    if remove_on_fail and path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass
    return False, reason

def is_metadata_clean(title, desc="", trusted=False):
    txt = f"{title or ''} {desc or ''}".lower()
    for b in BANNED_WORDS:
        if b in txt:
            return False, f"Banned word: {b}"
    if trusted or any(s in txt for s in FF_SIGNALS) or re.search(r"\bff\b", txt):
        return True, "Metadata OK"
    return False, "Missing Free Fire keyword"

def video_info(path):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-show_entries", "format=duration", "-of", "json", path]
    d = json.loads(subprocess.check_output(cmd, text=True))
    s = d.get("streams") or []
    return int(s[0]["width"]), int(s[0]["height"]), float(d["format"]["duration"])

def gray_frame(path, ts, size):
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{ts:.2f}", "-i", path, "-vframes", "1", "-vf", f"scale={size}:flags=bilinear,format=gray", "-f", "rawvideo", "-"]
    return subprocess.check_output(cmd)

def dhash_64(path, ts):
    buf = gray_frame(path, ts, "9:8")
    if len(buf) != 72:
        return None
    h = 0
    for y in range(8):
        for x in range(8):
            if buf[y * 9 + x] > buf[y * 9 + x + 1]:
                h |= 1 << (y * 8 + x)
    return h

def check_and_save_hash(path, dur, save=False):
    h1, h2 = dhash_64(path, dur * 0.30), dhash_64(path, dur * 0.70)
    if h1 is None or h2 is None:
        return True
    saved = json.load(open(HASH_FILE)) if os.path.exists(HASH_FILE) else []
    for item in saved:
        if bin(h1 ^ item[0]).count("1") <= 8 and bin(h2 ^ item[1]).count("1") <= 8:
            return False
    if save:
        saved.append([h1, h2])
        json.dump(saved[-300:], open(HASH_FILE, "w"))
    return True

def quality_scan(path, dur):
    samples, sharps, blurry, bad_light = [], [], 0, 0
    for idx, pct in enumerate((0.10, 0.30, 0.50, 0.70, 0.90), 1):
        ts = dur * pct
        buf = gray_frame(path, ts, "256:256")
        if len(buf) != 65536:
            return False, "Incomplete frame"
        bright = sum(buf) / 65536.0
        w, sum_l, sum_l2, n = 256, 0.0, 0.0, 254 * 254
        for y in range(1, 255):
            r = y * w
            for x in range(1, 255):
                i = r + x
                lap = 4 * buf[i] - buf[i - 1] - buf[i + 1] - buf[i - w] - buf[i + w]
                sum_l += lap
                sum_l2 += lap * lap
        sharp = (sum_l2 / n) - (sum_l / n) ** 2
        sharps.append(sharp)
        samples.append(buf[::16])
        print(f"[Quality {idx}/5 @ {ts:.1f}s] sharp={sharp:.1f} | bright={bright:.1f}")
        if sharp < 32.0:
            blurry += 1
        if bright < 15.0 or bright > 245.0:
            bad_light += 1
    avg_s = sum(sharps) / 5.0
    if blurry >= 2 or avg_s < 45.0:
        return False, f"Blurry video (avg_sharp={avg_s:.1f})"
    if bad_light >= 2:
        return False, "Black/blank screen detected"
    moves = sum(1 for a, b in zip(samples, samples[1:]) if sum(abs(x - y) for x, y in zip(a, b)) / len(a) > 2.5)
    if moves < 2:
        return False, f"Frozen/slideshow video (moves={moves}/4)"
    return True, "Quality OK"

def ensure_vision():
    for att in range(2):
        try:
            models = [m.get("name", "") for m in json.loads(urllib.request.urlopen(OLLAMA_TAGS, timeout=5).read()).get("models", [])]
            if any(VISION_MODEL in m for m in models):
                return True
            print(f"[*] Agent: Pulling {VISION_MODEL}...")
            subprocess.run(["ollama", "pull", VISION_MODEL], check=True)
            return True
        except Exception:
            if att == 0:
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(3)
    return False

def ai_check_frame(path, ts, unload=False):
    with tempfile.TemporaryDirectory() as tmp:
        jpg = os.path.join(tmp, "f.jpg")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{ts:.2f}", "-i", path, "-vframes", "1", "-vf", "scale=512:-2", "-q:v", "3", jpg], check=True)
        b64 = base64.b64encode(open(jpg, "rb").read()).decode("utf-8")
    prompt = (
        "Inspect strictly, return JSON only. Set is_free_fire=true ONLY if this is actual 3D Garena Free Fire "
        "mobile shooter gameplay (character/combat + mobile HUD controls, HP bar, weapon slots, fire/gloo buttons, minimap). "
        "Set is_free_fire=false for facecams, vlogs, anime, movies, text slides, GTA, Minecraft, PUBG/BGMI, Valorant, Fortnite. "
        "Set is_clear_sharp=false if heavily blurred, pixelated, or blocked by overlays."
    )
    pay = {"model": VISION_MODEL, "messages": [{"role": "user", "content": prompt, "images": [b64]}], "format": VISION_SCHEMA, "stream": False, "keep_alive": 0 if unload else "2m", "options": {"temperature": 0.1, "num_predict": 140}}
    req = urllib.request.Request(OLLAMA_CHAT, data=json.dumps(pay).encode(), headers={"Content-Type": "application/json"})
    raw = json.loads(urllib.request.urlopen(req, timeout=120).read().decode())
    return json.loads(raw.get("message", {}).get("content", "{}"))

def crop_action_peak(path, target_dur):
    try:
        _, _, dur = video_info(path)
        if not target_dur or dur <= target_dur + 4.0:
            return
        pcm = subprocess.check_output(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"])
        if len(pcm) < 64000:
            return
        samp = array.array("h")
        samp.frombytes(pcm[: (len(pcm) // 2) * 2])
        secs = len(samp) // 8000
        e = [sum(abs(x) for x in samp[s * 8000 : (s + 1) * 8000]) / 8000.0 for s in range(secs)]
        win = max(14, min(int(target_dur) + 2, secs))
        best = max(range(secs - win + 1), key=lambda s: 0.65 * sum(e[s : s + 5]) + 0.35 * (sum(e[s : s + win]) / win))
        tmp = f"{path}.crop.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(best), "-t", str(win), "-i", path, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", tmp], check=True)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 50000:
            os.replace(tmp, path)
            print(f"[Agent] Action-Peak Cropped @ {best}s ({win}s)")
    except Exception:
        pass

def verify_freefire_video(path, source_title="", trusted_category=False, remove_on_fail=True, target_dur=None):
    if not os.path.exists(path) or os.path.getsize(path) < 50000:
        return reject_del(path, "Missing or tiny file", remove_on_fail)
    ok, msg = is_metadata_clean(source_title, trusted=trusted_category)
    if not ok:
        return reject_del(path, msg, remove_on_fail)
    try:
        w, h, dur = video_info(path)
    except Exception as e:
        return reject_del(path, f"Corrupt video: {e}", remove_on_fail)
    if min(w, h) < 360 or dur < 12.0 or dur > 600.0:
        return reject_del(path, f"Bad res/dur ({w}x{h}, {dur:.1f}s)", remove_on_fail)
    ok_q, q_msg = quality_scan(path, dur)
    if not ok_q:
        return reject_del(path, q_msg, remove_on_fail)
    if not check_and_save_hash(path, dur, save=False):
        return reject_del(path, "Duplicate visual clip (dHash match)", remove_on_fail)
    if not ensure_vision():
        return reject_del(path, "Vision model unavailable", remove_on_fail)
    pts = (0.15, 0.40, 0.65, 0.88)
    for idx, pct in enumerate(pts, 1):
        ts = dur * pct
        r = ai_check_frame(path, ts, unload=(idx == len(pts)))
        conf = int(r.get("confidence", 0))
        ok_ai = bool(r.get("is_gameplay")) and bool(r.get("is_mobile_shooter")) and bool(r.get("is_free_fire")) and bool(r.get("is_clear_sharp")) and conf >= 65
        print(f"[Agent AI {idx}/4 @ {ts:.1f}s] '{r.get('what_is_shown')}' | ff={r.get('is_free_fire')} | sharp={r.get('is_clear_sharp')} | conf={conf}%")
        if not ok_ai:
            return reject_del(path, f"Failed AI @ {ts:.1f}s ({r.get('what_is_shown')})", remove_on_fail)
    check_and_save_hash(path, dur, save=True)
    if target_dur:
        crop_action_peak(path, target_dur)
    return True, f"Verified Free Fire ({w}x{h}, {dur:.1f}s)"

if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "raw_gameplay.mp4"
    ok, msg = verify_freefire_video(p, trusted_category=True, remove_on_fail=True)
    print(f"[*] Verdict: {ok} -> {msg}")
    if not ok:
        sys.exit(1)
