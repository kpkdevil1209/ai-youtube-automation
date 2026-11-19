import os, re, json, base64, struct, subprocess, requests

OLLAMA_CHAT = "http://127.0.0.1:11434/api/generate"
VISION_MODEL = "qwen2.5vl:3b"
HASH_DB = "visual_hashes.json"
BANNED_KW = ["pubg", "bgmi", "cod mobile", "call of duty", "fortnite", "valorant", "minecraft", "gta", "roblox", "giveaway", "redeem code", "mod apk", "facecam", "reaction", "podcast", "lobby spin"]
VISION_SCHEMA = {
    "type": "object",
    "properties": {
        "is_free_fire": {"type": "boolean"},
        "is_combat": {"type": "boolean"},
        "has_facecam": {"type": "boolean"},
        "has_overlay_text": {"type": "boolean"},
        "is_corrupt": {"type": "boolean"},
        "confidence": {"type": "integer"},
        "weapon": {"type": "string"},
        "scene": {"type": "string"},
    },
    "required": ["is_free_fire", "is_combat", "has_facecam", "has_overlay_text", "is_corrupt", "confidence", "weapon", "scene"],
}
PHASE_SCHEMA = {
    "type": "object",
    "properties": {"weapon": {"type": "string"}, "scene": {"type": "string"}},
    "required": ["weapon", "scene"],
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
    if diffs and max(diffs) < 1.8: return False, "frozen slideshow"
    return True, f"sharp={avg_s:.1f}"


def extract_frame_b64(path, ts):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ts:.2f}", "-i", path, "-frames:v", "1", "-vf", "scale=384:384:force_original_aspect_ratio=decrease", "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1"], capture_output=True, timeout=20)
    return base64.b64encode(r.stdout).decode("utf-8") if r.returncode == 0 and len(r.stdout) >= 1200 else None


def ask_vision_frame(b64_img):
    prompt = "Inspect this frame carefully. Is this pure active 3D mobile battle-royale combat (like Garena Free Fire)? Set is_combat=true ONLY for active match gameplay (NOT lobby, store, or menus). Set has_facecam=true if a human webcam box is visible. Set has_overlay_text=true ONLY if big TikTok/social captions or watermarks cover the screen (ignore small game HUD)."
    try:
        r = requests.post(OLLAMA_CHAT, json={"model": VISION_MODEL, "prompt": prompt, "images": [b64_img], "stream": False, "format": VISION_SCHEMA, "keep_alive": "4m", "options": {"num_ctx": 1024, "num_predict": 110, "temperature": 0.0}}, timeout=120)
        obj = json.loads(r.json().get("response", "{}"))
        ff = bool(obj.get("is_free_fire")) and bool(obj.get("is_combat"))
        bad = bool(obj.get("is_corrupt")) or bool(obj.get("has_facecam")) or bool(obj.get("has_overlay_text"))
        conf = int(obj.get("confidence") or (85 if ff else 0))
        if ff and conf == 0: conf = 85
        why = str(obj.get("scene") or "combat")[:100]
        if bool(obj.get("has_facecam")): why = "REJECT: facecam detected"
        elif bool(obj.get("has_overlay_text")): why = "REJECT: baked captions"
        elif not bool(obj.get("is_combat")): why = "REJECT: lobby/non-combat"
        return ff and (not bad), max(0, min(100, conf)), str(obj.get("weapon") or "unknown")[:40], why
    except Exception as e:
        print(f"[Vision API err] {str(e)[:90]}")
        return False, 0, "unknown", "vision error"


def verify_freefire_video(path, title=""):
    if any(b in (title or "").lower() for b in BANNED_KW): return False, "banned keyword"
    info = probe_video(path)
    if not info: return False, "ffprobe failed"
    dur, w, h = info["duration"], info["width"], info["height"]
    if dur < 14.0 or dur > 600.0 or min(w, h) < 360: return False, f"bad dims/dur {w}x{h} {dur:.1f}s"
    q_ok, q_msg = quality_scan(path, dur)
    if not q_ok: return False, q_msg

    old_hashes = json.load(open(HASH_DB, "r", encoding="utf-8")) if os.path.exists(HASH_DB) else []
    h_val = compute_dhash(path, max(1.0, dur * 0.45))
    if h_val is not None and any((h_val ^ int(o)).bit_count() <= 4 for o in old_hashes if str(o).isdigit()):
        return False, "duplicate visual hash"

    passes, timeouts, best_scene, best_w = 0, 0, "", "unknown"
    for idx, pct in enumerate([0.22, 0.55, 0.80], 1):
        if idx == 3 and (passes >= 2 or (passes == 0 and timeouts == 0)): break
        b64 = extract_frame_b64(path, max(1.0, dur * pct))
        if not b64: continue
        ff_ok, conf, weapon, scene = ask_vision_frame(b64)
        if scene == "vision error": timeouts += 1
        print(f"[Agent AI {idx}/3 @ {dur*pct:.1f}s] raw_ok={ff_ok} | conf={conf}% | '{scene}'")
        if ff_ok and conf >= 50:
            passes += 1; best_scene = scene
            if weapon.lower() not in ["unknown", "none", ""]: best_w = weapon

    if passes < 2: return False, f"Failed Raw Combat AI ({passes}/3 passed)"
    if h_val is not None:
        old_hashes.append(str(h_val))
        json.dump(old_hashes[-300:], open(HASH_DB, "w", encoding="utf-8"))
    try: json.dump({"title": title, "weapon": best_w, "scene": best_scene, "duration": dur}, open("verified_scene.json", "w", encoding="utf-8"), indent=2)
    except Exception: pass
    return True, f"Verified Raw Combat ({passes} AI pass, {q_msg})"


def detect_headshot_second(in_path, dur):
    n_sec = max(1, int(dur))
    scores = [0.0] * n_sec
    try:
        p = subprocess.run(["ffmpeg", "-hide_banner", "-i", in_path, "-an", "-vf", "select='gt(scene,0.10)',showinfo", "-f", "null", "-"], capture_output=True, text=True, timeout=45)
        for m in re.finditer(r"pts_time:([0-9.]+)", p.stderr or ""):
            sec = int(float(m.group(1)))
            if 0 <= sec < n_sec: scores[sec] += 2.5
    except Exception: pass
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", in_path, "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "pipe:1"], capture_output=True, timeout=30)
        pcm = r.stdout
        for s in range(min(n_sec, len(pcm) // 16000)):
            eng = sum(abs(x) for x in struct.unpack("<8000h", pcm[s*16000:(s+1)*16000])) / 8000.0
            scores[s] += eng / 1400.0
    except Exception: pass
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", in_path, "-vf", "fps=1,scale=64:64,format=rgb24", "-f", "rawvideo", "pipe:1"], capture_output=True, timeout=35)
        raw = r.stdout
        fsz = 64 * 64 * 3
        for s in range(min(n_sec, len(raw) // fsz)):
            fr = raw[s*fsz:(s+1)*fsz]
            red_hits = 0
            for y in range(20, 56):
                for x in range(18, 46):
                    k = (y * 64 + x) * 3
                    rv, gv, bv = fr[k], fr[k + 1], fr[k + 2]
                    if rv > 165 and rv > int(gv * 1.65) and rv > int(bv * 1.65): red_hits += 1
            scores[s] += min(6.0, red_hits * 0.25)
    except Exception: pass
    lo = min(6, max(0, n_sec - 3))
    hi = max(lo + 1, n_sec - 1)
    t_kill = max(range(lo, hi), key=lambda s: scores[s])
    return float(t_kill) + 0.5


def crop_action_peak(in_path, out_path="raw_gameplay.mp4", pre_sec=8.5, post_sec=2.5):
    info = probe_video(in_path)
    if not info: return False
    dur = info["duration"]
    t_kill = detect_headshot_second(in_path, dur)
    start_t = max(0.0, t_kill - pre_sec)
    end_t = min(dur, max(start_t + 10.5, t_kill + post_sec))
    clip_dur = end_t - start_t
    kill_at = max(3.0, min(clip_dur - 1.2, t_kill - start_t))
    print(f"[*] Surgical Cut: kill @ {t_kill:.1f}s -> cropping [{start_t:.1f}s .. {end_t:.1f}s] (kill_at={kill_at:.1f}s)")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start_t:.2f}", "-i", in_path, "-t", f"{clip_dur:.2f}", "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-c:a", "aac", "-b:a", "128k", out_path], check=True, timeout=90)
    json.dump({"kill_at": round(kill_at, 2), "duration": round(clip_dur, 2)}, open("verified_timeline.json", "w", encoding="utf-8"))
    return os.path.exists(out_path)


def inspect_timeline_phases(path="raw_gameplay.mp4"):
    info = probe_video(path)
    if not info: return {}
    dur = info["duration"]
    tl = json.load(open("verified_timeline.json", "r", encoding="utf-8")) if os.path.exists("verified_timeline.json") else {}
    k = float(tl.get("kill_at") or dur * 0.72)
    pts = [("before_setup", max(0.3, k - 5.0)), ("tension_aim", max(0.5, k - 1.6)), ("headshot_hit", min(dur - 0.3, k)), ("aftermath", min(dur - 0.2, k + 1.1))]
    tl.update({"duration": round(dur, 2), "kill_at": round(k, 2), "weapon": "unknown"})
    for name, ts in pts:
        b64 = extract_frame_b64(path, ts)
        if not b64: tl[name] = "intense close Free Fire combat"; continue
        try:
            r = requests.post(OLLAMA_CHAT, json={"model": VISION_MODEL, "prompt": f"Describe this Free Fire match moment ({name} @ {ts:.1f}s) in 8-10 clear English words: weapon held, enemy position, damage or movement.", "images": [b64], "stream": False, "format": PHASE_SCHEMA, "keep_alive": "2m", "options": {"num_ctx": 1024, "num_predict": 60, "temperature": 0.1}}, timeout=90)
            obj = json.loads(r.json().get("response", "{}"))
            tl[name] = str(obj.get("scene") or "intense Free Fire combat")[:95]
            w = str(obj.get("weapon") or "").strip()
            if w and w.lower() not in ["unknown", "none"] and tl["weapon"] == "unknown": tl["weapon"] = w[:30]
            print(f"[Timeline {name.upper()} @ {ts:.1f}s] {tl[name]}")
        except Exception:
            tl[name] = "intense Free Fire close combat"
    try: requests.post(OLLAMA_CHAT, json={"model": VISION_MODEL, "prompt": "", "keep_alive": 0}, timeout=8)
    except Exception: pass
    json.dump(tl, open("verified_timeline.json", "w", encoding="utf-8"), indent=2)
    return tl
