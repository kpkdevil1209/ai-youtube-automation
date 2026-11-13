import os, json, time, shutil, random, subprocess, requests, yt_dlp
from niche_brain import scout_live_viral_trend, save_history_entry, load_history

PIPED = ["https://pipedapi.kavin.rocks", "https://pipedapi-libre.kavin.rocks", "https://pipedapi.leptons.xyz", "https://pipedapi.adminforge.de", "https://api.piped.private.coffee"]
INVIDIOUS = ["https://inv.nadeko.net", "https://yewtu.be", "https://invidious.nerdvpn.de", "https://invidious.privacydev.net"]

CONCEPT_SCHEMA = {
    "type": "object",
    "properties": {
        "topic_angle": {"type": "string"},
        "title": {"type": "string"},
        "search_query": {"type": "string"},
        "visual_focus": {"type": "string"}
    },
    "required": ["topic_angle", "title", "search_query", "visual_focus"]
}

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "pinned_comment": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "time": {"type": "number"},
                    "narration": {"type": "string"},
                    "english_subtitle": {"type": "string"},
                    "focus_cue": {"type": "string"}
                },
                "required": ["time", "narration", "english_subtitle", "focus_cue"]
            }
        }
    },
    "required": ["title", "description", "tags", "pinned_comment", "scenes"]
}

def ensure_ollama():
    base = os.environ.get("OLLAMA_URL", "http://localhost:11434").split("/api/")[0].rstrip("/")
    def get_models():
        return [m["name"] for m in requests.get(f"{base}/api/tags", timeout=3).json().get("models", []) if m.get("name")]
    try:
        return base, get_models()
    except Exception:
        pass
    if not shutil.which("ollama"):
        print("[*] Installing Ollama...")
        subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(15):
        time.sleep(1.5)
        try:
            return base, get_models()
        except Exception:
            continue
    raise RuntimeError("FATAL: Ollama failed to start.")

def call_ollama_schema(prompt, schema, max_tokens=600):
    base, models = ensure_ollama()
    model = models[0] if models else "llama3.2:1b"
    if not models:
        print(f"[*] Pulling '{model}'...")
        subprocess.run(["ollama", "pull", model], check=True)
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": "Free Fire YouTube strategist. Output valid JSON strictly matching schema."}, {"role": "user", "content": prompt}],
        "format": schema,
        "stream": False,
        "keep_alive": "10m",
        "options": {"temperature": 0.5, "num_ctx": 1536, "num_predict": max_tokens, "num_thread": os.cpu_count() or 2}
    }
    for att in range(1, 4):
        try:
            print(f"[*] Calling Ollama ({model}) [Attempt {att}/3]...")
            r = requests.post(f"{base}/api/chat", json=payload, timeout=110)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
            txt = r.json().get("message", {}).get("content", "").strip()
            if not txt:
                raise ValueError("Empty response content")
            data = json.loads(txt)
            if all(k in data and data[k] for k in schema["required"]):
                return data
            raise ValueError(f"Missing required keys in: {list(data.keys())}")
        except Exception as e:
            print(f"[!] Ollama attempt {att} notice: {e}")
            time.sleep(2)
    raise RuntimeError("FATAL: AI structured output failed. Zero fallback policy enforced!")

def get_dur(path):
    if shutil.which("ffprobe"):
        try:
            return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path], text=True).strip())
        except Exception:
            return 0.0
    try:
        with open(path, "rb") as f:
            h = f.read(64)
        return 15.0 if (b"ftyp" in h or b"webm" in h.lower()) else 0.0
    except Exception:
        return 0.0

def valid_mp4(p):
    return os.path.exists(p) and os.path.getsize(p) >= 350000 and get_dur(p) >= 4.0

def clean_tmp():
    if os.path.exists("raw_gameplay.mp4"):
        os.remove("raw_gameplay.mp4")

def fetch_stream(url, hdr=None):
    try:
        r = requests.get(url, headers=hdr or {}, stream=True, timeout=25)
        if r.status_code == 200:
            with open("raw_gameplay.mp4", "wb") as f:
                for c in r.iter_content(1048576):
                    if c:
                        f.write(c)
            return valid_mp4("raw_gameplay.mp4")
    except Exception:
        pass
    return False

def dl_yt(q, used):
    print(f"[*] [Tier 1] yt-dlp searching: '{q}'...")
    js_rt = "deno" if shutil.which("deno") else ("node" if shutil.which("node") else None)
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True, "default_search": "ytsearch5", "noplaylist": True}) as ydl:
            cands = [e.get("id") for e in ydl.extract_info(f"ytsearch5:{q}", download=False).get("entries", []) if e.get("id") and e.get("id") not in used]
    except Exception:
        cands = []
    for vid in cands[:3]:
        opts = {"format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best", "outtmpl": "raw_gameplay.mp4", "overwrites": True, "quiet": True, "extractor_args": {"youtube": {"player_client": ["web_safari", "tv_embedded", "android_creator", "ios"], "player_skip": ["configs"]}}}
        if js_rt:
            opts["js_runtimes"] = {js_rt: {}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={vid}"])
            if valid_mp4("raw_gameplay.mp4"):
                return vid
        except Exception as e:
            print(f"[!] Tier 1 notice ({vid}): {str(e)[:80]}")
        clean_tmp()
    return None

def dl_piped(q, used):
    print("[*] [Tier 2] Checking Piped API...")
    for node in random.sample(PIPED, len(PIPED)):
        try:
            r = requests.get(f"{node}/search?q={requests.utils.quote(q)}&filter=videos", timeout=4)
            if r.status_code != 200:
                continue
            for it in r.json().get("items", [])[:3]:
                if "v=" not in it.get("url", ""):
                    continue
                vid = it["url"].split("v=")[-1].split("&")[0]
                if vid in used:
                    continue
                sr = requests.get(f"{node}/streams/{vid}", timeout=4)
                if sr.status_code != 200:
                    continue
                streams = sr.json().get("videoStreams", [])
                mp4s = [s for s in streams if s.get("format") == "MPEG_4" and not s.get("videoOnly")] or [s for s in streams if s.get("format") == "MPEG_4"]
                if mp4s and fetch_stream(mp4s[0].get("url")):
                    return vid
                clean_tmp()
        except Exception:
            continue
    return None

def dl_invid(q, used):
    print("[*] [Tier 3] Checking Invidious API...")
    for node in random.sample(INVIDIOUS, len(INVIDIOUS)):
        try:
            r = requests.get(f"{node}/api/v1/search?q={requests.utils.quote(q)}&type=video", timeout=4)
            if r.status_code != 200:
                continue
            for it in [i for i in r.json() if i.get("videoId") and i.get("videoId") not in used][:3]:
                vr = requests.get(f"{node}/api/v1/videos/{it['videoId']}", timeout=4)
                if vr.status_code == 200:
                    for s in vr.json().get("formatStreams", []):
                        if s.get("container") == "mp4" and fetch_stream(s.get("url")):
                            return it["videoId"]
                clean_tmp()
        except Exception:
            continue
    return None

def dl_dailymotion(q, used):
    print(f"[*] [Tier 4] Searching Unblocked Dailymotion HD: '{q}'...")
    try:
        r = requests.get(f"https://api.dailymotion.com/videos?search={requests.utils.quote(q)}&limit=10&fields=id,duration,url", timeout=8)
        for it in r.json().get("list", []):
            did = f"dm_{it.get('id', '')}"
            if did in used or int(it.get("duration") or 0) < 12 or not it.get("url"):
                continue
            try:
                with yt_dlp.YoutubeDL({"format": "best[height<=1080]/best", "outtmpl": "raw_gameplay.mp4", "merge_output_format": "mp4", "overwrites": True, "quiet": True}) as ydl:
                    ydl.download([it["url"]])
                if valid_mp4("raw_gameplay.mp4"):
                    return did
            except Exception:
                pass
            clean_tmp()
    except Exception as e:
        print(f"[!] Dailymotion notice: {e}")
    return None

def dl_reddit(used):
    print("[*] [Tier 5] Harvesting Free Fire clips from Reddit...")
    hdr = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0.0.0 Safari/537.36"}
    for sub in ["freefire", "freefireclips"]:
        for sort in ["hot", "new", "top"]:
            try:
                r = requests.get(f"https://www.reddit.com/r/{sub}/{sort}.json?limit=25&t=month", headers=hdr, timeout=8)
                for p in r.json().get("data", {}).get("children", []):
                    d = p.get("data", {})
                    pid = f"reddit_{d.get('id', '')}"
                    v = d.get("media", {}).get("reddit_video", {}).get("fallback_url")
                    if pid not in used and d.get("is_video") and v and fetch_stream(v, hdr):
                        return pid
                    clean_tmp()
            except Exception:
                continue
    return None

def generate_script():
    plan = {}
    for fn in ["daily_plan.json", "task_plan.json"]:
        if os.path.exists(fn):
            plan = json.load(open(fn, "r", encoding="utf-8"))
            break
    fmt = plan.get("format_type", plan.get("type", "short"))
    bp = scout_live_viral_trend(format_type=fmt)
    bp["target_duration"] = float(plan.get("target_duration", random.uniform(28.0, 33.5)))
    used = set(load_history().get("video_ids", []))

    concept = call_ollama_schema(
        f"Channel DEVIL INSANITY (DEVIL-999). Invent ONE new Free Fire video concept & 5-7 English word search_query (never repeat banned queries):\n{bp['prompt_context']}",
        CONCEPT_SCHEMA, max_tokens=220
    )
    q = concept["search_query"]
    print(f"[+] AI Topic: {concept['title']} | Query: '{q}'")

    clean_tmp()
    vid = dl_yt(q, used) or dl_piped(q, used) or dl_invid(q, used) or dl_dailymotion(q, used) or dl_reddit(used)
    if not vid or not valid_mp4("raw_gameplay.mp4"):
        raise RuntimeError(f"FATAL: All 5 real gameplay streams failed for '{q}'. Zero fallback policy enforced!")

    dur = get_dur("raw_gameplay.mp4")
    print(f"[+] REAL GAMEPLAY LOCKED: {vid} ({os.path.getsize('raw_gameplay.mp4')/1048576:.2f} MB, {dur:.1f}s)")
    t_dur = round(bp["target_duration"], 1)
    times = [round(i * (t_dur / 7.0), 1) for i in range(7)]

    ai_s = call_ollama_schema(
        f"Write 7-scene Roman Urdu narration + English subtitles for '{concept['title']}' | Pillar: {bp['pillar_name']} | Weapon: {bp['weapon']} (Dmg: {bp['damage']}) | Hook: {bp['psychology_strategy']} | Clip: {dur:.1f}s -> Target: {t_dur}s | Exact 7 timestamps: {times}. Keep narration punchy mobile-gamer Roman Urdu without emojis.",
        SCRIPT_SCHEMA, max_tokens=700
    )
    scenes = [{"time": float(s.get("time", times[min(i, 6)])), "narration": str(s.get("narration", "")).strip(), "text": str(s.get("narration", "")).strip(), "english_subtitle": str(s.get("english_subtitle", "")).strip(), "focus_cue": str(s.get("focus_cue") or "crosshair_lock")} for i, s in enumerate(ai_s["scenes"])]

    out = {"title": ai_s.get("title") or concept["title"], "topic": concept["topic_angle"], "description": ai_s.get("description", ""), "tags": ai_s.get("tags", ["freefire", "shorts", "gaming"]), "pinned_comment": ai_s.get("pinned_comment", ""), "pillar": bp["pillar"], "pillar_id": bp["pillar_id"], "pillar_name": bp["pillar_name"], "psychology_strategy": bp["psychology_strategy"], "search_query": q, "source_video_id": vid, "weapon": bp["weapon"], "damage": bp["damage"], "format_type": fmt, "target_duration": bp["target_duration"], "player_tag": "DEVIL-999", "script": " ".join(s["narration"] for s in scenes), "english_script": " ".join(s["english_subtitle"] for s in scenes), "scenes": scenes}
    json.dump(out, open("current_script.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    if os.path.isdir("kaggle_render"):
        shutil.copy2("current_script.json", "kaggle_render/current_script.json")
    save_history_entry(query=q, video_id=vid, title=out["title"], pillar_id=bp["pillar_id"])
    print("[+] Done! Structured AI Script & Real Video saved.")

if __name__ == "__main__":
    generate_script()
