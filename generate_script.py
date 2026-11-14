import os, re, json, time, socket, shutil, random, subprocess, requests, yt_dlp
from niche_brain import scout_live_viral_trend, save_history_entry, load_history

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
BANNED = {"devil", "insanity", "999", "devil999", "investigation", "enigma", "mystery", "documentary", "story", "analysis", "exposed", "truth", "panel", "vs", "pure", "skill", "reflex", "hindi", "urdu", "shorts", "short", "viral", "video", "youtube", "channel"}
SHORT_Q = ["free fire one tap headshot gameplay", "free fire awm sniper highlights", "free fire m1887 two shot clutch", "free fire desert eagle headshot", "free fire cs rank headshot montage", "garena free fire pro movement gameplay"]
LONG_Q = ["free fire full gameplay 60fps", "free fire grandmaster rank push gameplay", "free fire solo vs squad full match", "free fire clash squad ranked gameplay", "garena free fire tournament highlights"]

SCENE_ITEM = {"type": "object", "properties": {"time": {"type": "number"}, "narration": {"type": "string"}, "english_subtitle": {"type": "string"}, "focus_cue": {"type": "string"}}, "required": ["time", "narration", "english_subtitle", "focus_cue"]}
CONCEPT_SCHEMA = {"type": "object", "properties": {"topic_angle": {"type": "string"}, "title": {"type": "string"}, "search_query": {"type": "string"}, "visual_focus": {"type": "string"}}, "required": ["topic_angle", "title", "search_query", "visual_focus"]}
META_SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}, "pinned_comment": {"type": "string"}}, "required": ["title", "description", "tags", "pinned_comment"]}
SCENES_SCHEMA = {"type": "object", "properties": {"scenes": {"type": "array", "items": SCENE_ITEM}}, "required": ["scenes"]}
SCRIPT_SCHEMA = {"type": "object", "properties": {**META_SCHEMA["properties"], "scenes": {"type": "array", "items": SCENE_ITEM}}, "required": ["title", "description", "tags", "pinned_comment", "scenes"]}

def warp_proxy():
    try:
        with socket.create_connection(("127.0.0.1", 1080), timeout=1):
            return "socks5://127.0.0.1:1080"
    except Exception:
        return None

def clean_query(raw_q, weapon):
    q = re.sub(r"[\[\]\(\)\{\}_\-|/:#@\"',.?!]+", " ", str(raw_q or "").split(",")[0].lower())
    words = [w for w in q.split() if len(w) > 1 and w not in BANNED][:6]
    c = " ".join(words).strip()
    if c and "free fire" not in c and "garena" not in c:
        c = f"free fire {c}"
    return c if len(c.split()) >= 3 else f"free fire {weapon} headshot highlights"

def build_queries(raw_q, weapon, is_short=True):
    pool = list(SHORT_Q if is_short else LONG_Q)
    random.shuffle(pool)
    out = []
    for item in [clean_query(raw_q, weapon), f"free fire {str(weapon or 'awm').lower()} headshot gameplay"] + pool:
        if item and item not in out:
            out.append(item)
    return out[:6]

def ensure_ollama():
    base = os.environ.get("OLLAMA_URL", "http://localhost:11434").split("/api/")[0].rstrip("/")
    gm = lambda: [m["name"] for m in requests.get(f"{base}/api/tags", timeout=3).json().get("models", []) if m.get("name")]
    try:
        return base, gm()
    except Exception:
        pass
    if not shutil.which("ollama"):
        subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(15):
        time.sleep(1.5)
        try:
            return base, gm()
        except Exception:
            pass
    raise RuntimeError("FATAL: Ollama failed to start.")

def call_ollama_schema(prompt, schema, max_tokens=2048, raise_on_fail=True):
    base, models = ensure_ollama()
    model = models[0] if models else "llama3.2:1b"
    if not models:
        subprocess.run(["ollama", "pull", model], check=True)
    payload = {"model": model, "messages": [{"role": "system", "content": "Output valid compact JSON matching schema. Keep strings concise with no raw newlines."}, {"role": "user", "content": prompt}], "format": schema, "stream": False, "keep_alive": "10m", "options": {"temperature": 0.4, "repeat_penalty": 1.1, "num_ctx": 4096, "num_predict": max_tokens, "num_thread": os.cpu_count() or 2}}
    for att in range(1, 3):
        try:
            print(f"[*] Calling Ollama ({model}) [Attempt {att}/2]...")
            r = requests.post(f"{base}/api/chat", json=payload, timeout=140)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", r.json().get("message", {}).get("content", "").strip()).strip()
            data = json.loads(txt)
            if all(k in data and data[k] for k in schema["required"]):
                return data
        except Exception as e:
            print(f"[!] Ollama attempt {att} notice: {e}")
            time.sleep(1.5)
    if raise_on_fail:
        raise RuntimeError("FATAL: AI structured output failed. Zero fallback policy enforced!")
    return None

def get_dur(p):
    if shutil.which("ffprobe"):
        try:
            return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", p], text=True, timeout=15).strip())
        except Exception:
            return 0.0
    return 15.0

def valid_mp4(p, min_s=10.0):
    return os.path.exists(p) and os.path.getsize(p) >= 350000 and get_dur(p) >= min_s

def clean_tmp():
    if os.path.exists("raw_gameplay.mp4"):
        os.remove("raw_gameplay.mp4")

def fetch_stream(url, hdr=None):
    clean_tmp()
    try:
        with requests.get(url, headers={"User-Agent": UA, **(hdr or {})}, stream=True, timeout=35) as r:
            if r.status_code < 400:
                with open("raw_gameplay.mp4", "wb") as f:
                    for c in r.iter_content(524288):
                        if c:
                            f.write(c)
                if valid_mp4("raw_gameplay.mp4"):
                    return True
    except Exception:
        pass
    clean_tmp()
    return False

def ytdl_get(url, extra=None):
    clean_tmp()
    opts = {"format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/best[height<=1080][ext=mp4]/best", "outtmpl": "raw_gameplay.mp4", "merge_output_format": "mp4", "overwrites": True, "quiet": True, **(extra or {})}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        if valid_mp4("raw_gameplay.mp4"):
            return True
    except Exception:
        pass
    clean_tmp()
    return False

def dl_dm(q, used, min_d, max_d):
    print(f"[*] [Tier 1 - Dailymotion HD] Searching: '{q}'...")
    for s in ("relevance", "visited"):
        for pg in (1, 2):
            try:
                r = requests.get("https://api.dailymotion.com/videos", params={"search": q, "fields": "id,duration,url", "sort": s, "limit": 15, "page": pg, "longer_than": int(min_d), "shorter_than": int(max_d)}, headers={"User-Agent": UA}, timeout=10)
                for it in (r.json().get("list") or []) if r.status_code == 200 else []:
                    did, dur = f"dm_{it.get('id', '')}", int(it.get("duration") or 0)
                    if did not in used and min_d <= dur <= max_d and it.get("url") and ytdl_get(it["url"]):
                        return did
            except Exception:
                pass
    return None

def dl_tt(q, used, min_d, max_d):
    print(f"[*] [Tier 2 - TikTok HD] Searching: '{q}'...")
    time.sleep(2.2)
    hdr, pay = {"User-Agent": UA, "Referer": "https://www.tikwm.com/", "Origin": "https://www.tikwm.com"}, {"keywords": q, "count": 15, "cursor": 0, "hd": 1}
    for post in (True, False):
        try:
            r = requests.post("https://www.tikwm.com/api/feed/search", data=pay, headers=hdr, timeout=15) if post else requests.get("https://www.tikwm.com/api/feed/search", params=pay, headers=hdr, timeout=15)
            d = r.json().get("data") if r.status_code == 200 and r.json().get("code") == 0 else None
            vids = d.get("videos", []) if isinstance(d, dict) else (d if isinstance(d, list) else [])
            for v in vids:
                vid, dur = str(v.get("video_id") or v.get("id") or "").strip(), int(v.get("duration") or 0)
                u = v.get("hdplay") or v.get("play") or ""
                u = f"https://www.tikwm.com{u}" if u.startswith("/") else u
                if vid and f"tt_{vid}" not in used and (dur == 0 or min_d <= dur <= max_d) and u and fetch_stream(u, {"Referer": "https://www.tikwm.com/"}):
                    return f"tt_{vid}"
        except Exception:
            time.sleep(2.0)
    return None

def dl_twitch(used, min_d, max_d):
    print("[*] [Tier 3 - Twitch Free Fire Clips] Checking...")
    hdr = {"Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko", "Content-Type": "application/json", "User-Agent": UA}
    qs = "query($s: ID!, $l: Int, $c: GameClipsInput){game(slug:$s){clips(first:$l,criteria:$c){edges{node{slug durationSeconds url}}}}}"
    qn = "query($n: String!, $l: Int, $c: GameClipsInput){game(name:$n){clips(first:$l,criteria:$c){edges{node{slug durationSeconds url}}}}}"
    for gq, gv in [(qs, {"s": "garena-free-fire", "l": 20, "c": {"filter": "LAST_MONTH"}}), (qs, {"s": "garena-free-fire", "l": 20, "c": {"filter": "ALL_TIME"}}), (qn, {"n": "Garena Free Fire", "l": 20, "c": {"filter": "ALL_TIME"}})]:
        try:
            r = requests.post("https://gql.twitch.tv/gql", headers=hdr, json={"query": gq, "variables": gv}, timeout=12)
            edges = ((((r.json() or {}).get("data") or {}).get("game") or {}).get("clips") or {}).get("edges") or [] if r.status_code == 200 else []
            for e in edges:
                n = e.get("node") or {}
                sl, dur = n.get("slug") or "", int(n.get("durationSeconds") or 0)
                if sl and f"tw_{sl}" not in used and (dur == 0 or min_d <= dur <= max_d) and ytdl_get(n.get("url") or f"https://clips.twitch.tv/{sl}"):
                    return f"tw_{sl}"
        except Exception:
            pass
    return None

def dl_inv_piped(q, used, min_d, max_d):
    print(f"[*] [Tier 4 - Live Invidious/Piped] Checking: '{q}'...")
    inv = ["https://inv.nadeko.net", "https://yewtu.be"]
    try:
        ir = requests.get("https://api.invidious.io/instances.json?sort_by=health", timeout=6)
        if ir.status_code == 200:
            inv = [f"https://{x[0]}" for x in ir.json() if isinstance(x, list) and len(x) > 1 and isinstance(x[1], dict) and x[1].get("type") == "https" and x[1].get("api")][:5] + inv
    except Exception:
        pass
    for node in inv[:5]:
        try:
            r = requests.get(f"{node}/api/v1/search", params={"q": q, "type": "video"}, timeout=6)
            for it in (r.json() if r.status_code == 200 else [])[:4]:
                vid = it.get("videoId")
                if vid and vid not in used and min_d <= int(it.get("lengthSeconds") or 0) <= max_d:
                    vr = requests.get(f"{node}/api/v1/videos/{vid}", timeout=6)
                    for s in (vr.json().get("formatStreams") or []) if vr.status_code == 200 else []:
                        if s.get("container") == "mp4" and s.get("url") and fetch_stream(s["url"]):
                            return vid
        except Exception:
            pass
    return None

def dl_yt(q, used, min_d, max_d):
    px, js = warp_proxy(), ("deno" if shutil.which("deno") else ("node" if shutil.which("node") else None))
    print(f"[*] [Tier 5 - YouTube Bonus] (WARP={'ON' if px else 'OFF'}): '{q}'...")
    ex = {"extractor_args": {"youtube": {"player_client": ["tv", "android_vr", "mweb"]}}, "sleep_requests": 1, **({"proxy": px} if px else {}), **({"js_runtimes": {js: {}}} if js else {}), **({"cookiefile": "cookies.txt"} if os.path.exists("cookies.txt") else {})}
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True, **({"proxy": px} if px else {})}) as ydl:
            cands = [e["id"] for e in ((ydl.extract_info(f"ytsearch5:{q}", download=False) or {}).get("entries") or []) if e.get("id") and e["id"] not in used and (int(e.get("duration") or 0) == 0 or min_d <= int(e.get("duration") or 0) <= max_d)]
        for vid in cands[:3]:
            if ytdl_get(f"https://www.youtube.com/watch?v={vid}", ex):
                return vid
    except Exception:
        pass
    return None

def generate_script():
    plan = next((json.load(open(f, encoding="utf-8")) for f in ("daily_plan.json", "task_plan.json") if os.path.exists(f)), {})
    fmt = plan.get("format_type", plan.get("type", "short"))
    is_short = str(fmt).lower() != "long"
    bp = scout_live_viral_trend(format_type=fmt)
    bp["target_duration"] = float(plan.get("target_duration", random.uniform(28.0, 33.5) if is_short else 900.0))
    used = set(load_history().get("video_ids", []))

    concept = call_ollama_schema(f"DEVIL INSANITY (DEVIL-999). Invent ONE Free Fire concept. search_query MUST be a plain 4-6 word phrase (NO brackets/commas/hyphens).\n{bp['prompt_context']}", CONCEPT_SCHEMA, max_tokens=350)
    queries = build_queries(concept["search_query"], bp["weapon"], is_short=is_short)
    q, min_d, max_d, vid = queries[0], *((15, 300) if is_short else (120, 1800)), None
    print(f"[+] AI Topic: {concept['title']} | Primary Query: '{q}'")

    for cq in queries:
        vid = dl_dm(cq, used, min_d, max_d) or (dl_tt(cq, used, 15, 240) if is_short else None)
        if vid:
            q = cq; break
    if not vid:
        vid = dl_twitch(used, 15, max_d)
    if not vid:
        for cq in queries[:3]:
            vid = dl_inv_piped(cq, used, min_d, max_d) or dl_yt(cq, used, min_d, max_d)
            if vid:
                q = cq; break
    if not vid or not valid_mp4("raw_gameplay.mp4"):
        raise RuntimeError(f"FATAL: All real gameplay streams failed for {queries}. Zero fallback policy enforced!")

    dur, t_dur = get_dur("raw_gameplay.mp4"), round(bp["target_duration"], 1)
    times = [round(i * (t_dur / 7.0), 1) for i in range(7)]
    print(f"[+] REAL GAMEPLAY LOCKED: {vid} ({os.path.getsize('raw_gameplay.mp4')/1048576:.2f} MB, {dur:.1f}s)")
    base_p = f"Topic: '{concept['title']}' | Pillar: {bp['pillar_name']} | Weapon: {bp['weapon']} (Dmg: {bp['damage']}) | Hook: {bp['psychology_strategy']} | Clip: {dur:.1f}s -> Target: {t_dur}s"
    ai_s = call_ollama_schema(f"Write 7-scene Roman Urdu narration (10-14 words each, no emojis) + short English subtitles for {base_p} | Timestamps: {times} | Max 5 tags, 1-line description.", SCRIPT_SCHEMA, max_tokens=2048, raise_on_fail=False)
    if not ai_s:
        print("[*] Switching to 2-Step Split Schema for 1b reliability...")
        ai_m = call_ollama_schema(f"YouTube title, 1-line description, max 5 tags, 1 Roman Urdu pinned_comment for {base_p}.", META_SCHEMA, max_tokens=600)
        ai_sc = call_ollama_schema(f"EXACTLY 7 scenes with timestamps {times}. Short Roman Urdu narration (10-14 words, no emojis), short english_subtitle, focus_cue for {base_p}.", SCENES_SCHEMA, max_tokens=1600)
        ai_s = {**ai_m, "scenes": ai_sc["scenes"]}

    scenes = [{"time": float(s.get("time", times[min(i, 6)])), "narration": str(s.get("narration", "")).strip(), "text": str(s.get("narration", "")).strip(), "english_subtitle": str(s.get("english_subtitle", "")).strip(), "focus_cue": str(s.get("focus_cue") or "crosshair_lock")} for i, s in enumerate(ai_s["scenes"])]
    out = {"title": ai_s.get("title") or concept["title"], "topic": concept["topic_angle"], "description": ai_s.get("description", ""), "tags": ai_s.get("tags", ["freefire", "shorts", "gaming"]), "pinned_comment": ai_s.get("pinned_comment", ""), "pillar": bp["pillar"], "pillar_id": bp["pillar_id"], "pillar_name": bp["pillar_name"], "psychology_strategy": bp["psychology_strategy"], "search_query": q, "source_video_id": vid, "weapon": bp["weapon"], "damage": bp["damage"], "format_type": fmt, "target_duration": bp["target_duration"], "player_tag": "DEVIL-999", "script": " ".join(s["narration"] for s in scenes), "english_script": " ".join(s["english_subtitle"] for s in scenes), "scenes": scenes}
    json.dump(out, open("current_script.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    if os.path.isdir("kaggle_render"):
        shutil.copy2("current_script.json", "kaggle_render/current_script.json")
    save_history_entry(query=q, video_id=vid, title=out["title"], pillar_id=bp["pillar_id"])
    print("[+] Done! Structured AI Script & Real Video saved.")

if __name__ == "__main__":
    generate_script()
